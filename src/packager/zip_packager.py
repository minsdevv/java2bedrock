"""Bedrock Resource Pack (.mcpack) Builder & Packager."""

from dataclasses import dataclass, field
import json
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional, Tuple
import uuid
import zipfile

from PIL import Image

from ..converter.armor_builder import (
    build_bedrock_armor_attachable,
    detect_armor_slot,
    resolve_armor_wear_texture,
)
from ..converter.attachable_builder import build_bedrock_attachable
from ..converter.block_builder import (
    build_bedrock_block_geometry,
    build_bedrock_blocks_json,
    build_geyser_block_mappings_v1,
)
from ..converter.font_builder import convert_java_bitmap_fonts
from ..converter.furniture_builder import (
    build_bedrock_furniture_entity,
    build_bedrock_furniture_geometry,
    build_furniture_registry,
    build_furniture_render_controller,
)
from ..converter.geometry_builder import build_bedrock_geometry
from ..converter.math_utils import build_display_animation
from ..converter.mob_builder import (
    build_bedrock_mob_animation_controller,
    build_bedrock_mob_animations,
    build_bedrock_mob_entity,
    build_bedrock_mob_geometry,
    build_mob_registry,
)
from ..converter.texture_processor import (
    build_model_texture_atlas,
    compose_2d_layered_texture,
)
from ..mappings.geyser_mappings import (
    build_geyser_item_mappings_v1,
    build_geyser_item_mappings_v2,
)
from ..parser.bbmodel_parser import parse_java_pack_bbmodels
from ..parser.block_parser import (
    parse_java_pack_blocks,
    parse_java_pack_furniture,
)
from ..parser.item_parser import (
    ParsedJavaModel,
    parse_java_pack_items,
    resolve_texture_path,
)
from ..parser.pack_meta import PackMetadata, parse_pack_meta


NAMESPACE_J2B = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


@dataclass
class ConversionResult:
    """Summary of a completed Java-to-Bedrock conversion run."""

    pack_meta: PackMetadata
    bedrock_pack_dir: Path
    mcpack_path: Path
    mappings_v2_path: Path
    mappings_v1_path: Path
    total_items: int
    items_3d: int
    items_2d: int
    total_blocks: int = 0
    total_furniture: int = 0
    total_mobs: int = 0
    total_font_glyphs: int = 0
    block_mappings_path: Optional[Path] = None
    furniture_registry_path: Optional[Path] = None
    mob_registry_path: Optional[Path] = None
    warnings: List[str] = field(default_factory=list)


def build_bedrock_manifest(name: str, description: str) -> Dict[str, Any]:
    """Generate a Bedrock format_version 2 manifest.json with deterministic UUIDs."""
    header_uuid = str(uuid.uuid5(NAMESPACE_J2B, f"header:{name}:{description}"))
    module_uuid = str(uuid.uuid5(NAMESPACE_J2B, f"module:{name}:{description}"))

    return {
        "format_version": 2,
        "header": {
            "name": name,
            "description": description,
            "uuid": header_uuid,
            "version": [1, 0, 0],
            "min_engine_version": [1, 21, 0],
        },
        "modules": [
            {
                "type": "resources",
                "description": f"{name} Bedrock Resources",
                "uuid": module_uuid,
                "version": [1, 0, 0],
            }
        ],
    }


def _select_primary_texture(
    pack_root: Path,
    model: ParsedJavaModel,
) -> Optional[Path]:
    """Find the primary PNG file for a model."""
    preferred_keys = ["layer0", "0", "texture", "particle", "all"]
    for key in preferred_keys:
        if key in model.textures:
            p = resolve_texture_path(pack_root, model.textures[key])
            if p:
                return p
    for val in model.textures.values():
        p = resolve_texture_path(pack_root, val)
        if p:
            return p
    return None


def _get_image_size(img_path: Path) -> Tuple[int, int]:
    try:
        with Image.open(img_path) as im:
            return im.width, im.height
    except Exception:
        return 16, 16


