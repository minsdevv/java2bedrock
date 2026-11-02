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
from ..converter.geometry_builder import build_bedrock_geometry
from ..converter.math_utils import build_display_animation
from ..converter.texture_processor import (
    build_model_texture_atlas,
    compose_2d_layered_texture,
)
from ..mappings.geyser_mappings import (
    build_geyser_item_mappings_v1,
    build_geyser_item_mappings_v2,
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

        # Write Geyser Custom Mappings (v2 and v1)
        mappings_dir = output_dir / "custom_mappings"
        mappings_dir.mkdir(parents=True, exist_ok=True)

        mappings_v2 = build_geyser_item_mappings_v2(models)
        mappings_v2_path = mappings_dir / "items_v2.json"
        mappings_v2_path.write_text(json.dumps(mappings_v2, indent=2), encoding="utf-8")

        mappings_v1 = build_geyser_item_mappings_v1(models)
        mappings_v1_path = mappings_dir / "items_v1.json"
        mappings_v1_path.write_text(json.dumps(mappings_v1, indent=2), encoding="utf-8")

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
            warnings=warnings,
        )
    finally:
        if temp_extract_dir and temp_extract_dir.exists():
            shutil.rmtree(temp_extract_dir, ignore_errors=True)
