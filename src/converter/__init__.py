"""Model & Asset Converters."""

from .armor_builder import (
    build_bedrock_armor_attachable,
    detect_armor_slot,
    resolve_armor_wear_texture,
)
from .attachable_builder import build_bedrock_attachable
from .block_builder import (
    build_bedrock_block_geometry,
    build_bedrock_blocks_json,
    build_geyser_block_mappings_v1,
)
from .furniture_builder import (
    build_bedrock_furniture_entity,
    build_bedrock_furniture_geometry,
    build_furniture_registry,
    build_furniture_render_controller,
)
from .geometry_builder import build_bedrock_geometry
from .math_utils import (
    build_display_animation,
    java_box_to_bedrock_cube,
    java_face_uv_to_bedrock,
    java_pivot_to_bedrock,
    java_rotation_to_bedrock,
)
from .texture_processor import (
    apply_rgb_tint,
    build_model_texture_atlas,
    compose_2d_layered_texture,
)

__all__ = [
    "apply_rgb_tint",
    "build_bedrock_armor_attachable",
    "build_bedrock_attachable",
    "build_bedrock_geometry",
    "build_display_animation",
    "build_model_texture_atlas",
    "compose_2d_layered_texture",
    "detect_armor_slot",
    "java_box_to_bedrock_cube",
    "java_face_uv_to_bedrock",
    "java_pivot_to_bedrock",
    "java_rotation_to_bedrock",
    "resolve_armor_wear_texture",
]
