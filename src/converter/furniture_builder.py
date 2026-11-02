"""Converter for Java ItemDisplay Furniture -> Bedrock Custom Entities & Geyser Extension Registry."""

from typing import Any, Dict, List, Optional, Tuple

from ..parser.block_parser import ParsedFurniture
from ..parser.item_parser import ParsedJavaModel
from .geometry_builder import build_bedrock_geometry


def build_bedrock_furniture_geometry(
    furn: ParsedFurniture,
    tex_width: int = 16,
    tex_height: int = 16,
    uv_offsets: Optional[Dict[str, Tuple[int, int, int, int]]] = None,
) -> Dict[str, Any]:
    """Generate a Bedrock 1.16.0 Entity Geometry (.geo.json) for a Display Furniture model."""
    temp_model = ParsedJavaModel(
        model_id=furn.model_id,
        java_base_item=furn.java_base_item,
        bedrock_identifier=furn.bedrock_entity_id,
        short_name=f"furniture_{furn.short_name}",
        is_3d=True,
        textures=furn.textures,
        elements=furn.elements,
    )
    geo_doc = build_bedrock_geometry(
        temp_model,
        tex_width=tex_width,
        tex_height=tex_height,
        uv_offsets=uv_offsets,
    )
    bones = geo_doc["minecraft:geometry"][0]["bones"]
    if bones and "binding" in bones[0]:
        del bones[0]["binding"]
    return geo_doc


def build_bedrock_furniture_entity(
    furn: ParsedFurniture,
    texture_rel_path: str,
) -> Dict[str, Any]:
    """Generate a Bedrock 1.10.0 Client Entity (.entity.json) for a Display Furniture model."""
    return {
        "format_version": "1.10.0",
        "minecraft:client_entity": {
            "description": {
                "identifier": furn.bedrock_entity_id,
                "materials": {
                    "default": "entity_alphatest",
                },
                "textures": {
                    "default": texture_rel_path,
                },
                "geometry": {
                    "default": f"geometry.j2b.furniture_{furn.short_name}",
                },
                "render_controllers": [
                    "controller.render.j2b.furniture",
                ],
                "spawn_egg": {
                    "base_color": "#8B5A2B",
                    "overlay_color": "#D2B48C",
                },
            }
        },
    }


def build_furniture_render_controller() -> Dict[str, Any]:
    """Generate shared Bedrock render_controllers/furniture.render_controllers.json."""
    return {
        "format_version": "1.8.0",
        "render_controllers": {
            "controller.render.j2b.furniture": {
                "geometry": "Geometry.default",
                "materials": [{"*": "Material.default"}],
                "textures": ["Texture.default"],
            }
        },
    }


def build_furniture_registry(furniture_list: List[ParsedFurniture]) -> Dict[str, Any]:
    """Build custom_mappings/furniture_registry.json consumed by the Geyser Companion Extension."""
    entries: List[Dict[str, Any]] = []
    for furn in furniture_list:
        entries.append(
            {
                "furniture_id": furn.furniture_id,
                "model_id": furn.model_id,
                "bedrock_entity_identifier": furn.bedrock_entity_id,
                "java_base_item": furn.java_base_item,
                "custom_model_data": furn.custom_model_data,
                "hitbox": {
                    "width": furn.hitbox_width,
                    "height": furn.hitbox_height,
                },
                "seat_height": furn.seat_height,
            }
        )
    return {
        "format_version": 1,
        "furniture": entries,
    }
