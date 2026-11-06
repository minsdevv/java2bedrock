"""Unified parser for Java Resource Pack item models (Legacy 1.14-1.21.1 & Modern 26.x/1.21.2+)."""

from .vanilla_assets import get_vanilla_textures_dir
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple


def load_json_lenient(path: Path) -> Dict[str, Any]:
    """Load JSON while tolerating leading zeros in numbers (e.g. 010811) and trailing commas."""
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    cleaned = re.sub(r"(:\s*)0+([1-9]\d*)", r"\1\2", raw)
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
    return json.loads(cleaned)


@dataclass
class ItemPredicateRule:
    """Represents a matching rule for a custom item (Geyser v1 & v2 compatible)."""

    kind: str  # "range_dispatch" | "match" | "condition"
    property_name: str  # e.g. "custom_model_data", "damage", "damaged", "trim_material"
    threshold: Optional[float] = None
    match_value: Optional[Any] = None
    expected_bool: Optional[bool] = None
    index: int = 0


@dataclass
class ParsedJavaModel:
    """Resolved Java 3D or 2D item model."""

    model_id: str  # e.g. "nexo:item/ruby_sword" or "minecraft:item/custom_katana"
    java_base_item: str  # e.g. "minecraft:diamond_sword"
    bedrock_identifier: str  # e.g. "j2b:ruby_sword"
    short_name: str  # e.g. "ruby_sword"
    is_3d: bool
    parent: Optional[str] = None
    parent_chain: List[str] = field(default_factory=list)
    textures: Dict[str, str] = field(default_factory=dict)
    elements: List[Dict[str, Any]] = field(default_factory=list)
    display: Dict[str, Dict[str, List[float]]] = field(default_factory=dict)
    predicates: List[ItemPredicateRule] = field(default_factory=list)
    custom_model_data_int: Optional[int] = None
    tints: List[Dict[str, Any]] = field(default_factory=list)
    components: Dict[str, Any] = field(default_factory=dict)


def normalize_identifier(raw_id: str, default_namespace: str = "minecraft") -> Tuple[str, str]:
    """Split 'namespace:path' into (namespace, path)."""
    clean = raw_id.strip()
    if ":" in clean:
        ns, path = clean.split(":", 1)
        return ns, path
    return default_namespace, clean


def _candidate_namespaces(ns: str) -> List[str]:
    """Return candidate namespaces, stripping ItemsAdder's '_b_' and '_' atlas prefixes."""
    cands = [ns]
    stripped = re.sub(r"^_(?:b_)?", "", ns)
    if stripped and stripped not in cands:
        cands.append(stripped)
    if ns.startswith("_") and ns.lstrip("_") not in cands:
        cands.append(ns.lstrip("_"))
    return cands


def resolve_model_path(pack_root: Path, model_ref: str) -> Optional[Path]:
    """Locate the JSON file for a given model reference like 'nexo:item/katana'."""
    ns, rel_path = normalize_identifier(model_ref)
    if rel_path.endswith(".json"):
        rel_path = rel_path[:-5]
    for cand_ns in _candidate_namespaces(ns):
        candidate = pack_root / "assets" / cand_ns / "models" / f"{rel_path}.json"
        if candidate.is_file():
            return candidate
        # Fallback without 'models/' if already prefixed
        candidate_alt = pack_root / "assets" / cand_ns / f"{rel_path}.json"
        if candidate_alt.is_file():
            return candidate_alt
    return None


def resolve_texture_path(
    pack_root: Path,
    tex_ref: str,
    allow_vanilla_fallback: bool = True,
) -> Optional[Path]:
    """Locate the PNG file for a given texture reference like 'nexo:item/katana'."""
    if not tex_ref or tex_ref.startswith("#"):
        return None
    ns, rel_path = normalize_identifier(tex_ref)
    if rel_path.startswith("textures/"):
        rel_path = rel_path[len("textures/") :]
    if rel_path.endswith(".png"):
        rel_path = rel_path[:-4]
    cands = _candidate_namespaces(ns)
    for cand_ns in cands:
        candidate = pack_root / "assets" / cand_ns / "textures" / f"{rel_path}.png"
        if candidate.is_file():
            return candidate
    if allow_vanilla_fallback and any(c in ("minecraft", "") for c in cands):
        vanilla_dir = get_vanilla_textures_dir()
        if vanilla_dir is not None:
            vanilla_cache = vanilla_dir / f"{rel_path}.png"
            if vanilla_cache.is_file():
                return vanilla_cache
    return None


