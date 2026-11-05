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

    is_head_molang = (
        "(c.item_slot == 'head' || c.item_slot == 'slot.armor.head' || q.item_slot_to_bone_name(c.item_slot) == 'head')"
    )
    is_offhand_molang = (
        "(c.item_slot == 'off_hand' || c.item_slot == 'slot.weapon.offhand' || q.item_slot_to_bone_name(c.item_slot) == 'leftitem')"
    )

    animate_list = []
    # 1. First-person view
    if "first_person_left" in animation_map:
        animate_list.append({"first_person_left": f"c.is_first_person && {is_offhand_molang}"})
        if "first_person" in animation_map:
            animate_list.append({"first_person": f"c.is_first_person && !{is_offhand_molang}"})
    elif "first_person" in animation_map:
        animate_list.append({"first_person": "c.is_first_person"})

    # 2. Third-person view
    has_head = "head" in animation_map
    not_head_expr = f" && !{is_head_molang}" if has_head else ""

    if "third_person_left" in animation_map:
        animate_list.append(
            {"third_person_left": f"!c.is_first_person{not_head_expr} && {is_offhand_molang}"}
        )
        if "third_person" in animation_map:
            animate_list.append(
                {"third_person": f"!c.is_first_person{not_head_expr} && !{is_offhand_molang}"}
            )
    elif "third_person" in animation_map:
        animate_list.append(
            {"third_person": f"!c.is_first_person{not_head_expr}"}
        )

    # 3. Head slot (hats / helmets / furniture)
    if has_head:
        animate_list.append({"head": f"!c.is_first_person && {is_head_molang}"})

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
