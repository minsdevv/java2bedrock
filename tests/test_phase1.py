"""Unit and integration tests for Phase 1: Core Item Converter (2D/3D, 26.3 + Legacy)."""

import json
from pathlib import Path
import zipfile

from PIL import Image

from src.packager.zip_packager import convert_java_pack


def _create_dummy_png(path: Path, size: tuple[int, int] = (16, 16), color: tuple[int, int, int, int] = (255, 50, 50, 255)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGBA", size, color)
    img.save(path)


def _create_sample_java_pack(pack_dir: Path) -> Path:
    """Create a realistic Java Resource Pack containing both 26.3 and Legacy items."""
    pack_dir.mkdir(parents=True, exist_ok=True)

    # 1. pack.mcmeta (Format 46 for 1.21.4 / 26.x)
    mcmeta = {
        "pack": {
            "pack_format": 46,
            "supported_formats": [34, 60],
            "description": {"text": "Sample 26.3 & Nexo Resource Pack"},
        }
    }
    (pack_dir / "pack.mcmeta").write_text(json.dumps(mcmeta, indent=2), encoding="utf-8")

    # 2. Modern 26.3 Item Definition: assets/minecraft/items/diamond_sword.json
    modern_sword_def = {
        "model": {
            "type": "minecraft:range_dispatch",
            "property": "minecraft:custom_model_data",
            "index": 0,
            "entries": [
                {
                    "threshold": 1001.0,
                    "model": {
                        "type": "minecraft:model",
                        "model": "nexo:item/ruby_katana",
                    },
                },
                {
                    "threshold": 1002.0,
                    "model": {
                        "type": "minecraft:model",
                        "model": "nexo:item/emerald_dagger",
                    },
                },
            ],
            "fallback": {
                "type": "minecraft:model",
                "model": "minecraft:item/diamond_sword",
            },
        }
    }
    sword_item_path = pack_dir / "assets" / "minecraft" / "items" / "diamond_sword.json"
    sword_item_path.parent.mkdir(parents=True, exist_ok=True)
    sword_item_path.write_text(json.dumps(modern_sword_def, indent=2), encoding="utf-8")

    # 3. 3D Model: assets/nexo/models/item/ruby_katana.json
    ruby_katana_model = {
        "credit": "Made with Blockbench",
        "textures": {
            "0": "nexo:item/ruby_katana",
            "particle": "#0",
        },
        "elements": [
            {
                "name": "hilt",
                "from": [7.5, 0.0, 7.5],
                "to": [8.5, 4.0, 8.5],
                "faces": {
                    "north": {"uv": [0, 0, 2, 8], "texture": "#0"},
                    "east": {"uv": [2, 0, 4, 8], "texture": "#0"},
                    "south": {"uv": [4, 0, 6, 8], "texture": "#0"},
                    "west": {"uv": [6, 0, 8, 8], "texture": "#0"},
                    "up": {"uv": [0, 8, 2, 10], "texture": "#0"},
                    "down": {"uv": [2, 8, 4, 10], "texture": "#0"},
                },
            },
            {
                "name": "blade_angled",
                "from": [7.75, 4.0, 7.0],
                "to": [8.25, 16.0, 9.0],
                "rotation": {"angle": 22.5, "axis": "x", "origin": [8.0, 4.0, 8.0]},
                "faces": {
                    "north": {"uv": [8, 0, 9, 16], "texture": "#0"},
                    "east": {"uv": [9, 0, 13, 16], "texture": "#0"},
                    "south": {"uv": [13, 0, 14, 16], "texture": "#0"},
                    "west": {"uv": [9, 0, 13, 16], "texture": "#0"},
                },
            },
        ],
        "display": {
            "thirdperson_righthand": {
                "rotation": [0, -90, 55],
                "translation": [0, 4.0, 0.5],
                "scale": [0.85, 0.85, 0.85],
            },
            "firstperson_righthand": {
                "rotation": [0, -90, 25],
                "translation": [1.13, 3.2, 1.13],
                "scale": [0.68, 0.68, 0.68],
            },
        },
    }
    katana_model_path = pack_dir / "assets" / "nexo" / "models" / "item" / "ruby_katana.json"
    katana_model_path.parent.mkdir(parents=True, exist_ok=True)
    katana_model_path.write_text(json.dumps(ruby_katana_model, indent=2), encoding="utf-8")
    _create_dummy_png(pack_dir / "assets" / "nexo" / "textures" / "item" / "ruby_katana.png", (32, 32))

    # 4. 2D Model: assets/nexo/models/item/emerald_dagger.json
    emerald_dagger_model = {
        "parent": "minecraft:item/handheld",
        "textures": {
            "layer0": "nexo:item/emerald_dagger",
        },
    }
    dagger_model_path = pack_dir / "assets" / "nexo" / "models" / "item" / "emerald_dagger.json"
    dagger_model_path.write_text(json.dumps(emerald_dagger_model, indent=2), encoding="utf-8")
    _create_dummy_png(pack_dir / "assets" / "nexo" / "textures" / "item" / "emerald_dagger.png", (16, 16), (50, 255, 50, 255))

    # 5. Legacy 1.14 - 1.21.1 Override: assets/minecraft/models/item/paper.json
    legacy_paper = {
        "parent": "minecraft:item/generated",
        "textures": {"layer0": "minecraft:item/paper"},
        "overrides": [
            {
                "predicate": {"custom_model_data": 5001},
                "model": "nexo:item/magic_scroll",
            }
        ],
    }
    paper_path = pack_dir / "assets" / "minecraft" / "models" / "item" / "paper.json"
    paper_path.parent.mkdir(parents=True, exist_ok=True)
    paper_path.write_text(json.dumps(legacy_paper, indent=2), encoding="utf-8")

    scroll_model = {
        "parent": "minecraft:item/generated",
        "textures": {"layer0": "nexo:item/magic_scroll"},
    }
    (pack_dir / "assets" / "nexo" / "models" / "item" / "magic_scroll.json").write_text(
        json.dumps(scroll_model, indent=2), encoding="utf-8"
    )
    _create_dummy_png(pack_dir / "assets" / "nexo" / "textures" / "item" / "magic_scroll.png", (16, 16), (255, 220, 100, 255))

    return pack_dir


def test_phase1_full_conversion(tmp_path: Path) -> None:
    src_pack = _create_sample_java_pack(tmp_path / "sample_java_pack")
    out_dir = tmp_path / "output"

    res = convert_java_pack(
        input_path=src_pack,
        output_dir=out_dir,
        pack_name="Test263Pack",
        bedrock_ns="j2b",
    )

    assert res.total_items == 3
    assert res.items_3d == 1
    assert res.items_2d == 2
    assert res.mcpack_path.is_file()
    assert res.mappings_v2_path.is_file()
    assert res.mappings_v1_path.is_file()

    # Check Geyser v2 Mappings (Minecraft 26.3 compatible)
    v2_data = json.loads(res.mappings_v2_path.read_text(encoding="utf-8"))
    assert v2_data["format_version"] == 2
    assert "minecraft:diamond_sword" in v2_data["items"]
    assert "minecraft:paper" in v2_data["items"]

    sword_defs = v2_data["items"]["minecraft:diamond_sword"]
    assert len(sword_defs) == 2
    katana_def = next(d for d in sword_defs if "ruby_katana" in d["bedrock_identifier"])
    assert katana_def["model"] == "minecraft:diamond_sword"
    assert katana_def["predicate"][0]["type"] == "range_dispatch"
    assert katana_def["predicate"][0]["threshold"] == 1001.0
    assert katana_def["bedrock_options"]["display_handheld"] is True

    # Check Bedrock 3D Geometry (.geo.json)
    with zipfile.ZipFile(res.mcpack_path, "r") as zf:
        namelist = zf.namelist()
        assert "manifest.json" in namelist
        assert "textures/item_texture.json" in namelist
        geo_files = [n for n in namelist if n.endswith(".geo.json")]
        assert len(geo_files) == 1
        geo_json = json.loads(zf.read(geo_files[0]).decode("utf-8"))
        assert geo_json["format_version"] == "1.16.0"
        bones = geo_json["minecraft:geometry"][0]["bones"]
        # Root + x/y/z display bones + 1 rotated bone (blade_angled, parented to z)
        assert [b["name"] for b in bones[:4]] == ["root_item", "root_item_x", "root_item_y", "root_item_z"]
        assert len(bones) == 5
        assert bones[4]["name"] == "bone_rot_1"
        assert bones[4]["parent"] == "root_item_z"
        assert bones[4]["rotation"] == [-22.5, 0.0, 0.0]


import tempfile
import unittest


class TestPhase1Unittest(unittest.TestCase):
    def test_conversion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            test_phase1_full_conversion(Path(tmp))


if __name__ == "__main__":
    unittest.main()

