"""Bedrock Resource Pack (.mcpack) Builder & Packager."""

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import shutil
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid
import zipfile

from PIL import Image

from ..converter.armor_builder import (
    STANDARD_PLAYER_ARMOR_GEO_DOC,
    build_bedrock_armor_attachable,
    detect_armor_slot,
    process_bedrock_armor_texture,
    resolve_armor_wear_texture,
)
from ..converter.attachable_builder import (
    build_bedrock_attachable,
    build_bedrock_bow_attachable,
    build_bedrock_crossbow_attachable,
)
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
from ..converter.sound_converter import convert_java_pack_sounds
from ..converter.texture_processor import (
    build_model_texture_atlas,
    compose_2d_layered_texture,
    render_model_isometric,
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
from ..report import AssetStatus, ConversionReport
from ..converter.flipbook_builder import build_flipbook_entry, parse_mcmeta_animation


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
    total_sounds: int = 0
    block_mappings_path: Optional[Path] = None
    furniture_registry_path: Optional[Path] = None
    mob_registry_path: Optional[Path] = None
    warnings: List[str] = field(default_factory=list)
    report: Optional[ConversionReport] = None


def _deep_merge_dict(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge override dictionary into base dictionary."""
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge_dict(base[k], v)
        else:
            base[k] = v
    return base


def merge_bedrock_overlay(overlay_path: Union[str, Path], target_dir: Path) -> List[str]:
    """Merge a user-provided Bedrock pack (folder, .mcpack, or .zip) into the target bedrock pack directory."""
    overlay_path = Path(overlay_path)
    warnings: List[str] = []
    if not overlay_path.exists():
        warnings.append(f"Bedrock overlay path does not exist: {overlay_path}")
        return warnings

    temp_dir: Optional[Path] = None
    if overlay_path.is_file() and overlay_path.suffix.lower() in (".zip", ".mcpack"):
        temp_dir = target_dir / "_tmp_overlay"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(overlay_path, "r") as zf:
                zf.extractall(temp_dir)
            source_root = temp_dir
        except Exception as e:
            warnings.append(f"Failed to extract Bedrock overlay '{overlay_path}': {e}")
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            return warnings
    else:
        source_root = overlay_path

    try:
        for src_file in source_root.rglob("*"):
            if not src_file.is_file():
                continue
            rel = src_file.relative_to(source_root)
            rel_str = rel.as_posix()

            # Skip manifest so we preserve generated UUIDs and pack metadata
            if rel_str == "manifest.json":
                continue

            dest_file = target_dir / rel
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            # Known Bedrock JSON atlas/definitions that should be deep-merged rather than completely overwritten
            merge_candidates = (
                "textures/item_texture.json",
                "textures/terrain_texture.json",
                "sounds/sound_definitions.json",
                "blocks.json",
            )
            if rel_str in merge_candidates and dest_file.is_file():
                try:
                    base_json = json.loads(dest_file.read_text(encoding="utf-8"))
                    over_json = json.loads(src_file.read_text(encoding="utf-8"))
                    _deep_merge_dict(base_json, over_json)
                    dest_file.write_text(json.dumps(base_json, indent=2), encoding="utf-8")
                except Exception as e:
                    warnings.append(f"Failed to deep-merge JSON overlay '{rel_str}': {e}")
                    shutil.copy2(src_file, dest_file)
            else:
                shutil.copy2(src_file, dest_file)
    finally:
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

    return warnings


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


def _upscale_icon(path: Path, target: int) -> None:
    """Upscale a square pixel-art icon with NEAREST by an integer factor up to `target` px.

    Non-square images (animation strips) and images already >= target are left untouched.
    """
    if target <= 0 or not path.is_file():
        return
    try:
        with Image.open(path) as im:
            im.load()
            w, h = im.size
            if w != h or w >= target:
                return
            factor = target // w
            if factor < 2:
                return
            up = im.convert("RGBA").resize((w * factor, h * factor), Image.Resampling.NEAREST)
        up.save(path)
    except Exception:
        return


def _find_bow_pull_variants(
    models: List[ParsedJavaModel], standby: ParsedJavaModel
) -> Tuple[Optional[ParsedJavaModel], Optional[ParsedJavaModel], Optional[ParsedJavaModel]]:
    cmd = standby.custom_model_data_int

    def score(cand: ParsedJavaModel) -> int:
        s = 0
        if cmd is not None and cand.custom_model_data_int == cmd:
            s += 10
        sb_tokens = set(re.split(r"[^a-z0-9]+", standby.short_name.lower()))
        cand_tokens = set(re.split(r"[^a-z0-9]+", cand.short_name.lower()))
        s += len(sb_tokens.intersection(cand_tokens))
        return s

    candidates = [
        m for m in models
        if m != standby and (m.java_base_item.endswith("bow") or m.java_base_item.endswith("crossbow"))
        and score(m) >= (11 if cmd is not None else 2)
    ]
    pull0 = next((m for m in candidates if any(p.property_name == "pulling" for p in m.predicates) and not any(p.property_name == "pull" for p in m.predicates)), None)
    pull1 = next((m for m in candidates if any(p.property_name == "pull" and p.threshold is not None and 0.1 <= p.threshold < 0.8 for p in m.predicates)), None)
    pull2 = next((m for m in candidates if any(p.property_name == "pull" and p.threshold is not None and p.threshold >= 0.8 for p in m.predicates)), None)
    return pull0, pull1, pull2


def _find_crossbow_variants(
    models: List[ParsedJavaModel], standby: ParsedJavaModel
) -> Tuple[
    Optional[ParsedJavaModel],
    Optional[ParsedJavaModel],
    Optional[ParsedJavaModel],
    Optional[ParsedJavaModel],
    Optional[ParsedJavaModel],
]:
    cmd = standby.custom_model_data_int

    def score(cand: ParsedJavaModel) -> int:
        s = 0
        if cmd is not None and cand.custom_model_data_int == cmd:
            s += 10
        sb_tokens = set(re.split(r"[^a-z0-9]+", standby.short_name.lower()))
        cand_tokens = set(re.split(r"[^a-z0-9]+", cand.short_name.lower()))
        s += len(sb_tokens.intersection(cand_tokens))
        return s

    candidates = [
        m for m in models
        if m != standby and (m.java_base_item.endswith("crossbow") or m.java_base_item.endswith("bow"))
        and score(m) >= (11 if cmd is not None else 2)
    ]
    pull0 = next((m for m in candidates if any(p.property_name == "pulling" for p in m.predicates) and not any(p.property_name == "pull" for p in m.predicates)), None)
    pull1 = next((m for m in candidates if any(p.property_name == "pull" and p.threshold is not None and 0.1 <= p.threshold < 0.8 for p in m.predicates)), None)
    pull2 = next((m for m in candidates if any(p.property_name == "pull" and p.threshold is not None and p.threshold >= 0.8 for p in m.predicates)), None)
    arrow = next((m for m in candidates if any(p.property_name == "charged" for p in m.predicates) and not any(p.property_name == "firework" for p in m.predicates)), None)
    rocket = next((m for m in candidates if any(p.property_name == "firework" for p in m.predicates)), None)
    return pull0, pull1, pull2, arrow, rocket


def convert_java_pack(
    input_path: Path,
    output_dir: Path,
    pack_name: Optional[str] = None,
    bedrock_ns: str = "j2b",
    bedrock_overlays: Optional[List[Union[str, Path]]] = None,
    filter_gui_font_glyphs: bool = True,
    icon_size: int = 128,
    report_path: Optional[Union[str, Path]] = None,
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
        report = ConversionReport(
            pack={
                "name": meta.name,
                "description": meta.description,
                "pack_format": meta.pack_format,
                "namespaces": meta.namespaces,
            }
        )
        item_texture_atlas: Dict[str, Any] = {}
        flipbook_entries: List[Dict[str, Any]] = []
        count_3d = 0
        count_2d = 0

        # --- Pre-parse Custom Blocks so Phase 2 items can link block_placer ---
        custom_blocks = parse_java_pack_blocks(pack_root, bedrock_ns=bedrock_ns)
        block_lookup = {blk.short_name: blk for blk in custom_blocks}
        block_by_model = {blk.model_id.lstrip('_'): blk for blk in custom_blocks}

        for model in models:
            tex_rel_no_ext = f"textures/items/{bedrock_ns}/{model.short_name}"
            tex_dest = bedrock_dir / f"{tex_rel_no_ext}.png"
            tex_dest.parent.mkdir(parents=True, exist_ok=True)

            if model.is_3d:
                count_3d += 1
                atlas_img, tex_w, tex_h, uv_offsets = build_model_texture_atlas(pack_root, model)

                # Attachable texture path for 3D model entity rendering
                entity_tex_rel = f"textures/models/entity/{bedrock_ns}/{model.short_name}"
                entity_tex_dest = bedrock_dir / f"{entity_tex_rel}.png"
                entity_tex_dest.parent.mkdir(parents=True, exist_ok=True)

                if atlas_img is not None:
                    atlas_img.save(entity_tex_dest)
                else:
                    warnings.append(f"Missing texture for 3D model '{model.model_id}', generated placeholder.")
                    img = Image.new("RGBA", (16, 16), (255, 0, 255, 255))
                    img.save(entity_tex_dest)
                    tex_w, tex_h = 16, 16
                    uv_offsets = {}

                # Render isometric 2D icon for GUI/inventory slot
                iso_icon = render_model_isometric(pack_root, model, size=icon_size)
                iso_icon.save(tex_dest)

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

                attach_doc = build_bedrock_attachable(model, entity_tex_rel, anim_map)
                attach_path = bedrock_dir / "attachables" / bedrock_ns / f"{model.short_name}.json"
                attach_path.parent.mkdir(parents=True, exist_ok=True)
                attach_path.write_text(json.dumps(attach_doc, indent=2), encoding="utf-8")

                if atlas_img is not None:
                    report.add_asset(
                        model.bedrock_identifier,
                        "item",
                        AssetStatus.CONVERTED,
                        outputs=[
                            str(attach_path.relative_to(bedrock_dir)),
                            str(geo_path.relative_to(bedrock_dir)),
                            str(anim_path.relative_to(bedrock_dir)),
                        ],
                    )
                else:
                    report.add_asset(
                        model.bedrock_identifier,
                        "item",
                        AssetStatus.APPROXIMATED,
                        reasons=["missing_texture_placeholder"],
                        outputs=[
                            str(attach_path.relative_to(bedrock_dir)),
                            str(geo_path.relative_to(bedrock_dir)),
                            str(anim_path.relative_to(bedrock_dir)),
                        ],
                    )
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

                if composed_img is not None or (tex_src and tex_src.is_file()):
                    report.add_asset(
                        model.bedrock_identifier,
                        "item",
                        AssetStatus.CONVERTED,
                        outputs=[str(tex_dest.relative_to(bedrock_dir))],
                    )
                else:
                    report.add_asset(
                        model.bedrock_identifier,
                        "item",
                        AssetStatus.APPROXIMATED,
                        reasons=["missing_texture_placeholder"],
                        outputs=[str(tex_dest.relative_to(bedrock_dir))],
                    )

                # Check if this 2D item is a custom armor piece / equipment
                armor_slot = detect_armor_slot(model)
                if armor_slot:
                    wear_tex_src = resolve_armor_wear_texture(pack_root, model, armor_slot)
                    if wear_tex_src and wear_tex_src.is_file():
                        armor_tex_rel = f"textures/models/armor/{bedrock_ns}_{model.short_name}"
                        armor_tex_dest = bedrock_dir / f"{armor_tex_rel}.png"
                        armor_tex_dest.parent.mkdir(parents=True, exist_ok=True)
                        process_bedrock_armor_texture(wear_tex_src, armor_tex_dest, model)

                        armor_attach_doc = build_bedrock_armor_attachable(
                            model, armor_slot, armor_tex_rel
                        )
                        attach_path = bedrock_dir / "attachables" / bedrock_ns / f"{model.short_name}.json"
                        attach_path.parent.mkdir(parents=True, exist_ok=True)
                        attach_path.write_text(
                            json.dumps(armor_attach_doc, indent=2), encoding="utf-8"
                        )
                        report.add_asset(
                            f"{model.bedrock_identifier}:{armor_slot}",
                            "armor",
                            AssetStatus.CONVERTED,
                            outputs=[str(attach_path.relative_to(bedrock_dir))],
                        )

            icon_key = f"j2b_{model.short_name}"
            if not model.is_3d:
                _upscale_icon(tex_dest, icon_size)
                tex_src = _select_primary_texture(pack_root, model)
                if tex_src and tex_src.is_file():
                    mcmeta_p = tex_src.with_name(f"{tex_src.name}.mcmeta")
                    if mcmeta_p.is_file():
                        fb_params = parse_mcmeta_animation(mcmeta_p)
                        if fb_params:
                            flipbook_entries.append(
                                build_flipbook_entry(tex_rel_no_ext, icon_key, fb_params)
                            )
            item_texture_atlas[icon_key] = {
                "textures": tex_rel_no_ext,
            }

            # Generate Bedrock client Item Definition (items/*.json)
            armor_slot = detect_armor_slot(model)
            is_bow = model.java_base_item == "minecraft:bow" or model.java_base_item.endswith(":bow")
            is_crossbow = model.java_base_item == "minecraft:crossbow" or model.java_base_item.endswith(":crossbow")
            is_weapon_or_tool = (
                is_bow or is_crossbow or
                any(kw in model.java_base_item for kw in ("sword", "pickaxe", "axe", "shovel", "hoe", "shield", "trident", "spear"))
            )
            item_def: Dict[str, Any] = {
                "format_version": "1.20.20",
                "minecraft:item": {
                    "description": {
                        "identifier": model.bedrock_identifier,
                        "menu_category": {
                            "category": "equipment" if (armor_slot or is_weapon_or_tool) else "items",
                        },
                    },
                    "components": {
                        "minecraft:icon": {
                            "texture": icon_key,
                        },
                        **({"minecraft:hand_equipped": True} if is_weapon_or_tool else {}),
                    },
                },
            }
            # Link block_placer component if item represents a custom block (enables 3D dropped model)
            matching_blk = block_lookup.get(model.short_name) or block_by_model.get(model.model_id.lstrip('_'))
            if matching_blk:
                item_def["minecraft:item"]["components"]["minecraft:block_placer"] = {
                    "block": matching_blk.bedrock_identifier,
                }

            items_path = bedrock_dir / "items" / bedrock_ns / f"{model.short_name}.json"
            items_path.parent.mkdir(parents=True, exist_ok=True)
            items_path.write_text(json.dumps(item_def, indent=2), encoding="utf-8")

        # --- Generate Specialized Attachables for Bows & Crossbows ---
        for model in models:
            is_bow = model.java_base_item == "minecraft:bow" or model.java_base_item.endswith(":bow")
            is_crossbow = model.java_base_item == "minecraft:crossbow" or model.java_base_item.endswith(":crossbow")
            is_standby = not any(p.property_name in ("pulling", "pull", "charged", "firework") for p in model.predicates)

            if is_bow and is_standby:
                pull0, pull1, pull2 = _find_bow_pull_variants(models, model)
                sb_tex = f"textures/items/{bedrock_ns}/{model.short_name}"
                p0_tex = f"textures/items/{bedrock_ns}/{pull0.short_name}" if pull0 else sb_tex
                p1_tex = f"textures/items/{bedrock_ns}/{pull1.short_name}" if pull1 else sb_tex
                p2_tex = f"textures/items/{bedrock_ns}/{pull2.short_name}" if pull2 else sb_tex
                sb_geo = f"geometry.{bedrock_ns}.{model.short_name}" if model.is_3d else None
                p0_geo = f"geometry.{bedrock_ns}.{pull0.short_name}" if (pull0 and pull0.is_3d) else None
                p1_geo = f"geometry.{bedrock_ns}.{pull1.short_name}" if (pull1 and pull1.is_3d) else None
                p2_geo = f"geometry.{bedrock_ns}.{pull2.short_name}" if (pull2 and pull2.is_3d) else None

                bow_attach_doc = build_bedrock_bow_attachable(
                    model,
                    sb_tex,
                    p0_tex,
                    p1_tex,
                    p2_tex,
                    standby_geo=sb_geo,
                    pull0_geo=p0_geo,
                    pull1_geo=p1_geo,
                    pull2_geo=p2_geo,
                )
                attach_path = bedrock_dir / "attachables" / bedrock_ns / f"{model.short_name}.json"
                attach_path.parent.mkdir(parents=True, exist_ok=True)
                attach_path.write_text(json.dumps(bow_attach_doc, indent=2), encoding="utf-8")
                report.add_asset(
                    f"{model.bedrock_identifier}:bow",
                    "attachable",
                    AssetStatus.CONVERTED,
                    outputs=[str(attach_path.relative_to(bedrock_dir))],
                )
            elif is_crossbow and is_standby:
                pull0, pull1, pull2, arrow, rocket = _find_crossbow_variants(models, model)
                sb_tex = f"textures/items/{bedrock_ns}/{model.short_name}"
                p0_tex = f"textures/items/{bedrock_ns}/{pull0.short_name}" if pull0 else sb_tex
                p1_tex = f"textures/items/{bedrock_ns}/{pull1.short_name}" if pull1 else sb_tex
                p2_tex = f"textures/items/{bedrock_ns}/{pull2.short_name}" if pull2 else sb_tex
                arr_tex = f"textures/items/{bedrock_ns}/{arrow.short_name}" if arrow else sb_tex
                rkt_tex = f"textures/items/{bedrock_ns}/{rocket.short_name}" if rocket else sb_tex
                sb_geo = f"geometry.{bedrock_ns}.{model.short_name}" if model.is_3d else None
                p0_geo = f"geometry.{bedrock_ns}.{pull0.short_name}" if (pull0 and pull0.is_3d) else None
                p1_geo = f"geometry.{bedrock_ns}.{pull1.short_name}" if (pull1 and pull1.is_3d) else None
                p2_geo = f"geometry.{bedrock_ns}.{pull2.short_name}" if (pull2 and pull2.is_3d) else None
                arr_geo = f"geometry.{bedrock_ns}.{arrow.short_name}" if (arrow and arrow.is_3d) else None
                rkt_geo = f"geometry.{bedrock_ns}.{rocket.short_name}" if (rocket and rocket.is_3d) else None

                cb_attach_doc = build_bedrock_crossbow_attachable(
                    model,
                    sb_tex,
                    p0_tex,
                    p1_tex,
                    p2_tex,
                    arrow_tex_rel=arr_tex,
                    rocket_tex_rel=rkt_tex,
                    standby_geo=sb_geo,
                    pull0_geo=p0_geo,
                    pull1_geo=p1_geo,
                    pull2_geo=p2_geo,
                    arrow_geo=arr_geo,
                    rocket_geo=rkt_geo,
                )
                attach_path = bedrock_dir / "attachables" / bedrock_ns / f"{model.short_name}.json"
                attach_path.parent.mkdir(parents=True, exist_ok=True)
                attach_path.write_text(json.dumps(cb_attach_doc, indent=2), encoding="utf-8")
                report.add_asset(
                    f"{model.bedrock_identifier}:crossbow",
                    "attachable",
                    AssetStatus.CONVERTED,
                    outputs=[str(attach_path.relative_to(bedrock_dir))],
                )

        # --- Phase 3A: Custom Blocks ---
        terrain_texture_atlas: Dict[str, Any] = {}
        for blk in custom_blocks:
            blk_tex_rel = f"textures/blocks/{bedrock_ns}/{blk.short_name}"
            blk_tex_dest = bedrock_dir / f"{blk_tex_rel}.png"
            blk_tex_dest.parent.mkdir(parents=True, exist_ok=True)

            # Check if block uses an animated texture with .mcmeta
            blk_mcmeta_p: Optional[Path] = None
            primary_blk_tex: Optional[Path] = None
            if blk.is_unit_cube and blk.textures:
                first_ref = next(iter(blk.textures.values()))
                cand_p = resolve_texture_path(pack_root, first_ref, allow_vanilla_fallback=False)
                if cand_p and cand_p.is_file():
                    cand_meta = cand_p.with_name(f"{cand_p.name}.mcmeta")
                    if cand_meta.is_file():
                        blk_mcmeta_p = cand_meta
                        primary_blk_tex = cand_p

            temp_blk_model = ParsedJavaModel(
                model_id=blk.model_id,
                java_base_item=blk.base_block,
                bedrock_identifier=blk.bedrock_identifier,
                short_name=blk.short_name,
                is_3d=not blk.is_unit_cube,
                textures=blk.textures,
                elements=blk.elements,
            )
            if blk_mcmeta_p and primary_blk_tex:
                shutil.copy2(primary_blk_tex, blk_tex_dest)
                atlas_img = None
                tex_w, tex_h = 16, 16
                uv_offsets = {}
                fb_params = parse_mcmeta_animation(blk_mcmeta_p)
                if fb_params:
                    terrain_key = f"j2b_block_{blk.short_name}"
                    flipbook_entries.append(
                        build_flipbook_entry(blk_tex_rel, terrain_key, fb_params)
                    )
            else:
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
            report.add_asset(
                blk.bedrock_identifier,
                "block",
                AssetStatus.CONVERTED,
                outputs=[str(blk_tex_dest.relative_to(bedrock_dir))],
            )

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
            report.add_asset(
                furn.bedrock_entity_id,
                "furniture",
                AssetStatus.CONVERTED,
                outputs=[str(furn_geo_path.relative_to(bedrock_dir))],
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
            report.add_asset(
                mob.bedrock_entity_id,
                "mob",
                AssetStatus.CONVERTED,
                outputs=[str(mob_geo_path.relative_to(bedrock_dir))],
            )

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

        # --- Custom Sounds (sounds/sound_definitions.json) ---
        total_sounds, sound_warnings = convert_java_pack_sounds(
            pack_root, bedrock_dir, bedrock_ns=bedrock_ns
        )
        warnings.extend(sound_warnings)

        # --- Custom Font Bitmap Glyphs (font/glyph_XX.png) ---
        total_font_glyphs = convert_java_bitmap_fonts(
            pack_root, bedrock_dir, filter_gui_backgrounds=filter_gui_font_glyphs
        )

        # Write models/entity/player_armor.json to provide standard vanilla armor geometries for custom attachables
        player_armor_geo_path = bedrock_dir / "models" / "entity" / "player_armor.json"
        player_armor_geo_path.parent.mkdir(parents=True, exist_ok=True)
        player_armor_geo_path.write_text(
            json.dumps(STANDARD_PLAYER_ARMOR_GEO_DOC, indent=2), encoding="utf-8"
        )

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

        # Write textures/flipbook_textures.json if animated textures exist
        if flipbook_entries:
            fb_path = bedrock_dir / "textures" / "flipbook_textures.json"
            fb_path.parent.mkdir(parents=True, exist_ok=True)
            fb_path.write_text(json.dumps(flipbook_entries, indent=2), encoding="utf-8")

        # --- Merge User Bedrock Overlays (Custom UI, Texts, Title Logo, Splash, etc.) ---
        if bedrock_overlays:
            for overlay_path in bedrock_overlays:
                overlay_warns = merge_bedrock_overlay(overlay_path, bedrock_dir)
                warnings.extend(overlay_warns)

        # Write Geyser Custom Mappings (v2, v1, blocks, furniture_registry, mob_registry)
        mappings_dir = output_dir / "custom_mappings"
        mappings_dir.mkdir(parents=True, exist_ok=True)

        mappings_v2 = build_geyser_item_mappings_v2(models)
        mappings_v2_path = mappings_dir / "items_v2.json"
        mappings_v2_path.write_text(json.dumps(mappings_v2, indent=2), encoding="utf-8")

        mappings_v1 = build_geyser_item_mappings_v1(models)
        mappings_v1_path = mappings_dir / "items_v1_legacy.json.bak"
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

        report.totals = {
            "total_items": count_3d + count_2d,
            "items_3d": count_3d,
            "items_2d": count_2d,
            "total_blocks": len(custom_blocks),
            "total_furniture": len(furniture_list),
            "total_mobs": len(mob_list),
            "total_font_glyphs": total_font_glyphs,
            "total_sounds": total_sounds,
        }
        report.warnings = list(warnings)
        if report_path:
            report.write_json(Path(report_path))

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
            total_sounds=total_sounds,
            block_mappings_path=block_mappings_path,
            furniture_registry_path=furniture_registry_path,
            mob_registry_path=mob_registry_path,
            warnings=warnings,
            report=report,
        )
    finally:
        if temp_extract_dir and temp_extract_dir.exists():
            shutil.rmtree(temp_extract_dir, ignore_errors=True)
