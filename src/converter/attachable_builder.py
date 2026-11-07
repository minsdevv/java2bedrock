"""Builder for Bedrock Attachables (attachables/*.json)."""

import copy
from typing import Any, Dict, List, Optional
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
    # Accept both off_hand and offhand — Bedrock/Geyser versions differ.
    pre_animation = [
        "v.main_hand = c.item_slot == 'main_hand';",
        "v.off_hand = c.item_slot == 'off_hand' || c.item_slot == 'offhand';",
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
                        # charge_amount drives the pull pose; bow_tex_idx selects pull textures.
                        # Geyser custom bows do NOT advance query.get_animation_frame (vanilla RC),
                        # so arrow-on-string (painted into bow_pulling_* PNGs) never appears unless
                        # we index frames ourselves from use_duration / charge_amount.
                        "variable.charge_amount = math.clamp((query.main_hand_item_max_duration - (query.main_hand_item_use_duration - query.frame_alpha + 1.0)) / 10.0, 0.0, 1.0f);",
                        "variable.bow_tex_idx = query.main_hand_item_use_duration == 0.0f ? 0.0 : math.min(3.0, math.floor(variable.charge_amount / 0.5 + 1.0));",
                    ],
                    "animate": [
                        "wield",
                        {
                            "wield_first_person_pull": "query.main_hand_item_use_duration > 0.0f && c.is_first_person",
                        },
                    ],
                },
                # Unique RC name — do not override vanilla controller.render.bow.
                "render_controllers": [
                    "controller.render.j2b_bow",
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
                        "variable.crossbow_tex_idx = query.main_hand_item_use_duration == 0.0f ? (query.is_item_charged ? 4.0 : 0.0) : math.min(3.0, math.floor(variable.charge_amount / 0.58 + 1.0));",
                    ],
                    "animate": [
                        "wield",
                        {
                            "wield_first_person_pull": "query.main_hand_item_use_duration > 0.0f && c.is_first_person",
                        },
                    ],
                },
                "render_controllers": [
                    "controller.render.j2b_crossbow",
                ],
            },
        },
    }


def build_j2b_bow_render_controller() -> Dict[str, Any]:
    """Shared RC: switch bow pull textures/geos via variable.bow_tex_idx (not get_animation_frame)."""
    return {
        "format_version": "1.10.0",
        "render_controllers": {
            "controller.render.j2b_bow": {
                "arrays": {
                    "textures": {
                        "array.bow_texture_frames": [
                            "texture.default",
                            "texture.bow_pulling_0",
                            "texture.bow_pulling_1",
                            "texture.bow_pulling_2",
                        ]
                    },
                    "geometries": {
                        "array.bow_geo_frames": [
                            "geometry.default",
                            "geometry.bow_pulling_0",
                            "geometry.bow_pulling_1",
                            "geometry.bow_pulling_2",
                        ]
                    },
                },
                "geometry": "array.bow_geo_frames[variable.bow_tex_idx]",
                "materials": [
                    {"*": "variable.is_enchanted ? material.enchanted : material.default"}
                ],
                "textures": [
                    "array.bow_texture_frames[variable.bow_tex_idx]",
                    "texture.enchanted",
                ],
            }
        },
    }


def build_j2b_crossbow_render_controller() -> Dict[str, Any]:
    """Shared RC for crossbow pull / charged frames via variable.crossbow_tex_idx."""
    return {
        "format_version": "1.10.0",
        "render_controllers": {
            "controller.render.j2b_crossbow": {
                "arrays": {
                    "textures": {
                        "array.crossbow_texture_frames": [
                            "texture.default",
                            "texture.crossbow_pulling_0",
                            "texture.crossbow_pulling_1",
                            "texture.crossbow_pulling_2",
                            "texture.crossbow_arrow",
                            "texture.crossbow_rocket",
                        ]
                    },
                    "geometries": {
                        "array.crossbow_geo_frames": [
                            "geometry.default",
                            "geometry.crossbow_pulling_0",
                            "geometry.crossbow_pulling_1",
                            "geometry.crossbow_pulling_2",
                            "geometry.crossbow_arrow",
                            "geometry.crossbow_rocket",
                        ]
                    },
                },
                "geometry": "array.crossbow_geo_frames[variable.crossbow_tex_idx]",
                "materials": [
                    {"*": "variable.is_enchanted ? material.enchanted : material.default"}
                ],
                "textures": [
                    "array.crossbow_texture_frames[variable.crossbow_tex_idx]",
                    "texture.enchanted",
                ],
            }
        },
    }


