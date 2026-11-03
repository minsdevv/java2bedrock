"""GeyserMC Custom Mappings Exporter (Format v2 for Geyser 2.11+ / MC 26.3 and Format v1)."""

from typing import Any, Dict, List
from ..parser.item_parser import ItemPredicateRule, ParsedJavaModel


def _serialize_predicate_v2(rule: ItemPredicateRule) -> Dict[str, Any]:
    """Serialize an ItemPredicateRule into Geyser v2 predicate JSON."""
    if rule.kind == "range_dispatch":
        obj: Dict[str, Any] = {
            "type": "range_dispatch",
            "property": rule.property_name,
            "threshold": float(rule.threshold if rule.threshold is not None else 0.0),
        }
        if rule.property_name == "custom_model_data":
            obj["index"] = rule.index
        return obj
    if rule.kind == "match":
        obj = {
            "type": "match",
            "property": rule.property_name,
            "value": rule.match_value,
        }
        if rule.property_name == "custom_model_data":
            obj["index"] = rule.index
        return obj
    # "condition"
    obj = {
        "type": "condition",
        "property": rule.property_name,
        "expected": bool(rule.expected_bool if rule.expected_bool is not None else True),
    }
    if rule.property_name == "custom_model_data":
        obj["index"] = rule.index
    return obj


def build_geyser_item_mappings_v2(models: List[ParsedJavaModel]) -> Dict[str, Any]:
    """Build Geyser 2.11+ format_version: 2 item mappings JSON (Minecraft 26.3 compatible)."""
    items_by_java_id: Dict[str, List[Dict[str, Any]]] = {}

    for model in models:
        icon_name = f"j2b_{model.short_name}"
        is_handheld = bool(
            model.is_3d
            or (model.parent and "handheld" in model.parent)
            or "sword" in model.java_base_item
            or "pickaxe" in model.java_base_item
            or "axe" in model.java_base_item
        )

        # In Geyser v2 mappings, 'model' in a single definition specifies the item's
        # `minecraft:item_model` data component (which defaults to `java_base_item`,
        # e.g. "minecraft:diamond_sword", unless overridden by a custom item_model).
        item_model_component = model.java_base_item
        for p in model.predicates:
            if p.property_name == "item_model" and p.match_value:
                raw_im = str(p.match_value)
                item_model_component = raw_im if ":" in raw_im else f"minecraft:{raw_im}"
                break

        entry: Dict[str, Any] = {
            "type": "definition",
            "bedrock_identifier": model.bedrock_identifier,
            "model": (
                item_model_component
                if ":" in item_model_component
                else f"minecraft:{item_model_component}"
            ),
            "bedrock_options": {
                "icon": icon_name,
                "allow_offhand": True,
                "display_handheld": is_handheld,
            },
        }

        # Filter out synthetic item_model match rules since 'model' field already specifies it
        valid_preds = [
            _serialize_predicate_v2(p)
            for p in model.predicates
            if p.property_name != "item_model"
        ]
        if valid_preds:
            entry["predicate_strategy"] = "and"
            entry["predicate"] = valid_preds

        if model.components:
            entry["components"] = model.components

        items_by_java_id.setdefault(model.java_base_item, []).append(entry)

    return {
        "format_version": 2,
        "items": items_by_java_id,
    }


def build_geyser_item_mappings_v1(models: List[ParsedJavaModel]) -> Dict[str, Any]:
    """Build Geyser format_version: 1 item mappings JSON for backward compatibility."""
    items_by_java_id: Dict[str, List[Dict[str, Any]]] = {}

    for model in models:
        icon_name = f"j2b_{model.short_name}"
        entry: Dict[str, Any] = {
            "name": model.short_name,
            "icon": icon_name,
            "allow_offhand": True,
        }
        if model.custom_model_data_int is not None:
            entry["custom_model_data"] = model.custom_model_data_int

        for p in model.predicates:
            if p.property_name == "damage" and p.threshold is not None:
                entry["damage_predicate"] = p.threshold
            elif p.property_name == "unbreakable" and p.expected_bool:
                entry["unbreakable"] = True

        items_by_java_id.setdefault(model.java_base_item, []).append(entry)

    return {
        "format_version": 1,
        "items": items_by_java_id,
    }
