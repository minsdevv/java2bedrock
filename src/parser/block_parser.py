"""Parser for Java Custom Blockstates (NoteBlock, Tripwire, Mushroom) & Display Furniture."""

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .item_parser import (
    load_resolved_model_json,
    normalize_identifier,
    resolve_texture_path,
    resolve_texture_variables,
)


CUSTOM_BLOCK_CARRIERS = {
    "note_block",
    "tripwire",
    "mushroom_stem",
    "brown_mushroom_block",
    "red_mushroom_block",
    "chorus_plant",
}

CUBE_PARENTS = {
    "block/cube_all",
    "block/cube",
    "block/cube_column",
    "block/cube_bottom_top",
    "block/orientable",
    "block/leaves",
}


@dataclass
class ParsedCustomBlock:
    """Resolved custom block variant mapped from a vanilla blockstate carrier."""

    java_block_state: str  # e.g. "minecraft:note_block[instrument=harp,note=1,powered=false]"
    base_block: str  # e.g. "minecraft:note_block"
    state_predicate: str  # e.g. "[instrument=harp,note=1,powered=false]"
    model_id: str  # e.g. "nexo:block/ruby_ore"
    short_name: str  # e.g. "nexo_block_ruby_ore"
    bedrock_identifier: str  # e.g. "j2b:nexo_block_ruby_ore"
    is_unit_cube: bool
    textures: Dict[str, str] = field(default_factory=dict)
    elements: List[Dict[str, Any]] = field(default_factory=list)
    rotation_xyz: Tuple[int, int, int] = (0, 0, 0)


@dataclass
class ParsedFurniture:
    """Resolved Display Furniture model (ItemDisplay-based 3D furniture)."""

    furniture_id: str  # e.g. "nexo:oak_chair"
    model_id: str  # e.g. "nexo:furniture/oak_chair"
    short_name: str  # e.g. "nexo_furniture_oak_chair"
    bedrock_entity_id: str  # e.g. "j2b:furniture_nexo_oak_chair"
    java_base_item: str = "minecraft:paper"
    custom_model_data: Optional[int] = None
    textures: Dict[str, str] = field(default_factory=dict)
    elements: List[Dict[str, Any]] = field(default_factory=list)
    hitbox_width: float = 1.0
    hitbox_height: float = 1.0
    seat_height: Optional[float] = None


def _is_standard_unit_cube(parent: Optional[str], elements: List[Dict[str, Any]]) -> bool:
    if parent:
        _, rel_p = normalize_identifier(parent)
        if rel_p in CUBE_PARENTS:
            return True
    if len(elements) == 1:
        el = elements[0]
        if el.get("from") == [0, 0, 0] and el.get("to") == [16, 16, 16] and not el.get("rotation"):
            return True
    return not bool(elements)


def _multipart_when_to_state_str(when_obj: Dict[str, Any]) -> str:
    """Convert a multipart 'when' dictionary into a canonical '[k1=v1,k2=v2]' state string."""
    if "AND" in when_obj and isinstance(when_obj["AND"], list):
        merged: Dict[str, str] = {}
        for sub in when_obj["AND"]:
            if isinstance(sub, dict):
                for k, v in sub.items():
                    merged[str(k)] = str(v).lower() if isinstance(v, bool) else str(v)
        parts = [f"{k}={merged[k]}" for k in sorted(merged.keys())]
        return f"[{','.join(parts)}]"

    parts = []
    for k in sorted(when_obj.keys()):
        if k in ("OR", "AND"):
            continue
        v = when_obj[k]
        val_str = str(v).lower() if isinstance(v, bool) else str(v)
        parts.append(f"{k}={val_str}")
    return f"[{','.join(parts)}]" if parts else ""


def _make_block_short_name(model_ref: str) -> str:
    ns, path = normalize_identifier(model_ref)
    slug = path.replace("/", "_").replace("-", "_").replace(".", "_")
    if slug.startswith("block_"):
        slug = slug[6:]
    if ns != "minecraft":
        slug = f"{ns}_{slug}"
    return slug.lower()


