"""Builder for Bedrock 1.16.0 Entity/Attachable Geometry (.geo.json)."""

from typing import Any, Dict, List, Optional, Tuple
from ..parser.item_parser import ParsedJavaModel
from .math_utils import (
    java_box_to_bedrock_cube,
    java_face_uv_to_bedrock,
    java_rotation_to_bedrock,
)


def build_bedrock_geometry(
    model: ParsedJavaModel,
    tex_width: int = 16,
    tex_height: int = 16,
    uv_offsets: Optional[Dict[str, Tuple[int, int, int, int]]] = None,
) -> Dict[str, Any]:
    """Convert a ParsedJavaModel into a Bedrock 1.16.0 minecraft:geometry JSON dictionary.

    Args:
        model: Parsed Java model.
        tex_width: Total atlas or texture width in pixels.
        tex_height: Total atlas or texture height in pixels.
        uv_offsets: Optional mapping of texture key (e.g. '0', 'layer0') to
            (offset_x, offset_y, sub_width, sub_height) when using a stitched texture atlas.
    """
    geometry_id = f"geometry.j2b.{model.short_name}"
    root_bone_name = "root_item"

    root_cubes: List[Dict[str, Any]] = []
    child_bones: List[Dict[str, Any]] = []
    rot_groups: Dict[Tuple[float, float, float, float, float, float], List[Dict[str, Any]]] = {}

    for elem in model.elements:
        from_pos = elem.get("from", [0.0, 0.0, 0.0])
        to_pos = elem.get("to", [16.0, 16.0, 16.0])
        origin, size = java_box_to_bedrock_cube(from_pos, to_pos)

        faces_raw = elem.get("faces", {})
        bedrock_uv: Dict[str, Any] = {}
        for face_name, face_data in faces_raw.items():
            if not isinstance(face_data, dict):
                continue
            tex_var = str(face_data.get("texture", "")).lstrip("#")
            if uv_offsets and tex_var in uv_offsets:
                off_x, off_y, sub_w, sub_h = uv_offsets[tex_var]
                face_uv = java_face_uv_to_bedrock(
                    face_name, face_data, from_pos, to_pos, sub_w, sub_h
                )
                face_uv["uv"] = [
                    round(face_uv["uv"][0] + off_x, 4),
                    round(face_uv["uv"][1] + off_y, 4),
                ]
            else:
                face_uv = java_face_uv_to_bedrock(
                    face_name, face_data, from_pos, to_pos, tex_width, tex_height
                )
            bedrock_uv[face_name] = face_uv

        cube_obj: Dict[str, Any] = {
            "origin": origin,
            "size": size,
            "uv": bedrock_uv,
        }

        rot_raw = elem.get("rotation")
        if rot_raw and float(rot_raw.get("angle", 0.0)) != 0.0:
            pivot, euler = java_rotation_to_bedrock(rot_raw)
            key = (pivot[0], pivot[1], pivot[2], euler[0], euler[1], euler[2])
            rot_groups.setdefault(key, []).append(cube_obj)
        else:
            root_cubes.append(cube_obj)

    for idx, (key, cubes) in enumerate(rot_groups.items(), start=1):
        px, py, pz, rx, ry, rz = key
        child_bones.append(
            {
                "name": f"bone_rot_{idx}",
                "parent": root_bone_name,
                "pivot": [px, py, pz],
                "rotation": [rx, ry, rz],
                "cubes": cubes,
            }
        )

    bones: List[Dict[str, Any]] = [
        {
            "name": root_bone_name,
            "pivot": [0.0, 8.0, 0.0],
            "binding": "(c.item_slot == 'head' || c.item_slot == 'slot.armor.head') ? 'head' : q.item_slot_to_bone_name(c.item_slot)",
            **({"cubes": root_cubes} if root_cubes else {}),
        }
    ]
    bones.extend(child_bones)

    return {
        "format_version": "1.16.0",
        "minecraft:geometry": [
            {
                "description": {
                    "identifier": geometry_id,
                    "texture_width": tex_width,
                    "texture_height": tex_height,
                    "visible_bounds_width": 4.0,
                    "visible_bounds_height": 4.0,
                    "visible_bounds_offset": [0.0, 0.5, 0.0],
                },
                "bones": bones,
            }
        ],
    }