def convert_java_pack(
    input_path: Path,
    output_dir: Path,
    pack_name: Optional[str] = None,
    bedrock_ns: str = "j2b",
) -> ConversionResult:
    """Convert a Java Resource Pack (directory or .zip) into a Bedrock .mcpack + Geyser mappings."""
    input_path = Path(input_path).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    temp_extract_dir: Optional[Path] = None
    if input_path.is_file() and input_path.suffix.lower() == ".zip":
        temp_extract_dir = output_dir / "_tmp_java_extract"
        if temp_extract_dir.exists():
            shutil.rmtree(temp_extract_dir)
        temp_extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(input_path, "r") as zf:
            zf.extractall(temp_extract_dir)
        # Handle single nested folder inside zip if pack.mcmeta is inside a subfolder
        if not (temp_extract_dir / "assets").is_dir():
            subdirs = [d for d in temp_extract_dir.iterdir() if d.is_dir()]
            if len(subdirs) == 1 and (subdirs[0] / "assets").is_dir():
                pack_root = subdirs[0]
            else:
                pack_root = temp_extract_dir
        else:
            pack_root = temp_extract_dir
    else:
        pack_root = input_path

    try:
        meta = parse_pack_meta(pack_root, fallback_name=pack_name or input_path.stem)
        if pack_name:
            meta.name = pack_name

        bedrock_dir = output_dir / f"{meta.name}_bedrock"
        if bedrock_dir.exists():
            shutil.rmtree(bedrock_dir)
        bedrock_dir.mkdir(parents=True, exist_ok=True)

        # Copy pack.png -> pack_icon.png if available
        pack_png = pack_root / "pack.png"
        if pack_png.is_file():
            shutil.copy2(pack_png, bedrock_dir / "pack_icon.png")

        models = parse_java_pack_items(pack_root, bedrock_ns=bedrock_ns)
        warnings: List[str] = []
        item_texture_atlas: Dict[str, Any] = {}
        count_3d = 0
        count_2d = 0

        for model in models:
            tex_rel_no_ext = f"textures/items/{bedrock_ns}/{model.short_name}"
            tex_dest = bedrock_dir / f"{tex_rel_no_ext}.png"
            tex_dest.parent.mkdir(parents=True, exist_ok=True)

            if model.is_3d:
                count_3d += 1
                atlas_img, tex_w, tex_h, uv_offsets = build_model_texture_atlas(pack_root, model)
                if atlas_img is not None:
                    atlas_img.save(tex_dest)
                else:
                    warnings.append(f"Missing texture for 3D model '{model.model_id}', generated placeholder.")
                    img = Image.new("RGBA", (16, 16), (255, 0, 255, 255))
                    img.save(tex_dest)
                    tex_w, tex_h = 16, 16
                    uv_offsets = {}

                geo_doc = build_bedrock_geometry(
                    model, tex_width=tex_w, tex_height=tex_h, uv_offsets=uv_offsets
                )
                geo_path = bedrock_dir / "models" / "entity" / bedrock_ns / f"{model.short_name}.geo.json"
                geo_path.parent.mkdir(parents=True, exist_ok=True)
                geo_path.write_text(json.dumps(geo_doc, indent=2), encoding="utf-8")

                anim_doc, anim_map = build_display_animation(model.short_name, model.display)
                anim_path = bedrock_dir / "animations" / bedrock_ns / f"{model.short_name}.animation.json"
                anim_path.parent.mkdir(parents=True, exist_ok=True)
                anim_path.write_text(json.dumps(anim_doc, indent=2), encoding="utf-8")

                attach_doc = build_bedrock_attachable(model, tex_rel_no_ext, anim_map)
                attach_path = bedrock_dir / "attachables" / bedrock_ns / f"{model.short_name}.json"
                attach_path.parent.mkdir(parents=True, exist_ok=True)
                attach_path.write_text(json.dumps(attach_doc, indent=2), encoding="utf-8")
            else:
                count_2d += 1
                composed_img = compose_2d_layered_texture(pack_root, model)
                if composed_img is not None:
                    composed_img.save(tex_dest)
                else:
                    tex_src = _select_primary_texture(pack_root, model)
                    if tex_src and tex_src.is_file():
                        shutil.copy2(tex_src, tex_dest)
                    else:
                        warnings.append(f"Missing texture for model '{model.model_id}', generated placeholder.")
                        img = Image.new("RGBA", (16, 16), (255, 0, 255, 255))
                        img.save(tex_dest)

                # Check if this 2D item is a custom armor piece / equipment
                armor_slot = detect_armor_slot(model)
                if armor_slot:
                    wear_tex_src = resolve_armor_wear_texture(pack_root, model, armor_slot)
                    if wear_tex_src and wear_tex_src.is_file():
                        armor_tex_rel = f"textures/models/armor/{bedrock_ns}_{model.short_name}"
                        armor_tex_dest = bedrock_dir / f"{armor_tex_rel}.png"
                        armor_tex_dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(wear_tex_src, armor_tex_dest)

                        armor_attach_doc = build_bedrock_armor_attachable(
                            model, armor_slot, armor_tex_rel
                        )
                        attach_path = bedrock_dir / "attachables" / bedrock_ns / f"{model.short_name}.json"
                        attach_path.parent.mkdir(parents=True, exist_ok=True)
                        attach_path.write_text(
                            json.dumps(armor_attach_doc, indent=2), encoding="utf-8"
                        )

            icon_key = f"j2b_{model.short_name}"
            item_texture_atlas[icon_key] = {
                "textures": tex_rel_no_ext,
            }

        # --- Phase 3A: Custom Blocks ---
        custom_blocks = parse_java_pack_blocks(pack_root, bedrock_ns=bedrock_ns)
        terrain_texture_atlas: Dict[str, Any] = {}
        for blk in custom_blocks:
            blk_tex_rel = f"textures/blocks/{bedrock_ns}/{blk.short_name}"
            blk_tex_dest = bedrock_dir / f"{blk_tex_rel}.png"
            blk_tex_dest.parent.mkdir(parents=True, exist_ok=True)

            temp_blk_model = ParsedJavaModel(
                model_id=blk.model_id,
                java_base_item=blk.base_block,
                bedrock_identifier=blk.bedrock_identifier,
                short_name=blk.short_name,
                is_3d=not blk.is_unit_cube,
                textures=blk.textures,
                elements=blk.elements,
            )
            atlas_img, tex_w, tex_h, uv_offsets = build_model_texture_atlas(
                pack_root, temp_blk_model
            )
            if atlas_img is not None:
                atlas_img.save(blk_tex_dest)
            else:
                img = Image.new("RGBA", (16, 16), (255, 0, 255, 255))
                img.save(blk_tex_dest)
                tex_w, tex_h = 16, 16
                uv_offsets = {}

            terrain_key = f"j2b_block_{blk.short_name}"
            terrain_texture_atlas[terrain_key] = {
                "textures": blk_tex_rel,
            }

            if not blk.is_unit_cube:
                blk_geo = build_bedrock_block_geometry(
                    blk, tex_width=tex_w, tex_height=tex_h, uv_offsets=uv_offsets
                )
                blk_geo_path = (
                    bedrock_dir
                    / "models"
                    / "blocks"
                    / bedrock_ns
                    / f"{blk.short_name}.geo.json"
                )
                blk_geo_path.parent.mkdir(parents=True, exist_ok=True)
                blk_geo_path.write_text(
                    json.dumps(blk_geo, indent=2), encoding="utf-8"
                )

        if custom_blocks:
            blocks_json_doc = build_bedrock_blocks_json(custom_blocks)
            (bedrock_dir / "blocks.json").write_text(
                json.dumps(blocks_json_doc, indent=2), encoding="utf-8"
            )
            terrain_tex_doc = {
                "resource_pack_name": meta.name,
                "texture_name": "atlas.terrain",
                "padding": 8,
                "num_mip_levels": 4,
                "texture_data": terrain_texture_atlas,
            }
            terrain_tex_path = bedrock_dir / "textures" / "terrain_texture.json"
            terrain_tex_path.parent.mkdir(parents=True, exist_ok=True)
            terrain_tex_path.write_text(
                json.dumps(terrain_tex_doc, indent=2), encoding="utf-8"
            )

        # --- Phase 3B: Display Furniture ---
        furniture_list = parse_java_pack_furniture(pack_root, bedrock_ns=bedrock_ns)
        for furn in furniture_list:
            furn_tex_rel = f"textures/entity/furniture/{bedrock_ns}/{furn.short_name}"
            furn_tex_dest = bedrock_dir / f"{furn_tex_rel}.png"
            furn_tex_dest.parent.mkdir(parents=True, exist_ok=True)

            temp_furn_model = ParsedJavaModel(
                model_id=furn.model_id,
                java_base_item=furn.java_base_item,
                bedrock_identifier=furn.bedrock_entity_id,
                short_name=furn.short_name,
                is_3d=True,
                textures=furn.textures,
                elements=furn.elements,
            )
            atlas_img, tex_w, tex_h, uv_offsets = build_model_texture_atlas(
                pack_root, temp_furn_model
            )
            if atlas_img is not None:
                atlas_img.save(furn_tex_dest)
            else:
                img = Image.new("RGBA", (16, 16), (255, 0, 255, 255))
                img.save(furn_tex_dest)
                tex_w, tex_h = 16, 16
                uv_offsets = {}

            furn_geo = build_bedrock_furniture_geometry(
                furn, tex_width=tex_w, tex_height=tex_h, uv_offsets=uv_offsets
            )
            furn_geo_path = (
                bedrock_dir
                / "models"
                / "entity"
                / "furniture"
                / f"{furn.short_name}.geo.json"
            )
            furn_geo_path.parent.mkdir(parents=True, exist_ok=True)
            furn_geo_path.write_text(json.dumps(furn_geo, indent=2), encoding="utf-8")

            furn_entity_doc = build_bedrock_furniture_entity(furn, furn_tex_rel)
            furn_ent_path = (
                bedrock_dir
                / "entity"
                / "furniture"
                / f"{furn.short_name}.entity.json"
            )
            furn_ent_path.parent.mkdir(parents=True, exist_ok=True)
            furn_ent_path.write_text(
                json.dumps(furn_entity_doc, indent=2), encoding="utf-8"
            )

        # --- Phase 4: Custom Mobs (.bbmodel) ---
        mob_list = parse_java_pack_bbmodels(pack_root, bedrock_ns=bedrock_ns)
        for mob in mob_list:
            mob_tex_rel = f"textures/entity/mobs/{bedrock_ns}/{mob.mob_name}"
            mob_tex_dest = bedrock_dir / f"{mob_tex_rel}.png"
            mob_tex_dest.parent.mkdir(parents=True, exist_ok=True)
            if mob.texture_image is not None:
                mob.texture_image.save(mob_tex_dest)
            else:
                img = Image.new("RGBA", (mob.tex_width, mob.tex_height), (255, 0, 255, 255))
                img.save(mob_tex_dest)

            mob_geo = build_bedrock_mob_geometry(mob)
            mob_geo_path = (
                bedrock_dir
                / "models"
                / "entity"
                / "mobs"
                / f"{mob.mob_name}.geo.json"
            )
            mob_geo_path.parent.mkdir(parents=True, exist_ok=True)
            mob_geo_path.write_text(json.dumps(mob_geo, indent=2), encoding="utf-8")

            mob_anim = build_bedrock_mob_animations(mob)
            mob_anim_path = (
                bedrock_dir
                / "animations"
                / "mobs"
                / f"{mob.mob_name}.animation.json"
            )
            mob_anim_path.parent.mkdir(parents=True, exist_ok=True)
            mob_anim_path.write_text(json.dumps(mob_anim, indent=2), encoding="utf-8")

            mob_ctrl = build_bedrock_mob_animation_controller(mob)
            mob_ctrl_path = (
                bedrock_dir
                / "animation_controllers"
                / "mobs"
                / f"{mob.mob_name}.animation_controllers.json"
            )
            mob_ctrl_path.parent.mkdir(parents=True, exist_ok=True)
            mob_ctrl_path.write_text(json.dumps(mob_ctrl, indent=2), encoding="utf-8")

            mob_ent = build_bedrock_mob_entity(mob, mob_tex_rel)
            mob_ent_path = (
                bedrock_dir
                / "entity"
                / "mobs"
                / f"{mob.mob_name}.entity.json"
            )
            mob_ent_path.parent.mkdir(parents=True, exist_ok=True)
            mob_ent_path.write_text(json.dumps(mob_ent, indent=2), encoding="utf-8")

        if furniture_list or mob_list:
            rc_path = (
                bedrock_dir
                / "render_controllers"
                / "furniture.render_controllers.json"
            )
            rc_path.parent.mkdir(parents=True, exist_ok=True)
            rc_path.write_text(
                json.dumps(build_furniture_render_controller(), indent=2),
                encoding="utf-8",
            )

        # --- Custom Font Bitmap Glyphs (font/glyph_XX.png) ---
        total_font_glyphs = convert_java_bitmap_fonts(pack_root, bedrock_dir)

        # Write manifest.json
        manifest_doc = build_bedrock_manifest(meta.name, meta.description)
        (bedrock_dir / "manifest.json").write_text(
            json.dumps(manifest_doc, indent=2), encoding="utf-8"
        )

        # Write textures/item_texture.json
        item_tex_doc = {
            "resource_pack_name": meta.name,
            "texture_name": "atlas.items",
            "texture_data": item_texture_atlas,
        }
        item_tex_path = bedrock_dir / "textures" / "item_texture.json"
        item_tex_path.parent.mkdir(parents=True, exist_ok=True)
        item_tex_path.write_text(json.dumps(item_tex_doc, indent=2), encoding="utf-8")

        # Write Geyser Custom Mappings (v2, v1, blocks, furniture_registry, mob_registry)
        mappings_dir = output_dir / "custom_mappings"
        mappings_dir.mkdir(parents=True, exist_ok=True)

        mappings_v2 = build_geyser_item_mappings_v2(models)
        mappings_v2_path = mappings_dir / "items_v2.json"
        mappings_v2_path.write_text(json.dumps(mappings_v2, indent=2), encoding="utf-8")

        mappings_v1 = build_geyser_item_mappings_v1(models)
        mappings_v1_path = mappings_dir / "items_v1.json"
        mappings_v1_path.write_text(json.dumps(mappings_v1, indent=2), encoding="utf-8")

        block_mappings_path: Optional[Path] = None
        if custom_blocks:
            block_mappings_doc = build_geyser_block_mappings_v1(custom_blocks)
            block_mappings_path = mappings_dir / "blocks.json"
            block_mappings_path.write_text(
                json.dumps(block_mappings_doc, indent=2), encoding="utf-8"
            )

        furniture_registry_path: Optional[Path] = None
        if furniture_list:
            furn_reg_doc = build_furniture_registry(furniture_list)
            furniture_registry_path = mappings_dir / "furniture_registry.json"
            furniture_registry_path.write_text(
                json.dumps(furn_reg_doc, indent=2), encoding="utf-8"
            )

        mob_registry_path: Optional[Path] = None
        if mob_list:
            mob_reg_doc = build_mob_registry(mob_list)
            mob_registry_path = mappings_dir / "mob_registry.json"
            mob_registry_path.write_text(
                json.dumps(mob_reg_doc, indent=2), encoding="utf-8"
            )

        # Package .mcpack
        mcpack_path = output_dir / f"{meta.name}.mcpack"
        with zipfile.ZipFile(mcpack_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file_path in sorted(bedrock_dir.rglob("*")):
                if file_path.is_file():
                    arcname = file_path.relative_to(bedrock_dir).as_posix()
                    zf.write(file_path, arcname)

        return ConversionResult(
            pack_meta=meta,
            bedrock_pack_dir=bedrock_dir,
            mcpack_path=mcpack_path,
            mappings_v2_path=mappings_v2_path,
            mappings_v1_path=mappings_v1_path,
            total_items=len(models),
            items_3d=count_3d,
            items_2d=count_2d,
            total_blocks=len(custom_blocks),
            total_furniture=len(furniture_list),
            total_mobs=len(mob_list),
            total_font_glyphs=total_font_glyphs,
            block_mappings_path=block_mappings_path,
            furniture_registry_path=furniture_registry_path,
            mob_registry_path=mob_registry_path,
            warnings=warnings,
        )
    finally:
        if temp_extract_dir and temp_extract_dir.exists():
            shutil.rmtree(temp_extract_dir, ignore_errors=True)
