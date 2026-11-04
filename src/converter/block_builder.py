"""Converter for Custom Blocks -> Bedrock blocks.json, terrain_texture.json, 3D Block Geometry & Geyser Block Mappings."""

from typing import Any, Dict, List, Optional, Tuple

from ..parser.block_parser import ParsedCustomBlock
from ..parser.item_parser import ParsedJavaModel
from .geometry_builder import build_bedrock_geometry


def build_bedrock_block_geometry(
    block: ParsedCustomBlock,
    tex_width: int = 16,
    tex_height: int = 16,
    uv_offsets: Optional[Dict[str, Tuple[int, int, int, int]]] = None,
) -> Dict[str, Any]:
    """Build a Bedrock 1.16.0 Block Geometry (.geo.json) from a non-cube ParsedCustomBlock."""
    temp_model = ParsedJavaModel(
        model_id=block.model_id,
        java_base_item=block.base_block,
        bedrock_identifier=block.bedrock_identifier,
        short_name=f"block_{block.short_name}",
        is_3d=True,
        textures=block.textures,
        elements=block.elements,
    )
    geo_doc = build_bedrock_geometry(
        temp_model,
        tex_width=tex_width,
        tex_height=tex_height,
        uv_offsets=uv_offsets,
    )
    # Remove item slot binding on root bone for block geometry
    bones = geo_doc["minecraft:geometry"][0]["bones"]
    if bones and "binding" in bones[0]:
        del bones[0]["binding"]
    return geo_doc


def build_bedrock_blocks_json(blocks: List[ParsedCustomBlock]) -> Dict[str, Any]:
    """Generate Bedrock root blocks.json mapping custom block identifiers to terrain textures/sound."""
    doc: Dict[str, Any] = {
        "format_version": [1, 21, 0],
    }
    for blk in blocks:
        tex_key = f"j2b_block_{blk.short_name}"
        doc[blk.bedrock_identifier] = {
            "textures": tex_key,
            "sound": "stone",
        }
    return doc


def build_geyser_block_mappings_v1(blocks: List[ParsedCustomBlock]) -> Dict[str, Any]:
    """Generate Geyser 2.11+ custom_mappings/blocks.json (BlockMappingsReader_v1 schema)."""
    grouped_by_carrier: Dict[str, List[ParsedCustomBlock]] = {}
    for blk in blocks:
        grouped_by_carrier.setdefault(blk.base_block, []).append(blk)

    blocks_root: Dict[str, Any] = {}
    for base_block, variants in grouped_by_carrier.items():
        carrier_short = base_block.split(":")[-1]
        state_overrides: Dict[str, Any] = {}

        for blk in variants:
            tex_key = f"j2b_block_{blk.short_name}"
            state_entry: Dict[str, Any] = {
                "display_name": blk.short_name.replace("_", " ").title(),
                "place_air": True,
                "material_instances": {
                    "*": {
                        "texture": tex_key,
                        "render_method": "alpha_test" if not blk.is_unit_cube else "opaque",
                        "face_dimming": True,
                        "ambient_occlusion": blk.is_unit_cube,
                    }
                },
            }
            if blk.is_unit_cube:
                state_entry["unit_cube"] = True
            else:
                state_entry["geometry"] = f"geometry.j2b.block_{blk.short_name}"

            rx, ry, rz = blk.rotation_xyz
            if (rx, ry, rz) != (0, 0, 0):
                state_entry["transformation"] = {
                    "rotation": [rx, ry, rz],
                    "scale": [1.0, 1.0, 1.0],
                    "translation": [0.0, 0.0, 0.0],
                }

            clean_pred = blk.state_predicate.strip("[]")
            state_overrides[clean_pred] = state_entry

        blocks_root[base_block] = {
            "name": f"j2b_{carrier_short}",
            "included_in_creative_inventory": False,
            "only_override_states": True,
            "state_overrides": state_overrides,
        }

    return {
        "format_version": 1,
        "blocks": blocks_root,
    }
