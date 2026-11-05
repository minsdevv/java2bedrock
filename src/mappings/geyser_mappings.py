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
        # In Bedrock, display_handheld=True rotates item icons by 45 deg in GUIs/slots (like swords/tools).
        # Only actual tools/weapons should have display_handheld=True.
        # Blocks, paintings, furniture, food, and wearable hats must remain flat (display_handheld=False).
        is_tool_or_weapon = any(
            kw in model.model_id.lower() or kw in model.short_name.lower() or kw in model.java_base_item.lower()
            for kw in (
                "sword", "pickaxe", "axe", "shovel", "hoe", "weapon", "gun", "bow",
                "crossbow", "rod", "stick", "staff", "wand", "spear", "dagger",
                "knife", "rifle", "pistol", "shotgun", "ak47", "handheld"
            )
        )
        is_handheld = bool(
            (model.parent and "handheld" in model.parent)
            or is_tool_or_weapon
        ) and not (
            "block/" in model.model_id.lower()
            or "blocks/" in model.model_id.lower()
            or (model.parent and "block" in model.parent.lower())
            or any(
                kw in model.model_id.lower() or kw in model.short_name.lower()
                for kw in ("painting", "furniture", "deco", "hat", "cap", "mask", "fridge", "chair", "table")
            )
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

        components = dict(model.components) if model.components else {}
        is_weapon_or_tool = any(
            kw in model.model_id.lower() or kw in model.short_name.lower()
            for kw in (
                "weapon", "gun", "sword", "shield", "bow", "axe", "pickaxe",
                "shovel", "hoe", "spear", "staff", "knife", "dagger", "shotgun",
                "revolver", "pistol", "rifle", "ak47"
            )
        )
        is_wearable_head = (
            any(
                kw in model.model_id.lower()
                for kw in ("hat/", "hat_", "helmet", "cap", "mask", "crown", "glasses", "iawearables:")
            )
            or (model.components and model.components.get("minecraft:equippable", {}).get("slot") == "head")
        )
        is_furniture = any(
            kw in model.model_id.lower()
            for kw in ("iadeco:", "furniture", "mini_fridge", "chair", "table")
        )

        if (
            model.is_3d
            and "minecraft:equippable" not in components
            and not any(
                armor_kw in model.java_base_item
                for armor_kw in ("helmet", "chestplate", "leggings", "boots")
            )
            and not is_weapon_or_tool
            and is_wearable_head
        ):
            components["minecraft:equippable"] = {"slot": "head"}

        if components:
            entry["components"] = components

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
