"""GeyserMC Custom Mappings Exporter (Format v2 for Geyser 2.11+ / MC 26.3 and Format v1)."""

import re
from typing import Any, Dict, List
from ..parser.item_parser import ItemPredicateRule, ParsedJavaModel


def _has_kw(keywords, *texts: str) -> bool:
    """True if any keyword equals a whole token (split on non-alphanumerics) of the given texts.

    Whole-token matching avoids substring false positives such as 'cap' in 'capsule' or 'gun' in 'gunpowder'.
    """
    tokens = set()
    for t in texts:
        tokens.update(x for x in re.split(r"[^a-z0-9]+", (t or "").lower()) if x)
    return any(k in tokens for k in keywords)


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


VANILLA_WEAPONS_AND_TOOLS = {
    "wooden_sword", "stone_sword", "iron_sword", "golden_sword", "diamond_sword", "netherite_sword",
    "wooden_pickaxe", "stone_pickaxe", "iron_pickaxe", "golden_pickaxe", "diamond_pickaxe", "netherite_pickaxe",
    "wooden_axe", "stone_axe", "iron_axe", "golden_axe", "diamond_axe", "netherite_axe",
    "wooden_shovel", "stone_shovel", "iron_shovel", "golden_shovel", "diamond_shovel", "netherite_shovel",
    "wooden_hoe", "stone_hoe", "iron_hoe", "golden_hoe", "diamond_hoe", "netherite_hoe",
    "bow", "crossbow", "trident", "mace", "fishing_rod", "carrot_on_a_stick",
    "warped_fungus_on_a_stick", "brush", "spyglass", "shears", "flint_and_steel",
}

NON_HANDHELD_KEYWORDS = (
    "painting", "furniture", "deco", "hat", "cap", "mask", "fridge", "chair", "table", "crown", "glasses"
)

WEAPON_TOOL_KEYWORDS = (
    "sword", "pickaxe", "axe", "shovel", "hoe", "weapon", "gun", "bow",
    "crossbow", "trident", "rod", "stick", "staff", "wand", "spear", "dagger",
    "knife", "rifle", "pistol", "shotgun", "ak47", "handheld"
)


def is_model_handheld(model: ParsedJavaModel) -> bool:
    """Data-driven determination if an item should have display_handheld=True in Bedrock."""
    base_name = model.java_base_item.split(":")[-1]
    if any(base_name.endswith(s) for s in ("_helmet", "_chestplate", "_leggings", "_boots", "elytra", "shield")):
        return False

    if "block/" in model.model_id.lower() or "blocks/" in model.model_id.lower():
        return False
    if any("block" in p.lower() for p in getattr(model, "parent_chain", [])):
        return False
    if model.parent and "block" in model.parent.lower():
        return False

    if _has_kw(NON_HANDHELD_KEYWORDS, model.model_id, model.short_name):
        return False

    if any("handheld" in p.lower() for p in getattr(model, "parent_chain", [])):
        return True
    if model.parent and "handheld" in model.parent.lower():
        return True

    if base_name in VANILLA_WEAPONS_AND_TOOLS:
        return True

    return _has_kw(WEAPON_TOOL_KEYWORDS, model.model_id, model.short_name)


def build_geyser_item_mappings_v2(models: List[ParsedJavaModel]) -> Dict[str, Any]:
    """Build Geyser 2.11+ format_version: 2 item mappings JSON (Minecraft 26.3 compatible)."""
    items_by_java_id: Dict[str, List[Dict[str, Any]]] = {}

    for model in models:
        icon_name = f"j2b_{model.short_name}"
        is_handheld = is_model_handheld(model)
        bedrock_options = {
            "icon": icon_name,
            "allow_offhand": True,
            "display_handheld": is_handheld,
        }

        components = dict(model.components) if model.components else {}
        is_weapon_or_tool = _has_kw(
            (
                "weapon", "gun", "sword", "shield", "bow", "crossbow", "trident",
                "axe", "pickaxe", "shovel", "hoe", "spear", "staff", "knife",
                "dagger", "shotgun", "revolver", "pistol", "rifle", "ak47"
            ),
            model.model_id, model.short_name,
        )
        is_wearable_head = (
            _has_kw(
                ("hat", "helmet", "cap", "mask", "crown", "glasses", "iawearables"),
                model.model_id,
            )
            or (model.components and model.components.get("minecraft:equippable", {}).get("slot") == "head")
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

        # In Geyser v2 mappings, 'model' in a single definition specifies the item's
        # `minecraft:item_model` data component (which defaults to `java_base_item`,
        # e.g. "minecraft:diamond_sword", unless overridden by a custom item_model).
        item_model_component = model.java_base_item
        has_explicit_item_model = False
        for p in model.predicates:
            if p.property_name == "item_model" and p.match_value:
                raw_im = str(p.match_value)
                item_model_component = raw_im if ":" in raw_im else f"minecraft:{raw_im}"
                has_explicit_item_model = True
                break

        # ItemsAdder-style stacks are still discriminated by custom_model_data numbers.
        # On Geyser 2.x, pure CMD matchers must use type=legacy; type=definition expects a
        # real item_model identity first and often fails to bind for CMD-only packs
        # (see Geyser#6439). Keep definition for true item_model / multi-predicate items.
        non_cmd_preds = [
            p for p in model.predicates
            if p.property_name not in ("item_model", "custom_model_data")
        ]
        use_legacy = (
            model.custom_model_data_int is not None
            and not has_explicit_item_model
            and not non_cmd_preds
        )

        if use_legacy:
            entry: Dict[str, Any] = {
                "type": "legacy",
                "bedrock_identifier": model.bedrock_identifier,
                "custom_model_data": int(model.custom_model_data_int),
                "bedrock_options": bedrock_options,
            }
        else:
            entry = {
                "type": "definition",
                "bedrock_identifier": model.bedrock_identifier,
                "model": (
                    item_model_component
                    if ":" in item_model_component
                    else f"minecraft:{item_model_component}"
                ),
                "bedrock_options": bedrock_options,
            }
            # Geyser only accepts a subset of condition properties. Entries that rely on
            # unsupported ones (pulling/blocking/charged/...) would make Geyser reject the
            # whole vanilla-item group — skip those charge/block variants entirely.
            geyser_condition_ok = {
                "broken", "damaged", "custom_model_data", "has_component", "fishing_rod_cast",
            }
            if any(
                p.kind == "condition" and p.property_name not in geyser_condition_ok
                for p in model.predicates
            ):
                continue

            valid_preds = [
                _serialize_predicate_v2(p)
                for p in model.predicates
                if p.property_name != "item_model"
            ]
            if valid_preds:
                entry["predicate_strategy"] = "and"
                entry["predicate"] = valid_preds

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