def parse_java_pack_blocks(
    pack_root: Path,
    bedrock_ns: str = "j2b",
) -> List[ParsedCustomBlock]:
    """Scan assets/minecraft/blockstates/*.json for custom blocks."""
    results: List[ParsedCustomBlock] = []
    bs_dir = pack_root / "assets" / "minecraft" / "blockstates"
    if not bs_dir.is_dir():
        return results

    for bs_file in sorted(bs_dir.glob("*.json")):
        block_stem = bs_file.stem
        if block_stem not in CUSTOM_BLOCK_CARRIERS:
            continue
        base_block = f"minecraft:{block_stem}"
        try:
            data = json.loads(bs_file.read_text(encoding="utf-8-sig"))
        except Exception:
            continue

        entries_to_process: List[Tuple[str, Dict[str, Any]]] = []

        # 1. Variants format
        variants = data.get("variants")
        if isinstance(variants, dict):
            for state_key, apply_val in variants.items():
                apply_obj = apply_val[0] if isinstance(apply_val, list) and apply_val else apply_val
                if isinstance(apply_obj, dict):
                    norm_state = f"[{state_key}]" if state_key and not state_key.startswith("[") else state_key
                    entries_to_process.append((norm_state, apply_obj))

        # 2. Multipart format
        multipart = data.get("multipart")
        if isinstance(multipart, list):
            for part in multipart:
                if not isinstance(part, dict):
                    continue
                when_obj = part.get("when")
                apply_val = part.get("apply")
                if not isinstance(when_obj, dict) or not apply_val:
                    continue
                apply_obj = apply_val[0] if isinstance(apply_val, list) and apply_val else apply_val
                if isinstance(apply_obj, dict):
                    state_str = _multipart_when_to_state_str(when_obj)
                    if state_str:
                        entries_to_process.append((state_str, apply_obj))

        for state_pred, apply_obj in entries_to_process:
            model_ref = apply_obj.get("model")
            if not model_ref:
                continue
            ns, rel_model = normalize_identifier(model_ref)
            # Skip unmodified vanilla note_block / mushroom models
            if ns == "minecraft" and rel_model in (
                "block/note_block",
                "block/tripwire_ns",
                "block/tripwire_n",
                "block/mushroom_stem",
                "block/brown_mushroom_block",
                "block/red_mushroom_block",
                "block/template_single_face",
            ):
                continue

            resolved = load_resolved_model_json(pack_root, model_ref)
            if not resolved:
                continue
            textures = resolve_texture_variables(resolved.get("textures", {}))
            elements = resolved.get("elements", [])
            parent = resolved.get("_root_parent") or resolved.get("parent")

            if not elements and not any(resolve_texture_path(pack_root, t) for t in textures.values()):
                continue

            is_cube = _is_standard_unit_cube(parent, elements)
            short_name = _make_block_short_name(model_ref)
            rot_x = int(apply_obj.get("x", 0))
            rot_y = int(apply_obj.get("y", 0))
            rot_z = int(apply_obj.get("z", 0))

            full_state = f"{base_block}{state_pred}"
            results.append(
                ParsedCustomBlock(
                    java_block_state=full_state,
                    base_block=base_block,
                    state_predicate=state_pred,
                    model_id=model_ref,
                    short_name=short_name,
                    bedrock_identifier=f"{bedrock_ns}:block_{short_name}",
                    is_unit_cube=is_cube,
                    textures=textures,
                    elements=elements,
                    rotation_xyz=(rot_x, rot_y, rot_z),
                )
            )

    return results


def parse_java_pack_furniture(
    pack_root: Path,
    bedrock_ns: str = "j2b",
) -> List[ParsedFurniture]:
    """Discover Display Furniture 3D models from furniture.json or assets/<ns>/models/**/furniture/*.json."""
    results: List[ParsedFurniture] = []
    seen_models: set[str] = set()

    # 1. Explicit furniture.json at pack root if provided
    furniture_cfg = pack_root / "furniture.json"
    if furniture_cfg.is_file():
        try:
            cfg_data = json.loads(furniture_cfg.read_text(encoding="utf-8-sig"))
            for furn_id, info in cfg_data.get("furniture", {}).items():
                model_ref = info.get("model", furn_id)
                resolved = load_resolved_model_json(pack_root, model_ref)
                if not resolved or not resolved.get("elements"):
                    continue
                textures = resolve_texture_variables(resolved.get("textures", {}))
                short_name = _make_block_short_name(model_ref)
                seen_models.add(model_ref)
                results.append(
                    ParsedFurniture(
                        furniture_id=furn_id,
                        model_id=model_ref,
                        short_name=short_name,
                        bedrock_entity_id=f"{bedrock_ns}:furniture_{short_name}",
                        java_base_item=info.get("item", "minecraft:paper"),
                        custom_model_data=info.get("custom_model_data"),
                        textures=textures,
                        elements=resolved["elements"],
                        hitbox_width=float(info.get("hitbox", {}).get("width", 1.0)),
                        hitbox_height=float(info.get("hitbox", {}).get("height", 1.0)),
                        seat_height=info.get("seat_height"),
                    )
                )
        except Exception:
            pass

    # 2. Auto-discover 3D models under assets/<ns>/models/furniture/**/*.json
    assets_dir = pack_root / "assets"
    if assets_dir.is_dir():
        for ns_dir in sorted(assets_dir.iterdir()):
            furn_models_dir = ns_dir / "models" / "furniture"
            if not furn_models_dir.is_dir():
                continue
            for mf in sorted(furn_models_dir.rglob("*.json")):
                rel_p = mf.relative_to(ns_dir / "models").with_suffix("").as_posix()
                model_ref = f"{ns_dir.name}:{rel_p}"
                if model_ref in seen_models:
                    continue
                resolved = load_resolved_model_json(pack_root, model_ref)
                if not resolved or not resolved.get("elements"):
                    continue
                textures = resolve_texture_variables(resolved.get("textures", {}))
                short_name = _make_block_short_name(model_ref)
                seen_models.add(model_ref)
                results.append(
                    ParsedFurniture(
                        furniture_id=f"{ns_dir.name}:{mf.stem}",
                        model_id=model_ref,
                        short_name=short_name,
                        bedrock_entity_id=f"{bedrock_ns}:furniture_{short_name}",
                        textures=textures,
                        elements=resolved["elements"],
                    )
                )

    return results
