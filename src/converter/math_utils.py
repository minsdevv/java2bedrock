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


def build_display_animation(
    short_name: str,
    display_settings: Dict[str, Dict[str, List[float]]],
    root_bone: str = "root_item",
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Build Bedrock attachable animations for thirdperson, firstperson, and head displays."""
    animations: Dict[str, Any] = {}
    anim_map: Dict[str, str] = {}

    # 1. Third-person Right Hand
    tp_has_right = "thirdperson_righthand" in display_settings
    tp_right = display_settings.get("thirdperson_righthand") or display_settings.get("thirdperson_lefthand") or {}
    tp_rot = tp_right.get("rotation", [0.0, 0.0, 0.0])
    tp_trans = tp_right.get("translation", [0.0, 0.0, 0.0])
    # Fallback scale: blocks in hand default to ~0.375, items to 0.68 instead of oversized 1.0
    tp_scale = tp_right.get("scale", [0.375, 0.375, 0.375] if "head" in display_settings else [0.68, 0.68, 0.68])

    # If the model explicitly defines thirdperson_righthand (like 3D guns, bat, shields),
    # respect its custom Euler angles without arbitrarily adding 90 deg tilt to X.
    # Vanilla fallback tools (where no thirdperson display exists) still need the +90 deg X tilt.
    if tp_has_right:
        bedrock_tp_rot = [
            round(-float(tp_rot[0]), 4),
            round(-float(tp_rot[1]), 4),
            round(float(tp_rot[2]), 4),
        ]
        bedrock_tp_trans = [
            round(-float(tp_trans[0]), 4),
            round(float(tp_trans[1]), 4),
            round(float(tp_trans[2]), 4),
        ]
    else:
        bedrock_tp_rot = [
            round(90.0 - float(tp_rot[0]), 4),
            round(-float(tp_rot[1]), 4),
            round(-float(tp_rot[2]), 4),
        ]
        bedrock_tp_trans = [
            round(-float(tp_trans[0]), 4),
            round(float(tp_trans[1]) + 6.0, 4),
            round(float(tp_trans[2]) + 1.0, 4),
        ]

    tp_anim_id = f"animation.j2b.{short_name}.third_person"
    animations[tp_anim_id] = {
        "loop": True,
        "bones": {
            root_bone: {
                "rotation": bedrock_tp_rot,
                "position": bedrock_tp_trans,
                "scale": [round(float(x), 4) for x in tp_scale],
            }
        },
    }
    anim_map["third_person"] = tp_anim_id

    # 2. Third-person Left Hand (offhand / shields / dual wield)
    if "thirdperson_lefthand" in display_settings:
        tp_left = display_settings["thirdperson_lefthand"]
        tpl_rot = tp_left.get("rotation", [0.0, 0.0, 0.0])
        tpl_trans = tp_left.get("translation", [0.0, 0.0, 0.0])
        tpl_scale = tp_left.get("scale", [0.375, 0.375, 0.375] if "head" in display_settings else [0.68, 0.68, 0.68])
        tpl_anim_id = f"animation.j2b.{short_name}.third_person_left"
        animations[tpl_anim_id] = {
            "loop": True,
            "bones": {
                root_bone: {
                    "rotation": [
                        round(-float(tpl_rot[0]), 4),
                        round(-float(tpl_rot[1]), 4),
                        round(float(tpl_rot[2]), 4),
                    ],
                    "position": [
                        round(-float(tpl_trans[0]), 4),
                        round(float(tpl_trans[1]), 4),
                        round(float(tpl_trans[2]), 4),
                    ],
                    "scale": [round(float(x), 4) for x in tpl_scale],
                }
            },
        }
        anim_map["third_person_left"] = tpl_anim_id

    # 3. Default First-person Right Hand
    fp_has_right = "firstperson_righthand" in display_settings
    fp_right = display_settings.get("firstperson_righthand") or display_settings.get("firstperson_lefthand") or {}
    fp_rot = fp_right.get("rotation", [0.0, 0.0, 0.0])
    fp_trans = fp_right.get("translation", [0.0, 0.0, 0.0])
    fp_scale = fp_right.get("scale", [0.4, 0.4, 0.4] if "head" in display_settings else [0.68, 0.68, 0.68])

    if fp_has_right:
        bedrock_fp_rot = [
            round(-float(fp_rot[0]), 4),
            round(-float(fp_rot[1]), 4),
            round(float(fp_rot[2]), 4),
        ]
        bedrock_fp_trans = [
            round(-float(fp_trans[0]), 4),
            round(float(fp_trans[1]), 4),
            round(float(fp_trans[2]), 4),
        ]
    else:
        bedrock_fp_rot = [
            round(-float(fp_rot[0]), 4),
            round(-float(fp_rot[1]), 4),
            round(float(fp_rot[2]), 4),
        ]
        bedrock_fp_trans = [
            round(-float(fp_trans[0]) + 3.0, 4),
            round(float(fp_trans[1]) + 12.0, 4),
            round(float(fp_trans[2]) - 3.0, 4),
        ]

    fp_anim_id = f"animation.j2b.{short_name}.first_person"
    animations[fp_anim_id] = {
        "loop": True,
        "bones": {
            root_bone: {
                "rotation": bedrock_fp_rot,
                "position": bedrock_fp_trans,
                "scale": [round(float(x), 4) for x in fp_scale],
            }
        },
    }
    anim_map["first_person"] = fp_anim_id

    # 4. First-person Left Hand
    if "firstperson_lefthand" in display_settings:
        fp_left = display_settings["firstperson_lefthand"]
        fpl_rot = fp_left.get("rotation", [0.0, 0.0, 0.0])
        fpl_trans = fp_left.get("translation", [0.0, 0.0, 0.0])
        fpl_scale = fp_left.get("scale", [0.4, 0.4, 0.4] if "head" in display_settings else [0.68, 0.68, 0.68])
        fpl_anim_id = f"animation.j2b.{short_name}.first_person_left"
        animations[fpl_anim_id] = {
            "loop": True,
            "bones": {
                root_bone: {
                    "rotation": [
                        round(-float(fpl_rot[0]), 4),
                        round(-float(fpl_rot[1]), 4),
                        round(float(fpl_rot[2]), 4),
                    ],
                    "position": [
                        round(-float(fpl_trans[0]), 4),
                        round(float(fpl_trans[1]), 4),
                        round(float(fpl_trans[2]), 4),
                    ],
                    "scale": [round(float(x), 4) for x in fpl_scale],
                }
            },
        }
        anim_map["first_person_left"] = fpl_anim_id

    # 5. Head slot (hats / helmets worn via head slot, or furniture placed on ArmorStand head)
    if "head" in display_settings:
        head_cfg = display_settings["head"]
        h_rot = head_cfg.get("rotation", [0.0, 0.0, 0.0])
        h_trans = head_cfg.get("translation", [0.0, 0.0, 0.0])
        h_scale = head_cfg.get("scale", [1.0, 1.0, 1.0])
        head_anim_id = f"animation.j2b.{short_name}.head"

        # Furniture models on Small ArmorStands have negative translation (e.g. -14 to -19).
        # In Bedrock, the scale (2.0-2.5x) around pivot [0, 8, 0] stretches the base.
        # Adding +8.0 keeps furniture flush with ground (fixing 0.5 block sinking).
        # For wall paintings or furniture with negative z_raw (<= -6.0), add +7.0 to prevent
        # sinking into wall (0.3-0.5 block).
        # Wearable items (hats, helmets, masks) use +16.0 offset to seat snuggly on top of player's head (y=32.0).
        y_raw = float(h_trans[1])
        z_raw = float(h_trans[2])
        if y_raw <= -10.0:
            y_pos = 8.0
            if z_raw <= -6.0:
                z_pos = round(z_raw + 7.0, 4)
            else:
                z_pos = round(z_raw, 4)
        else:
            y_pos = round(y_raw + 16.0, 4)
            z_pos = round(z_raw, 4)

        animations[head_anim_id] = {
            "loop": True,
            "bones": {
                root_bone: {
                    "rotation": [round(-float(h_rot[0]), 4), round(-float(h_rot[1]), 4), round(float(h_rot[2]), 4)],
                    "position": [
                        round(-float(h_trans[0]), 4),
                        y_pos,
                        z_pos,
                    ],
                    "scale": [round(float(x), 4) for x in h_scale],
                }
            },
        }
        anim_map["head"] = head_anim_id

    doc = {
        "format_version": "1.8.0",
        "animations": animations,
    }
    return doc, anim_map