STANDARD_CUBE_ELEMENTS = [
    {
        "from": [0, 0, 0],
        "to": [16, 16, 16],
        "faces": {
            "down": {"uv": [0, 0, 16, 16], "texture": "#down", "cullface": "down"},
            "up": {"uv": [0, 0, 16, 16], "texture": "#up", "cullface": "up"},
            "north": {"uv": [0, 0, 16, 16], "texture": "#north", "cullface": "north"},
            "south": {"uv": [0, 0, 16, 16], "texture": "#south", "cullface": "south"},
            "west": {"uv": [0, 0, 16, 16], "texture": "#west", "cullface": "west"},
            "east": {"uv": [0, 0, 16, 16], "texture": "#east", "cullface": "east"},
        },
    }
]

STANDARD_BLOCK_DISPLAY = {
    "gui": {"rotation": [30, 225, 0], "translation": [0, 0, 0], "scale": [0.625, 0.625, 0.625]},
    "ground": {"rotation": [0, 0, 0], "translation": [0, 3, 0], "scale": [0.25, 0.25, 0.25]},
    "fixed": {"rotation": [0, 0, 0], "translation": [0, 0, 0], "scale": [0.5, 0.5, 0.5]},
    "thirdperson_righthand": {"rotation": [75, 45, 0], "translation": [0, 2.5, 0], "scale": [0.375, 0.375, 0.375]},
    "firstperson_righthand": {"rotation": [0, 45, 0], "translation": [0, 0, 0], "scale": [0.4, 0.4, 0.4]},
    "firstperson_lefthand": {"rotation": [0, 225, 0], "translation": [0, 0, 0], "scale": [0.4, 0.4, 0.4]},
}


def load_resolved_model_json(
    pack_root: Path,
    model_ref: str,
    visited: Optional[set] = None,
) -> Dict[str, Any]:
    """Recursively resolve 'parent' hierarchy for a Java model JSON."""
    if visited is None:
        visited = set()
    if model_ref in visited:
        return {}
    visited.add(model_ref)

    model_path = resolve_model_path(pack_root, model_ref)
    if not model_path:
        return {"parent": model_ref}

    try:
        current = load_json_lenient(model_path)
    except Exception:
        return {}

    parent_ref = current.get("parent")
    if not parent_ref:
        return current

    # Builtin vanilla parents
    _, parent_rel = normalize_identifier(parent_ref)
    if parent_rel in ("item/generated", "item/handheld", "item/handheld_rod", "builtin/generated", "builtin/entity"):
        merged = dict(current)
        merged["_root_parent"] = parent_rel
        merged["_parent_chain"] = [parent_ref]
        return merged

    if parent_rel in (
        "block/cube_all", "block/cube", "block/cube_column", "block/cube_bottom_top",
        "block/orientable", "block/leaves", "block/cross", "block/tinted_cross"
    ) or parent_rel.startswith("block/cube"):
        merged = dict(current)
        merged["_root_parent"] = parent_rel
        merged["_parent_chain"] = [parent_ref]
        if "elements" not in merged:
            tex_map = dict(merged.get("textures", {}))
            primary = (
                tex_map.get("all")
                or tex_map.get("texture")
                or tex_map.get("layer0")
                or (next(iter(tex_map.values())) if tex_map else "all")
            )
            for face in ("down", "up", "north", "south", "west", "east"):
                if face not in tex_map:
                    tex_map[face] = primary
            merged["textures"] = tex_map
            merged["elements"] = [dict(el) for el in STANDARD_CUBE_ELEMENTS]
            if "display" not in merged:
                merged["display"] = dict(STANDARD_BLOCK_DISPLAY)
        return merged

    parent_data = load_resolved_model_json(pack_root, parent_ref, visited)
    merged: Dict[str, Any] = dict(parent_data)
    chain = list(parent_data.get("_parent_chain", []))
    chain.append(parent_ref)
    merged["_parent_chain"] = chain

    # Merge textures
    merged_textures = dict(parent_data.get("textures", {}))
    merged_textures.update(current.get("textures", {}))
    if merged_textures:
        merged["textures"] = merged_textures

    # Merge display
    merged_display = dict(parent_data.get("display", {}))
    merged_display.update(current.get("display", {}))
    if merged_display:
        merged["display"] = merged_display

    # Override elements if present in child
    if "elements" in current:
        merged["elements"] = current["elements"]
    if "gui_light" in current:
        merged["gui_light"] = current["gui_light"]
    merged["parent"] = parent_ref
    return merged


