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

    animate_list = []
    if "first_person" in animation_map:
        animate_list.append({"first_person": "c.is_first_person"})
    if "third_person" in animation_map:
        animate_list.append(
            {
                "third_person": (
                    "!c.is_first_person && c.item_slot != 'head'"
                    if "head" in animation_map
                    else "!c.is_first_person"
                )
            }
        )
    if "head" in animation_map:
        animate_list.append({"head": "!c.is_first_person && c.item_slot == 'head'"})

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
                    "animate": animate_list,
                },
                "render_controllers": [
                    "controller.render.item_default",
                ],
            }
        },
    }
