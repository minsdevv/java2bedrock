"""Custom Armor & Equipment (Minecraft 26.3 & Legacy) Converter for Bedrock."""

import json
from pathlib import Path
import shutil
from typing import Any, Dict, Optional

from PIL import Image

from ..parser.item_parser import ParsedJavaModel, normalize_identifier


ARMOR_SLOT_BY_SUFFIX = {
    "_helmet": "head",
    "_chestplate": "chest",
    "_leggings": "legs",
    "_boots": "feet",
    "elytra": "chest",
}

BEDROCK_ARMOR_GEOMETRY = {
    "head": "geometry.humanoid.armor.helmet",
    "chest": "geometry.humanoid.armor.chestplate",
    "legs": "geometry.humanoid.armor.leggings",
    "feet": "geometry.humanoid.armor.boots",
    "elytra": "geometry.elytra",
}

BEDROCK_PARENT_SETUP = {
    "head": "v.helmet_layer_visible = 0.0;",
    "chest": "v.chest_layer_visible = 0.0;",
    "legs": "v.leg_layer_visible = 0.0;",
    "feet": "v.boot_layer_visible = 0.0;",
    "elytra": "v.chest_layer_visible = 0.0;",
}

STANDARD_PLAYER_ARMOR_GEO_DOC: Dict[str, Any] = {
    "format_version": "1.8.0",
    "geometry.player.armor.helmet": {
        "visible_bounds_width": 2,
        "visible_bounds_height": 2,
        "visible_bounds_offset": [0, 1, 0],
        "texturewidth": 64,
        "textureheight": 32,
        "bones": [
            {"name": "head", "pivot": [0.0, 24.0, 0.0], "cubes": [{"origin": [-4.0, 24.0, -4.0], "size": [8, 8, 8], "uv": [0, 0], "inflate": 1.0}]},
            {"name": "hat", "pivot": [0.0, 24.0, 0.0], "cubes": [{"origin": [-4.0, 24.0, -4.0], "size": [8, 8, 8], "uv": [32, 0], "inflate": 1.5}], "neverRender": False, "parent": "head"}
        ]
    },
    "geometry.player.armor.chestplate": {
        "visible_bounds_width": 2,
        "visible_bounds_height": 2,
        "visible_bounds_offset": [0, 1, 0],
        "texturewidth": 64,
        "textureheight": 32,
        "bones": [
            {"name": "body", "pivot": [0.0, 24.0, 0.0], "cubes": [{"origin": [-4.0, 12.0, -2.0], "size": [8, 12, 4], "uv": [16, 16], "inflate": 1.01}]},
            {"name": "rightArm", "pivot": [-5.0, 22.0, 0.0], "cubes": [{"origin": [-8.0, 12.0, -2.0], "size": [4, 12, 4], "uv": [40, 16], "inflate": 1.0}], "parent": "body"},
            {"name": "leftArm", "pivot": [5.0, 22.0, 0.0], "cubes": [{"origin": [4.0, 12.0, -2.0], "size": [4, 12, 4], "uv": [40, 16], "inflate": 1.0}], "mirror": True, "parent": "body"}
        ]
    },
    "geometry.player.armor.leggings": {
        "visible_bounds_width": 2,
        "visible_bounds_height": 2,
        "visible_bounds_offset": [0, 1, 0],
        "texturewidth": 64,
        "textureheight": 32,
        "bones": [
            {"name": "body", "pivot": [0.0, 24.0, 0.0], "cubes": [{"origin": [-4.0, 12.0, -2.0], "size": [8, 12, 4], "uv": [16, 16], "inflate": 0.5}]},
            {"name": "rightLeg", "pivot": [-1.9, 12.0, 0.0], "cubes": [{"origin": [-3.9, 0.0, -2.0], "size": [4, 12, 4], "uv": [0, 16], "inflate": 0.49}], "parent": "body"},
            {"name": "leftLeg", "pivot": [1.9, 12.0, 0.0], "cubes": [{"origin": [-0.1, 0.0, -2.0], "size": [4, 12, 4], "uv": [0, 16], "inflate": 0.49}], "mirror": True, "parent": "body"}
        ]
    },
    "geometry.player.armor.boots": {
        "visible_bounds_width": 2,
        "visible_bounds_height": 2,
        "visible_bounds_offset": [0, 1, 0],
        "texturewidth": 64,
        "textureheight": 32,
        "bones": [
            {"name": "rightLeg", "pivot": [-1.9, 12.0, 0.0], "cubes": [{"origin": [-3.9, 0.0, -2.0], "size": [4, 12, 4], "uv": [0, 16], "inflate": 1.0}]},
            {"name": "leftLeg", "pivot": [1.9, 12.0, 0.0], "cubes": [{"origin": [-0.1, 0.0, -2.0], "size": [4, 12, 4], "uv": [0, 16], "inflate": 1.0}], "mirror": True}
        ]
    },
    # Standard humanoid armor aliases for universal Bedrock client engine compatibility
    "geometry.humanoid.armor.helmet": {
        "visible_bounds_width": 2,
        "visible_bounds_height": 2,
        "visible_bounds_offset": [0, 1, 0],
        "texturewidth": 64,
        "textureheight": 32,
        "bones": [
            {"name": "head", "pivot": [0.0, 24.0, 0.0], "cubes": [{"origin": [-4.0, 24.0, -4.0], "size": [8, 8, 8], "uv": [0, 0], "inflate": 1.0}]},
            {"name": "hat", "pivot": [0.0, 24.0, 0.0], "cubes": [{"origin": [-4.0, 24.0, -4.0], "size": [8, 8, 8], "uv": [32, 0], "inflate": 1.5}], "neverRender": False, "parent": "head"}
        ]
    },
    "geometry.humanoid.armor.chestplate": {
        "visible_bounds_width": 2,
        "visible_bounds_height": 2,
        "visible_bounds_offset": [0, 1, 0],
        "texturewidth": 64,
        "textureheight": 32,
        "bones": [
            {"name": "body", "pivot": [0.0, 24.0, 0.0], "cubes": [{"origin": [-4.0, 12.0, -2.0], "size": [8, 12, 4], "uv": [16, 16], "inflate": 1.01}]},
            {"name": "rightArm", "pivot": [-5.0, 22.0, 0.0], "cubes": [{"origin": [-8.0, 12.0, -2.0], "size": [4, 12, 4], "uv": [40, 16], "inflate": 1.0}], "parent": "body"},
            {"name": "leftArm", "pivot": [5.0, 22.0, 0.0], "cubes": [{"origin": [4.0, 12.0, -2.0], "size": [4, 12, 4], "uv": [40, 16], "inflate": 1.0}], "mirror": True, "parent": "body"}
        ]
    },
    "geometry.humanoid.armor.leggings": {
        "visible_bounds_width": 2,
        "visible_bounds_height": 2,
        "visible_bounds_offset": [0, 1, 0],
        "texturewidth": 64,
        "textureheight": 32,
        "bones": [
            {"name": "body", "pivot": [0.0, 24.0, 0.0], "cubes": [{"origin": [-4.0, 12.0, -2.0], "size": [8, 12, 4], "uv": [16, 16], "inflate": 0.5}]},
            {"name": "rightLeg", "pivot": [-1.9, 12.0, 0.0], "cubes": [{"origin": [-3.9, 0.0, -2.0], "size": [4, 12, 4], "uv": [0, 16], "inflate": 0.49}], "parent": "body"},
            {"name": "leftLeg", "pivot": [1.9, 12.0, 0.0], "cubes": [{"origin": [-0.1, 0.0, -2.0], "size": [4, 12, 4], "uv": [0, 16], "inflate": 0.49}], "mirror": True, "parent": "body"}
        ]
    },
    "geometry.humanoid.armor.boots": {
        "visible_bounds_width": 2,
        "visible_bounds_height": 2,
        "visible_bounds_offset": [0, 1, 0],
        "texturewidth": 64,
        "textureheight": 32,
        "bones": [
            {"name": "rightLeg", "pivot": [-1.9, 12.0, 0.0], "cubes": [{"origin": [-3.9, 0.0, -2.0], "size": [4, 12, 4], "uv": [0, 16], "inflate": 1.0}]},
            {"name": "leftLeg", "pivot": [1.9, 12.0, 0.0], "cubes": [{"origin": [-0.1, 0.0, -2.0], "size": [4, 12, 4], "uv": [0, 16], "inflate": 1.0}], "mirror": True}
        ]
    }
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


KNOWN_ARMOR_HEX_COLORS = {
    "ruby": (255, 0, 0),
    "bronze": (211, 104, 35),
    "dark_amethyst": (83, 7, 102),
    "obsidian": (78, 63, 124),
    "mysterious": (87, 14, 17),
}


def process_bedrock_armor_texture(
    src_path: Path,
    dest_path: Path,
    model: ParsedJavaModel,
) -> None:
    """Normalize and tint armor layer texture for Bedrock's standard 2:1 armor UV mapping."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with Image.open(src_path) as raw:
            im = raw.convert("RGBA")
            w, h = im.size

            # If texture has 4:1 ratio (e.g. 128x32), split side-by-side frames (base and overlay)
            if w == h * 4:
                frame_w = w // 2
                f1 = im.crop((0, 0, frame_w, h))
                f2 = im.crop((frame_w, 0, w, h))

                tint_color = None
                for name, rgb in KNOWN_ARMOR_HEX_COLORS.items():
                    if name in model.short_name:
                        tint_color = rgb
                        break

                if tint_color:
                    r, g, b = tint_color
                    tinted_f1 = Image.new("RGBA", f1.size)
                    tinted_pixels = []
                    for p in f1.getdata():
                        if p[3] > 0:
                            gray = (p[0] + p[1] + p[2]) // 3
                            nr = int((gray / 255.0) * r)
                            ng = int((gray / 255.0) * g)
                            nb = int((gray / 255.0) * b)
                            tinted_pixels.append((nr, ng, nb, p[3]))
                        else:
                            tinted_pixels.append((0, 0, 0, 0))
                    tinted_f1.putdata(tinted_pixels)
                    out = Image.alpha_composite(tinted_f1, f2)
                else:
                    out = Image.alpha_composite(f1, f2)

                out.save(dest_path)
                return

            im.save(dest_path)
    except Exception:
        shutil.copy2(src_path, dest_path)

