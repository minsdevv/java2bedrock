"""Builder for Bedrock Attachables (attachables/*.json)."""

from typing import Any, Dict, Optional
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


def build_bedrock_bow_attachable(
    model: ParsedJavaModel,
    standby_tex_rel: str,
    pull0_tex_rel: str,
    pull1_tex_rel: str,
    pull2_tex_rel: str,
    standby_geo: Optional[str] = None,
    pull0_geo: Optional[str] = None,
    pull1_geo: Optional[str] = None,
    pull2_geo: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a Bedrock attachable for a bow supporting native draw/pull animation frames."""
    return {
        "format_version": "1.10.0",
        "minecraft:attachable": {
            "description": {
                "identifier": model.bedrock_identifier,
                "materials": {
                    "default": "entity_alphatest",
                    "enchanted": "entity_alphatest_glint",
                },
                "textures": {
                    "default": standby_tex_rel,
                    "bow_pulling_0": pull0_tex_rel,
                    "bow_pulling_1": pull1_tex_rel,
                    "bow_pulling_2": pull2_tex_rel,
                    "enchanted": "textures/misc/enchanted_item_glint",
                },
                "geometry": {
                    "default": standby_geo or "geometry.bow_standby",
                    "bow_pulling_0": pull0_geo or "geometry.bow_pulling_0",
                    "bow_pulling_1": pull1_geo or "geometry.bow_pulling_1",
                    "bow_pulling_2": pull2_geo or "geometry.bow_pulling_2",
                },
                "animations": {
                    "wield": "animation.bow.wield",
                    "wield_first_person_pull": "animation.bow.wield_first_person_pull",
                },
                "scripts": {
                    "pre_animation": [
                        "variable.charge_amount = math.clamp((query.main_hand_item_max_duration - (query.main_hand_item_use_duration - query.frame_alpha + 1.0)) / 10.0, 0.0, 1.0f);",
                    ],
                    "animate": [
                        "wield",
                        {
                            "wield_first_person_pull": "query.main_hand_item_use_duration > 0.0f && c.is_first_person",
                        },
                    ],
                },
                "render_controllers": [
                    "controller.render.bow",
                ],
            },
        },
    }


def build_bedrock_crossbow_attachable(
    model: ParsedJavaModel,
    standby_tex_rel: str,
    pull0_tex_rel: str,
    pull1_tex_rel: str,
    pull2_tex_rel: str,
    arrow_tex_rel: Optional[str] = None,
    rocket_tex_rel: Optional[str] = None,
    standby_geo: Optional[str] = None,
    pull0_geo: Optional[str] = None,
    pull1_geo: Optional[str] = None,
    pull2_geo: Optional[str] = None,
    arrow_geo: Optional[str] = None,
    rocket_geo: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a Bedrock attachable for a crossbow supporting native pull & loaded states."""
    return {
        "format_version": "1.10.0",
        "minecraft:attachable": {
            "description": {
                "identifier": model.bedrock_identifier,
                "materials": {
                    "default": "entity_alphatest",
                    "enchanted": "entity_alphatest_glint",
                },
                "textures": {
                    "default": standby_tex_rel,
                    "crossbow_pulling_0": pull0_tex_rel,
                    "crossbow_pulling_1": pull1_tex_rel,
                    "crossbow_pulling_2": pull2_tex_rel,
                    "crossbow_arrow": arrow_tex_rel or standby_tex_rel,
                    "crossbow_rocket": rocket_tex_rel or standby_tex_rel,
                    "enchanted": "textures/misc/enchanted_item_glint",
                },
                "geometry": {
                    "default": standby_geo or "geometry.crossbow_standby",
                    "crossbow_pulling_0": pull0_geo or "geometry.crossbow_pulling_0",
                    "crossbow_pulling_1": pull1_geo or "geometry.crossbow_pulling_1",
                    "crossbow_pulling_2": pull2_geo or "geometry.crossbow_pulling_2",
                    "crossbow_arrow": arrow_geo or "geometry.crossbow_arrow",
                    "crossbow_rocket": rocket_geo or "geometry.crossbow_rocket",
                },
                "animations": {
                    "wield": "animation.crossbow.wield",
                    "wield_first_person_pull": "animation.crossbow.wield_first_person_pull",
                },
                "scripts": {
                    "pre_animation": [
                        "variable.charge_amount = math.clamp((query.main_hand_item_max_duration - (query.main_hand_item_use_duration - query.frame_alpha + 1.0)) / 10.0, 0.0, 1.0f);",
                    ],
                    "animate": [
                        "wield",
                        {
                            "wield_first_person_pull": "query.main_hand_item_use_duration > 0.0f && c.is_first_person",
                        },
                    ],
                },
                "render_controllers": [
                    "controller.render.crossbow",
                ],
            },
        },
    }
