"""Converter for Blockbench .bbmodel Custom Mobs -> Bedrock Entity Geometry, Animations, Controllers & Registry."""

from typing import Any, Dict, List

from ..parser.bbmodel_parser import ParsedBBModelMob


def _bb_cube_to_bedrock(
    elem: Dict[str, Any],
    tex_w: int,
    tex_h: int,
) -> Dict[str, Any]:
    """Convert a Blockbench cube element into a Bedrock 1.16.0 cube dictionary."""
    f = elem.get("from", [0.0, 0.0, 0.0])
    t = elem.get("to", [1.0, 1.0, 1.0])
    fx, fy, fz = float(f[0]), float(f[1]), float(f[2])
    tx, ty, tz = float(t[0]), float(t[1]), float(t[2])

    origin = [round(-tx, 4), round(fy, 4), round(fz, 4)]
    size = [round(tx - fx, 4), round(ty - fy, 4), round(tz - fz, 4)]

    faces_raw = elem.get("faces", {})
    bedrock_uv: Dict[str, Any] = {}
    if isinstance(faces_raw, dict) and faces_raw:
        for face_name, face_data in faces_raw.items():
            if not isinstance(face_data, dict) or "uv" not in face_data:
                continue
            uv_arr = face_data["uv"]
            u1, v1, u2, v2 = float(uv_arr[0]), float(uv_arr[1]), float(uv_arr[2]), float(uv_arr[3])
            bedrock_uv[face_name] = {
                "uv": [round(u1, 4), round(v1, 4)],
                "uv_size": [round(u2 - u1, 4), round(v2 - v1, 4)],
            }
    else:
        uv_off = elem.get("uv_offset", [0, 0])
        bedrock_uv = [int(uv_off[0]), int(uv_off[1])]

    cube_obj: Dict[str, Any] = {
        "origin": origin,
        "size": size,
        "uv": bedrock_uv,
    }
    if "inflate" in elem and float(elem["inflate"]) != 0.0:
        cube_obj["inflate"] = round(float(elem["inflate"]), 4)
    if "rotation" in elem and isinstance(elem["rotation"], list) and len(elem["rotation"]) == 3:
        rx, ry, rz = [float(x) for x in elem["rotation"]]
        if (rx, ry, rz) != (0.0, 0.0, 0.0):
            orig = elem.get("origin", [0.0, 0.0, 0.0])
            cube_obj["pivot"] = [round(-float(orig[0]), 4), round(float(orig[1]), 4), round(float(orig[2]), 4)]
            cube_obj["rotation"] = [round(-rx, 4), round(-ry, 4), round(rz, 4)]
    return cube_obj


def build_bedrock_mob_geometry(mob: ParsedBBModelMob) -> Dict[str, Any]:
    """Generate Bedrock 1.16.0 Entity Geometry (.geo.json) from a ParsedBBModelMob."""
    bones_json: List[Dict[str, Any]] = []
    for bone in mob.bones:
        px, py, pz = bone.pivot
        rx, ry, rz = bone.rotation
        b_dict: Dict[str, Any] = {
            "name": bone.name,
            "pivot": [round(-px, 4), round(py, 4), round(pz, 4)],
        }
        if bone.parent_name:
            b_dict["parent"] = bone.parent_name
        if (rx, ry, rz) != (0.0, 0.0, 0.0):
            b_dict["rotation"] = [round(-rx, 4), round(-ry, 4), round(rz, 4)]

        cubes: List[Dict[str, Any]] = []
        for c_uuid in bone.cube_uuids:
            el = mob.elements_by_uuid.get(c_uuid)
            if el:
                cubes.append(_bb_cube_to_bedrock(el, mob.tex_width, mob.tex_height))
        if cubes:
            b_dict["cubes"] = cubes
        bones_json.append(b_dict)

    return {
        "format_version": "1.16.0",
        "minecraft:geometry": [
            {
                "description": {
                    "identifier": f"geometry.j2b.mob_{mob.mob_name}",
                    "texture_width": mob.tex_width,
                    "texture_height": mob.tex_height,
                    "visible_bounds_width": 4.0,
                    "visible_bounds_height": 4.0,
                    "visible_bounds_offset": [0.0, 1.5, 0.0],
                },
                "bones": bones_json,
            }
        ],
    }