def resolve_texture_variables(textures: Dict[str, str]) -> Dict[str, str]:
    """Resolve '#variable' references inside a model's textures dictionary."""
    resolved: Dict[str, str] = {}
    for key, val in textures.items():
        cur = val
        depth = 0
        while isinstance(cur, str) and cur.startswith("#") and depth < 10:
            ref_key = cur[1:]
            cur = textures.get(ref_key, cur)
            depth += 1
        resolved[key] = cur
    return resolved


def _make_short_name(model_ref: str, cmd: Optional[int] = None) -> str:
    ns, path = normalize_identifier(model_ref)
    slug = path.replace("/", "_").replace("-", "_").replace(".", "_")
    if slug.startswith("item_"):
        slug = slug[5:]
    if slug.startswith("ia_auto_"):
        slug = slug[8:]
    clean_ns = ns.lstrip("_")
    if clean_ns != "minecraft":
        if clean_ns.startswith("ia") and len(clean_ns) > 2:
            clean_ns = clean_ns[2:]
        slug = f"{clean_ns}_{slug}"
    if cmd is not None and str(cmd) not in slug:
        slug = f"{slug}_{cmd}"
    if len(slug) > 42:
        if cmd is not None:
            tail = f"_{cmd}"
            slug = slug[: 42 - len(tail)] + tail
        else:
            slug = slug[:42]
    return slug.lower()


def _build_parsed_model(
    pack_root: Path,
    model_ref: str,
    java_base_item: str,
    predicates: List[ItemPredicateRule],
    cmd_int: Optional[int] = None,
    tints: Optional[List[Dict[str, Any]]] = None,
    bedrock_ns: str = "j2b",
) -> Optional[ParsedJavaModel]:
    resolved = load_resolved_model_json(pack_root, model_ref)
    if not resolved:
        return None

    textures = resolve_texture_variables(resolved.get("textures", {}))
    elements = resolved.get("elements", [])
    display = resolved.get("display", {})
    parent = resolved.get("_root_parent") or resolved.get("parent")
    is_3d = bool(elements)

    # Ignore pure vanilla models with neither elements nor custom textures on disk
    if not is_3d and not predicates and not any(resolve_texture_path(pack_root, t, allow_vanilla_fallback=False) for t in textures.values()):
        return None

    short_name = _make_short_name(model_ref, cmd_int)
    bedrock_id = f"{bedrock_ns}:{short_name}"

    return ParsedJavaModel(
        model_id=model_ref,
        java_base_item=java_base_item,
        bedrock_identifier=bedrock_id,
        short_name=short_name,
        is_3d=is_3d,
        parent=parent,
        parent_chain=resolved.get("_parent_chain", []),
        textures=textures,
        elements=elements,
        display=display,
        predicates=predicates,
        custom_model_data_int=cmd_int,
        tints=tints or [],
    )