def build_bedrock_trident_attachable(
    model: ParsedJavaModel,
    standby_tex_rel: str,
    throwing_tex_rel: str,
    animation_map: Dict[str, str],
    standby_geo: Optional[str] = None,
    throwing_geo: Optional[str] = None,
    default_material: str = "entity_alphatest",
) -> Dict[str, Any]:
    """Build a Bedrock 1.10.0 attachable for a Trident supporting held & throwing states."""
    sb_geo = standby_geo or f"geometry.j2b.{model.short_name}"
    th_geo = throwing_geo or sb_geo

    pre_animation = [
        "v.main_hand = c.item_slot == 'main_hand';",
        "v.off_hand = c.item_slot == 'off_hand' || c.item_slot == 'offhand';",
        "v.head = c.item_slot == 'head';",
        "v.is_throwing = query.main_hand_item_use_duration > 0.0f || query.is_using_item;",
        "variable.trident_tex_idx = v.is_throwing ? 1.0 : 0.0;",
    ]
    animate_list = [
        {"third_person": "v.main_hand && !c.is_first_person && !v.is_throwing"},
        {"third_person_throw": "v.main_hand && !c.is_first_person && v.is_throwing"},
        {"third_person_left": "v.off_hand && !c.is_first_person"},
        {"head": "v.head && !c.is_first_person"},
        {"first_person": "v.main_hand && c.is_first_person && !v.is_throwing"},
        {"first_person_throw": "v.main_hand && c.is_first_person && v.is_throwing"},
        {"first_person_left": "v.off_hand && c.is_first_person"},
        {"first_person_head": "v.head && c.is_first_person"},
    ]
    anim_map = dict(animation_map)
    anim_map["first_person_head"] = anim_map.get("disable", "animation.j2b.disable")
    anim_map.pop("disable", None)

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
                    "default": standby_tex_rel,
                    "trident_throwing": throwing_tex_rel,
                    "enchanted": "textures/misc/enchanted_item_glint",
                },
                "geometry": {
                    "default": sb_geo,
                    "trident_throwing": th_geo,
                },
                "animations": anim_map,
                "scripts": {
                    "pre_animation": pre_animation,
                    "animate": animate_list,
                },
                "render_controllers": [
                    "controller.render.j2b_trident",
                ],
            },
        },
    }


def build_j2b_trident_render_controller() -> Dict[str, Any]:
    """Shared RC for switching trident standby vs throwing textures/geometries."""
    return {
        "format_version": "1.10.0",
        "render_controllers": {
            "controller.render.j2b_trident": {
                "arrays": {
                    "textures": {
                        "array.trident_texture_frames": [
                            "texture.default",
                            "texture.trident_throwing",
                        ]
                    },
                    "geometries": {
                        "array.trident_geo_frames": [
                            "geometry.default",
                            "geometry.trident_throwing",
                        ]
                    },
                },
                "geometry": "array.trident_geo_frames[variable.trident_tex_idx]",
                "materials": [
                    {"*": "variable.is_enchanted ? material.enchanted : material.default"}
                ],
                "textures": [
                    "array.trident_texture_frames[variable.trident_tex_idx]",
                    "texture.enchanted",
                ],
            }
        },
    }


def build_thrown_trident_geometry(
    base_geo_doc: Dict[str, Any],
    geo_id: str = "geometry.trident",
) -> Dict[str, Any]:
    """Wrap an item 3D geometry under Bedrock's 'pole' bone so animation.trident.move works in-flight."""
    doc = copy.deepcopy(base_geo_doc)
    geos = doc.get("minecraft:geometry", [])
    if not geos:
        return doc
    geo = geos[0]
    geo["description"]["identifier"] = geo_id
    bones = geo.get("bones", [])
    for b in bones:
        b.pop("binding", None)
        if b.get("name") == "root_item":
            b["parent"] = "pole"
            b["pivot"] = [0.0, 24.0, 0.0]
            # Vanilla thrown_trident pole points downward along -Y before animation.trident.move flips it
            b["rotation"] = [180.0, 0.0, 0.0]
    pole_bone = {
        "name": "pole",
        "pivot": [0.0, 24.0, 0.0],
    }
    geo["bones"] = [pole_bone] + bones
    return doc


def build_thrown_trident_entity(
    entity_id: str,
    texture_rel_path: str,
    geo_id: str = "geometry.trident",
) -> Dict[str, Any]:
    """Build a Bedrock client_entity definition for a thrown trident projectile."""
    return {
        "format_version": "1.10.0",
        "minecraft:client_entity": {
            "description": {
                "identifier": entity_id,
                "materials": {
                    "default": "entity_alphatest",
                    "enchanted": "entity_alphatest_glint",
                },
                "textures": {
                    "default": texture_rel_path,
                    "enchanted": "textures/misc/enchanted_item_glint",
                },
                "geometry": {
                    "default": geo_id,
                },
                "animations": {
                    "move": "animation.trident.move",
                },
                "scripts": {
                    "animate": [
                        "move",
                    ]
                },
                "render_controllers": [
                    "controller.render.item_default",
                ],
            }
        },
    }


def build_trident_registry(models: List[ParsedJavaModel], bedrock_ns: str = "j2b") -> Dict[str, Any]:
    """Build trident_registry.json for the Geyser Companion Extension to map thrown trident projectiles."""
    entries: List[Dict[str, Any]] = []
    for m in models:
        entries.append(
            {
                "short_name": m.short_name,
                "model_id": m.model_id,
                "java_base_item": m.java_base_item,
                "custom_model_data": m.custom_model_data_int,
                "bedrock_item_identifier": m.bedrock_identifier,
                "bedrock_entity_identifier": f"{bedrock_ns}:thrown_{m.short_name}",
            }
        )
    return {
        "format_version": 1,
        "tridents": entries,
    }