def build_bedrock_mob_animations(mob: ParsedBBModelMob) -> Dict[str, Any]:
    """Generate Bedrock 1.8.0 animations/mobs/<mob_name>.animation.json."""
    anims_out: Dict[str, Any] = {}
    for anim in mob.animations:
        anim_id = f"animation.j2b.{mob.mob_name}.{anim.name}"
        loop_val: Any = True if anim.loop == "loop" else ("hold_on_last_frame" if anim.loop == "hold" else False)
        anim_entry: Dict[str, Any] = {
            "loop": loop_val,
            "animation_length": anim.length,
            "bones": anim.bone_channels,
        }
        anims_out[anim_id] = anim_entry

    if not anims_out:
        anims_out[f"animation.j2b.{mob.mob_name}.idle"] = {
            "loop": True,
            "animation_length": 1.0,
            "bones": {},
        }

    return {
        "format_version": "1.8.0",
        "animations": anims_out,
    }


def build_bedrock_mob_animation_controller(mob: ParsedBBModelMob) -> Dict[str, Any]:
    """Generate Bedrock 1.10.0 animation_controllers/mobs/<mob_name>.animation_controllers.json."""
    anim_names = [a.name for a in mob.animations] or ["idle"]
    default_state = "idle" if "idle" in anim_names else anim_names[0]

    states: Dict[str, Any] = {}
    for state_name in anim_names:
        transitions = [
            {other: f"q.property('j2b:anim_state') == '{other}'"}
            for other in anim_names
            if other != state_name
        ]
        state_obj: Dict[str, Any] = {
            "animations": [state_name],
            "blend_transition": 0.2,
        }
        if transitions:
            state_obj["transitions"] = transitions
        states[state_name] = state_obj

    return {
        "format_version": "1.10.0",
        "animation_controllers": {
            f"controller.animation.j2b.mob_{mob.mob_name}": {
                "initial_state": default_state,
                "states": states,
            }
        },
    }


def build_bedrock_mob_entity(
    mob: ParsedBBModelMob,
    texture_rel_path: str,
) -> Dict[str, Any]:
    """Generate Bedrock 1.10.0 entity/mobs/<mob_name>.entity.json."""
    anim_names = [a.name for a in mob.animations] or ["idle"]
    anim_map = {
        name: f"animation.j2b.{mob.mob_name}.{name}" for name in anim_names
    }
    ctrl_id = f"controller.animation.j2b.mob_{mob.mob_name}"
    anim_map["ctrl_main"] = ctrl_id

    return {
        "format_version": "1.10.0",
        "minecraft:client_entity": {
            "description": {
                "identifier": mob.bedrock_entity_id,
                "materials": {
                    "default": "entity_alphatest",
                },
                "textures": {
                    "default": texture_rel_path,
                },
                "geometry": {
                    "default": f"geometry.j2b.mob_{mob.mob_name}",
                },
                "animations": anim_map,
                "scripts": {
                    "animate": [
                        "ctrl_main",
                    ],
                },
                "render_controllers": [
                    "controller.render.j2b.furniture",
                ],
                "spawn_egg": {
                    "base_color": "#2E2E2E",
                    "overlay_color": "#FF4500",
                },
            }
        },
    }


def build_mob_registry(mobs: List[ParsedBBModelMob]) -> Dict[str, Any]:
    """Generate custom_mappings/mob_registry.json for the Geyser Companion Extension."""
    entries: List[Dict[str, Any]] = []
    for mob in mobs:
        anim_states = [a.name for a in mob.animations] or ["idle"]
        entries.append(
            {
                "mob_name": mob.mob_name,
                "bedrock_entity_identifier": mob.bedrock_entity_id,
                "geometry_identifier": f"geometry.j2b.mob_{mob.mob_name}",
                "animation_states": anim_states,
                "default_animation_state": "idle" if "idle" in anim_states else anim_states[0],
                "property_identifier": "j2b:anim_state",
            }
        )
    return {
        "format_version": 1,
        "mobs": entries,
    }
