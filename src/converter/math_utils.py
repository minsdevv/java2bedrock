"""3D Voxel-to-Bedrock Bone & Display Matrix Math Utilities."""

from typing import Any, Dict, List, Optional, Tuple


def java_box_to_bedrock_cube(
    from_pos: List[float],
    to_pos: List[float],
) -> Tuple[List[float], List[float]]:
    """Convert Java voxel bounds [0..16] to Bedrock origin and size centered at [-8..8]."""
    fx, fy, fz = float(from_pos[0]), float(from_pos[1]), float(from_pos[2])
    tx, ty, tz = float(to_pos[0]), float(to_pos[1]), float(to_pos[2])

    size = [
        round(tx - fx, 4),
        round(ty - fy, 4),
        round(tz - fz, 4),
    ]
    origin = [
        round(-(tx - 8.0), 4),
        round(fy, 4),
        round(fz - 8.0, 4),
    ]
    return origin, size


def java_pivot_to_bedrock(origin: List[float]) -> List[float]:
    """Convert Java rotation origin [ox, oy, oz] to Bedrock bone pivot."""
    ox, oy, oz = float(origin[0]), float(origin[1]), float(origin[2])
    return [
        round(-(ox - 8.0), 4),
        round(oy, 4),
        round(oz - 8.0, 4),
    ]


def java_rotation_to_bedrock(rotation_obj: Optional[Dict[str, Any]]) -> Tuple[List[float], List[float]]:
    """Convert Java single-axis element rotation into (bedrock_pivot, bedrock_euler_xyz)."""
    if not rotation_obj:
        return [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]

    origin = rotation_obj.get("origin", [8.0, 8.0, 8.0])
    axis = str(rotation_obj.get("axis", "y")).lower()
    angle = float(rotation_obj.get("angle", 0.0))

    pivot = java_pivot_to_bedrock(origin)
    if axis == "x":
        rot = [round(-angle, 4), 0.0, 0.0]
    elif axis == "y":
        rot = [0.0, round(-angle, 4), 0.0]
    elif axis == "z":
        rot = [0.0, 0.0, round(angle, 4)]
    else:
        rot = [0.0, 0.0, 0.0]

    return pivot, rot


def java_face_uv_to_bedrock(
    face_name: str,
    face_data: Dict[str, Any],
    from_pos: List[float],
    to_pos: List[float],
    tex_width: int = 16,
    tex_height: int = 16,
) -> Dict[str, Any]:
    """Convert Java per-face UV [u1, v1, u2, v2] (in 0..16 space) to Bedrock per-face UV."""
    raw_uv = face_data.get("uv")
    if not raw_uv or len(raw_uv) != 4:
        # Auto-compute default UV from element bounds like vanilla Minecraft
        fx, fy, fz = from_pos
        tx, ty, tz = to_pos
        if face_name in ("north", "south"):
            raw_uv = [fx, 16.0 - ty, tx, 16.0 - fy]
        elif face_name in ("east", "west"):
            raw_uv = [fz, 16.0 - ty, tz, 16.0 - fy]
        else:  # up, down
            raw_uv = [fx, fz, tx, tz]

    u1, v1, u2, v2 = [float(x) for x in raw_uv]
    scale_u = tex_width / 16.0
    scale_v = tex_height / 16.0

    uv = [round(u1 * scale_u, 4), round(v1 * scale_v, 4)]
    uv_size = [round((u2 - u1) * scale_u, 4), round((v2 - v1) * scale_v, 4)]

    result: Dict[str, Any] = {
        "uv": uv,
        "uv_size": uv_size,
    }
    if "rotation" in face_data:
        result["uv_rotation"] = int(face_data["rotation"])
    return result


