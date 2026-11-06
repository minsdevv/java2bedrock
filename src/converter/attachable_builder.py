"""Builder for Bedrock Attachables (attachables/*.json)."""

from typing import Any, Dict
from ..parser.item_parser import ParsedJavaModel


def build_bedrock_attachable(
    model: ParsedJavaModel,
    texture_rel_path: str,
    animation_map: Dict[str, str],
    default_material: str = "entity_alphatest",
) -> Dict[str, Any]:
    """Build a Bedrock 1.10.0 minecraft:attachable JSON dictionary for a 3D item."""
    geometry_id = f"geometry.j2b.{model.short_name}"

    # Slot variables are computed once per frame (Geyser sets c.item_slot to main_hand/off_hand/head).
    pre_animation = [
        "v.main_hand = c.item_slot == 'main_hand';",
        "v.off_hand = c.item_slot == 'off_hand';",
        "v.head = c.item_slot == 'head';",
    ]
    animate_list = [
        {"third_person": "v.main_hand && !c.is_first_person"},
        {"third_person_left": "v.off_hand && !c.is_first_person"},
        {"head": "v.head && !c.is_first_person"},
        {"first_person": "v.main_hand && c.is_first_person"},
        {"first_person_left": "v.off_hand && c.is_first_person"},
        {"first_person_head": "v.head && c.is_first_person"},
    ]
    animation_map = dict(animation_map)
    animation_map["first_person_head"] = animation_map.get("disable", "animation.j2b.disable")
    animation_map.pop("disable", None)

    return {
        "format_version": "1.10.0",
        "minecraft:attachable": {
            "description": {
                "identifier": model.bedrock_identifier,
                "materials": {
                    "default": default_material,
                    "enchanted": "entity_alphatest_glint",
                },
                "textures": {
                    "default": texture_rel_path,
                    "enchanted": "textures/misc/enchanted_item_glint",
                },
                "geometry": {
                    "default": geometry_id,
                },
                "animations": animation_map,
                "scripts": {
                    "pre_animation": pre_animation,
                    "animate": animate_list,
                },
                "render_controllers": [
                    "controller.render.item_default",
                ],
            }
        },
    }