def _walk_modern_item_node(
    pack_root: Path,
    node: Dict[str, Any],
    java_base_item: str,
    inherited_predicates: List[ItemPredicateRule],
    results: List[ParsedJavaModel],
    bedrock_ns: str = "j2b",
) -> None:
    """Recursively traverse Minecraft 26.x / 1.21.2+ item definition tree."""
    if not isinstance(node, dict):
        return

    node_type = node.get("type", "")
    _, clean_type = normalize_identifier(node_type)

    if clean_type == "model":
        model_ref = node.get("model")
        tints = node.get("tints", [])
        if model_ref:
            cmd_int = None
            for p in inherited_predicates:
                if p.property_name == "custom_model_data" and p.threshold is not None:
                    cmd_int = int(p.threshold)
                    break
            parsed = _build_parsed_model(
                pack_root=pack_root,
                model_ref=model_ref,
                java_base_item=java_base_item,
                predicates=list(inherited_predicates),
                cmd_int=cmd_int,
                tints=tints,
                bedrock_ns=bedrock_ns,
            )
            if parsed:
                results.append(parsed)

    elif clean_type == "range_dispatch":
        _, prop_name = normalize_identifier(node.get("property", "custom_model_data"))
        index = int(node.get("index", 0))
        for entry in node.get("entries", []):
            threshold = float(entry.get("threshold", 0.0))
            rule = ItemPredicateRule(
                kind="range_dispatch",
                property_name=prop_name,
                threshold=threshold,
                index=index,
            )
            child_model = entry.get("model")
            if isinstance(child_model, dict):
                _walk_modern_item_node(
                    pack_root,
                    child_model,
                    java_base_item,
                    inherited_predicates + [rule],
                    results,
                    bedrock_ns,
                )
        fallback = node.get("fallback")
        if isinstance(fallback, dict) and inherited_predicates:
            _walk_modern_item_node(
                pack_root, fallback, java_base_item, inherited_predicates, results, bedrock_ns
            )

    elif clean_type == "select":
        _, prop_name = normalize_identifier(node.get("property", "custom_model_data"))
        index = int(node.get("index", 0))
        for case in node.get("cases", []):
            when_val = case.get("when")
            when_list = when_val if isinstance(when_val, list) else [when_val]
            for val in when_list:
                rule = ItemPredicateRule(
                    kind="match",
                    property_name=prop_name,
                    match_value=val,
                    index=index,
                )
                child_model = case.get("model")
                if isinstance(child_model, dict):
                    _walk_modern_item_node(
                        pack_root,
                        child_model,
                        java_base_item,
                        inherited_predicates + [rule],
                        results,
                        bedrock_ns,
                    )

    elif clean_type == "condition":
        _, prop_name = normalize_identifier(node.get("property", "custom_model_data"))
        index = int(node.get("index", 0))
        for branch_key, expected in (("on_true", True), ("on_false", False)):
            branch = node.get(branch_key)
            if isinstance(branch, dict):
                rule = ItemPredicateRule(
                    kind="condition",
                    property_name=prop_name,
                    expected_bool=expected,
                    index=index,
                )
                _walk_modern_item_node(
                    pack_root,
                    branch,
                    java_base_item,
                    inherited_predicates + [rule],
                    results,
                    bedrock_ns,
                )

    elif clean_type == "composite":
        for child in node.get("models", []):
            if isinstance(child, dict):
                _walk_modern_item_node(
                    pack_root, child, java_base_item, inherited_predicates, results, bedrock_ns
                )