def _axis_bones(
    root_bone: str,
    cfg: Optional[Dict[str, List[float]]],
    *,
    pos_sign: Tuple[float, float, float],
    pos_scale: float = 1.0,
    default_scale: Optional[float] = None,
    default_rot: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Split a Java display transform (translation/rotation/scale) over the x/y/z bones.

    Java applies translation, then rotation about the model centre, then scale. Bedrock
    bone rotation is split per axis (x outermost) with the Java Y/X signs flipped for the
    handedness change, mirroring the proven Geyser/Java2Bedrock layout.
    """
    bones: Dict[str, Any] = {}
    x_bone: Dict[str, Any] = {}
    if cfg:
        rot = cfg.get("rotation")
        trans = cfg.get("translation")
        scale = cfg.get("scale")
        if rot:
            x_bone["rotation"] = [round(-float(rot[0]), 4), 0, 0]
            bones[f"{root_bone}_y"] = {"rotation": [0, round(-float(rot[1]), 4), 0]}
            bones[f"{root_bone}_z"] = {"rotation": [0, 0, round(float(rot[2]), 4)]}
        elif default_rot is not None:
            x_bone["rotation"] = default_rot
        if trans:
            x_bone["position"] = [
                round(pos_sign[0] * float(trans[0]) * pos_scale, 4),
                round(pos_sign[1] * float(trans[1]) * pos_scale, 4),
                round(pos_sign[2] * float(trans[2]) * pos_scale, 4),
            ]
        if scale:
            x_bone["scale"] = [round(float(v) * (pos_scale if pos_scale != 1.0 else 1.0), 4) for v in scale]
    elif default_rot is not None:
        x_bone["rotation"] = default_rot
    if "scale" not in x_bone and default_scale is not None:
        x_bone["scale"] = default_scale
    if x_bone:
        bones[f"{root_bone}_x"] = x_bone
    return bones


def build_display_animation(
    short_name: str,
    display_settings: Dict[str, Dict[str, List[float]]],
    root_bone: str = "root_item",
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Build Bedrock attachable animations (3rd/1st person main+off hand, head, disable).

    The root bone carries the fixed per-slot base pose of Bedrock's hand bones (the item
    geometry is bound to rightitem/leftitem whose axes differ from Java's), while the
    x/y/z child bones carry the model's own Java display transform.
    """
    pre = f"animation.j2b.{short_name}"
    animations: Dict[str, Any] = {}
    anim_map: Dict[str, str] = {}

    def add(key: str, root_pose: Dict[str, Any], axis: Dict[str, Any]) -> None:
        bones: Dict[str, Any] = {root_bone: root_pose}
        bones.update(axis)
        animations[f"{pre}.{key}"] = {"loop": True, "bones": bones}
        anim_map[key] = f"{pre}.{key}"

    hand3 = {"rotation": [90, 0, 0], "position": [0, 13, -3]}
    hand1 = {"rotation": [90, 60, -40], "position": [4, 10, 4], "scale": 1.5}

    add("third_person", dict(hand3),
        _axis_bones(root_bone, display_settings.get("thirdperson_righthand"), pos_sign=(-1, 1, 1)))
    add("third_person_left", dict(hand3),
        _axis_bones(root_bone, display_settings.get("thirdperson_lefthand"), pos_sign=(1, 1, 1)))
    add("first_person", dict(hand1),
        _axis_bones(root_bone, display_settings.get("firstperson_righthand"),
                    pos_sign=(-1, 1, -1), default_rot=[0.1, 0.1, 0.1]))
    add("first_person_left", dict(hand1),
        _axis_bones(root_bone, display_settings.get("firstperson_lefthand"),
                    pos_sign=(1, 1, -1), default_rot=[0.1, 0.1, 0.1]))

    # Head slot:
    # Wall paintings and wall-mounted furniture (e.g. ItemsAdder furniture_big_painting with ty <= -20, tz <= -6):
    # In commit 56fe157, the in-game verified pose placed them directly on root_bone at y=16.0, z=1.5
    # with un-downscaled scale (h_scale), sitting flush against the wall face without the 0.5-block protrusion.
    head_cfg = display_settings.get("head")
    is_wall_mounted = False
    if head_cfg and "translation" in head_cfg:
        trans = head_cfg["translation"]
        if float(trans[1]) <= -20.0 and float(trans[2]) <= -6.0:
            is_wall_mounted = True

    if is_wall_mounted and head_cfg:
        h_trans = head_cfg.get("translation", [0.0, 0.0, 0.0])
        h_rot = head_cfg.get("rotation", [0.0, 0.0, 0.0])
        h_scale = head_cfg.get("scale", [1.0, 1.0, 1.0])
        animations[f"{pre}.head"] = {
            "loop": True,
            "bones": {
                root_bone: {
                    "rotation": [round(-float(h_rot[0]), 4), round(-float(h_rot[1]), 4), round(float(h_rot[2]), 4)],
                    "position": [round(-float(h_trans[0]), 4), 16.0, 1.5],
                    "scale": [round(float(s), 4) for s in h_scale],
                }
            },
        }
        anim_map["head"] = f"{pre}.head"
    else:
        # Standard head slot: Java renders head items at 0.625 of model size before the display transform.
        head_axis = _axis_bones(
            root_bone, head_cfg, pos_sign=(-1, 1, 1),
            pos_scale=0.625, default_scale=0.625,
        )
        if f"{root_bone}_x" not in head_axis:
            head_axis[f"{root_bone}_x"] = {"scale": 0.625}
        add("head", {"position": [0, 19.9, 0]}, head_axis)

    animations["animation.j2b.disable"] = {
        "loop": True,
        "override_previous_animation": True,
        "bones": {root_bone: {"scale": 0}},
    }
    anim_map["disable"] = "animation.j2b.disable"

    doc = {"format_version": "1.8.0", "animations": animations}
    return doc, anim_map
