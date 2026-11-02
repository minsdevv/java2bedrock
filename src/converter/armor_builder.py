"""Custom Armor & Equipment (Minecraft 26.3 & Legacy) Converter for Bedrock."""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from ..parser.item_parser import ParsedJavaModel, normalize_identifier


ARMOR_SLOT_BY_SUFFIX = {
    "_helmet": "head",
    "_chestplate": "chest",
    "_leggings": "legs",
    "_boots": "feet",
    "elytra": "chest",
}

BEDROCK_ARMOR_GEOMETRY = {
    "head": "geometry.player.armor.helmet",
    "chest": "geometry.player.armor.chestplate",
    "legs": "geometry.player.armor.leggings",
    "feet": "geometry.player.armor.boots",
    "elytra": "geometry.elytra",
}

BEDROCK_PARENT_SETUP = {
    "head": "v.helmet_layer_visible = 0.0;",
    "chest": "v.chest_layer_visible = 0.0;",
    "legs": "v.leg_layer_visible = 0.0;",
    "feet": "v.boot_layer_visible = 0.0;",
    "elytra": "v.chest_layer_visible = 0.0;",
}


def detect_armor_slot(model: ParsedJavaModel) -> Optional[str]:
    """Detect whether an item is an armor piece or elytra and return its slot ('head'|'chest'|'legs'|'feet'|'elytra')."""
    if "minecraft:equippable" in model.components:
        eq = model.components["minecraft:equippable"]
        if isinstance(eq, dict) and "slot" in eq:
            return str(eq["slot"]).lower()

    base_item = model.java_base_item.lower()
    if base_item.endswith("elytra"):
        return "elytra"
    for suffix, slot in ARMOR_SLOT__BY_SUFFIX_ITEMS:
        if base_item.endswith(suffix) or model.short_name.endswith(suffix):
            return slot
    return None


ARMOR_SLOT__BY_SUFFIX_ITEMS = list(ARMOR_SLOT_BY_SUFFIX.items())


def resolve_armor_wear_texture(
    pack_root: Path,
    model: ParsedJavaModel,
    slot: str,
) -> Optional[Path]:
    """Locate the 3D armor layer texture from Minecraft 26.3 equipment/*.json or legacy models/armor/."""
    layer_kind = "wings" if slot == "elytra" else ("humanoid_leggings" if slot == "legs" else "humanoid")
    legacy_layer_num = 2 if slot == "legs" else 1

    # 1. Check Minecraft 26.3 assets/<ns>/equipment/*.json
    assets_dir = pack_root / "assets"
    if assets_dir.is_dir():
        for ns_dir in sorted(assets_dir.iterdir()):
            eq_dir = ns_dir / "equipment"
            if not eq_dir.is_dir():
                continue
            for eq_file in sorted(eq_dir.rglob("*.json")):
                eq_stem = eq_file.stem.lower()
                if eq_stem in model.short_name or any(eq_stem in part for part in model.short_name.split("_")):
                    try:
                        eq_data = json.loads(eq_file.read_text(encoding="utf-8-sig"))
                        layers = eq_data.get("layers", {})
                        entries = layers.get(layer_kind, [])
                        if entries and isinstance(entries[0], dict):
                            tex_id = entries[0].get("texture", "")
                            ns, rel_tex = normalize_identifier(tex_id, default_namespace=ns_dir.name)
                            candidate = (
                                pack_root
                                / "assets"
                                / ns
                                / "textures"
                                / "entity"
                                / "equipment"
                                / layer_kind
                                / f"{rel_tex}.png"
                            )
                            if candidate.is_file():
                                return candidate
                    except Exception:
                        continue

    # 2. Check Legacy assets/<ns>/textures/models/armor/*_layer_1.png or _2.png
    if assets_dir.is_dir():
        for ns_dir in sorted(assets_dir.iterdir()):
            armor_tex_dir = ns_dir / "textures" / "models" / "armor"
            if not armor_tex_dir.is_dir():
                continue
            for png in sorted(armor_tex_dir.glob(f"*_layer_{legacy_layer_num}.png")):
                prefix = png.stem.replace(f"_layer_{legacy_layer_num}", "").lower()
                if prefix in model.short_name:
                    return png
            # Fallback to first matching layer
            all_layers = sorted(armor_tex_dir.glob(f"*_layer_{legacy_layer_num}.png"))
            if len(all_layers) == 1:
                return all_layers[0]

    return None


def build_bedrock_armor_attachable(
    model: ParsedJavaModel,
    slot: str,
    armor_texture_rel_path: str,
) -> Dict[str, Any]:
    """Generate a Bedrock 1.10.0 Armor Attachable JSON dictionary."""
    geom = BEDROCK_ARMOR_GEOMETRY.get(slot, "geometry.player.armor.chestplate")
    parent_setup = BEDROCK_PARENT_SETUP.get(slot, "v.chest_layer_visible = 0.0;")
    eq_slot = "chest" if slot == "elytra" else slot

    # Ensure Geyser v2 components include minecraft:equippable
    if "minecraft:equippable" not in model.components:
        model.components["minecraft:equippable"] = {"slot": eq_slot}

    return {
        "format_version": "1.10.0",
        "minecraft:attachable": {
            "description": {
                "identifier": model.bedrock_identifier,
                "materials": {
                    "default": "armor",
                    "enchanted": "armor_enchanted",
                },
                "textures": {
                    "default": armor_texture_rel_path,
                    "enchanted": "textures/misc/enchanted_item_glint",
                },
                "geometry": {
                    "default": geom,
                },
                "scripts": {
                    "parent_setup": parent_setup,
                },
                "render_controllers": [
                    "controller.render.armor",
                ],
            }
        },
    }