def parse_java_pack_items(pack_root: Path, bedrock_ns: str = "j2b") -> List[ParsedJavaModel]:
    """Parse both Modern (26.x / 1.21.2+) and Legacy (1.14 - 1.21.1) item models from a Java pack."""
    pack_root = Path(pack_root).resolve()
    assets_dir = pack_root / "assets"
    if not assets_dir.is_dir():
        return []

    parsed_models: List[ParsedJavaModel] = []
    seen_bedrock_ids = set()
    seen_item_keys: set[Tuple[str, Optional[int]]] = set()

    # 1. Scan Modern 26.x / 1.21.2+ Item Definitions: assets/<ns>/items/*.json
    for ns_dir in sorted(assets_dir.iterdir()):
        if not ns_dir.is_dir():
            continue
        ns = ns_dir.name
        if ns in ("_iainternal",):
            continue
        items_dir = ns_dir / "items"
        if items_dir.is_dir():
            for item_file in sorted(items_dir.rglob("*.json")):
                rel_item = item_file.relative_to(items_dir).with_suffix("").as_posix()
                if rel_item == "block_outline" or rel_item.startswith("base/"):
                    continue
                try:
                    data = load_json_lenient(item_file)
                except Exception:
                    continue
                root_model = data.get("model")
                if not isinstance(root_model, dict):
                    continue

                if ns == "minecraft":
                    java_base_item = f"minecraft:{rel_item}"
                    initial_preds: List[ItemPredicateRule] = []
                else:
                    # Direct custom namespace item_model (e.g., nexo:katana) mapped via paper/default item
                    java_base_item = data.get("base_item", "minecraft:paper")
                    initial_preds = [
                        ItemPredicateRule(
                            kind="match",
                            property_name="item_model",
                            match_value=f"{ns}:{rel_item}",
                        )
                    ]

                found: List[ParsedJavaModel] = []
                _walk_modern_item_node(
                    pack_root, root_model, java_base_item, initial_preds, found, bedrock_ns
                )
                for m in found:
                    if m.custom_model_data_int is not None:
                        key = (m.java_base_item, m.custom_model_data_int)
                        if key in seen_item_keys:
                            continue
                        seen_item_keys.add(key)
                    if m.bedrock_identifier in seen_bedrock_ids:
                        base_slug = m.java_base_item.split(":")[-1]
                        m.short_name = f"{base_slug[:4]}_{m.short_name}"[:42]
                        m.bedrock_identifier = f"{bedrock_ns}:{m.short_name}"
                    if m.bedrock_identifier not in seen_bedrock_ids:
                        seen_bedrock_ids.add(m.bedrock_identifier)
                        parsed_models.append(m)

    # 2. Scan Legacy 1.14 - 1.21.1 Item Overrides: assets/minecraft/models/item/*.json
    mc_models_item_dir = assets_dir / "minecraft" / "models" / "item"
    if mc_models_item_dir.is_dir():
        for model_file in sorted(mc_models_item_dir.rglob("*.json")):
            rel_item = model_file.relative_to(mc_models_item_dir).with_suffix("").as_posix()
            if rel_item == "block_outline" or rel_item.startswith("base/"):
                continue
            try:
                data = load_json_lenient(model_file)
            except Exception:
                continue

            overrides = data.get("overrides", [])
            if not isinstance(overrides, list):
                continue

            java_base_item = f"minecraft:{rel_item}"
            for ov in overrides:
                if not isinstance(ov, dict):
                    continue
                pred_dict = ov.get("predicate", {})
                target_model = ov.get("model")
                if not target_model or not isinstance(pred_dict, dict):
                    continue

                rules: List[ItemPredicateRule] = []
                cmd_int: Optional[int] = None
                skip_override = False
                for k, v in pred_dict.items():
                    if k == "custom_model_data":
                        cmd_int = int(v)
                        rules.append(
                            ItemPredicateRule(
                                kind="range_dispatch",
                                property_name="custom_model_data",
                                threshold=float(v),
                                index=0,
                            )
                        )
                    elif k == "damage":
                        rules.append(
                            ItemPredicateRule(
                                kind="range_dispatch",
                                property_name="damage",
                                threshold=float(v),
                            )
                        )
                    elif k in ("damaged", "broken"):
                        rules.append(
                            ItemPredicateRule(
                                kind="condition",
                                property_name=k,
                                expected_bool=bool(int(v) == 1 if isinstance(v, (int, float)) else v),
                            )
                        )
                    elif k == "cast":
                        if bool(int(v) == 1 if isinstance(v, (int, float)) else v):
                            skip_override = True
                    elif k in ("pull", "pulling", "throwing", "blocking", "time", "angle", "cooldown", "charged", "firework", "lefthanded"):
                        # Secondary animation state frame (e.g. bow pulling frame 0/1/2)
                        if float(v) > 0:
                            skip_override = True
                if skip_override or not rules:
                    continue

                parsed = _build_parsed_model(
                    pack_root=pack_root,
                    model_ref=target_model,
                    java_base_item=java_base_item,
                    predicates=rules,
                    cmd_int=cmd_int,
                    bedrock_ns=bedrock_ns,
                )
                if parsed:
                    if parsed.custom_model_data_int is not None:
                        key = (parsed.java_base_item, parsed.custom_model_data_int)
                        if key in seen_item_keys:
                            continue
                        seen_item_keys.add(key)
                    if parsed.bedrock_identifier in seen_bedrock_ids:
                        base_slug = parsed.java_base_item.split(":")[-1]
                        parsed.short_name = f"{base_slug[:4]}_{parsed.short_name}"[:42]
                        parsed.bedrock_identifier = f"{bedrock_ns}:{parsed.short_name}"
                    if parsed.bedrock_identifier not in seen_bedrock_ids:
                        seen_bedrock_ids.add(parsed.bedrock_identifier)
                        parsed_models.append(parsed)

    return parsed_models
