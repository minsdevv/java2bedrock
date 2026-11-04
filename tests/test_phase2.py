"""Unit tests for Phase 2: Texture Atlas Stitcher, Tintindex Compositor & Custom Armor."""

import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from src.packager.zip_packager import convert_java_pack


def _create_phase2_mock_pack(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pack.mcmeta").write_text(
        json.dumps({"pack": {"pack_format": 55, "description": "Phase 2 Pack"}}),
        encoding="utf-8",
    )

    # 1. Multi-texture 3D Hammer (2 separate 16x16 PNGs: head.png and handle.png)
    tex_item_dir = root / "assets" / "nexo" / "textures" / "item"
    tex_item_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (16, 16), (200, 50, 50, 255)).save(tex_item_dir / "hammer_head.png")
    Image.new("RGBA", (16, 16), (100, 70, 30, 255)).save(tex_item_dir / "hammer_handle.png")

    items_dir = root / "assets" / "minecraft" / "items"
    items_dir.mkdir(parents=True, exist_ok=True)
    (items_dir / "mace.json").write_text(
        json.dumps(
            {
                "model": {
                    "type": "minecraft:range_dispatch",
                    "property": "minecraft:custom_model_data",
                    "entries": [
                        {
                            "threshold": 10,
                            "model": {
                                "type": "minecraft:model",
                                "model": "nexo:item/war_hammer",
                            },
                        }
                    ],
                }
            }
        ),
        encoding="utf-8",
    )

    model_dir = root / "assets" / "nexo" / "models" / "item"
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "war_hammer.json").write_text(
        json.dumps(
            {
                "textures": {
                    "0": "nexo:item/hammer_head",
                    "1": "nexo:item/hammer_handle",
                },
                "elements": [
                    {
                        "name": "head",
                        "from": [4, 10, 4],
                        "to": [12, 15, 12],
                        "faces": {
                            "north": {"uv": [0, 0, 8, 5], "texture": "#0"},
                            "south": {"uv": [0, 0, 8, 5], "texture": "#0"},
                        },
                    },
                    {
                        "name": "handle",
                        "from": [7, 0, 7],
                        "to": [9, 10, 9],
                        "faces": {
                            "north": {"uv": [0, 0, 2, 10], "texture": "#1"},
                            "south": {"uv": [0, 0, 2, 10], "texture": "#1"},
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    # 2. Tinted 2D Potion / Leaf item (white base texture + green tint 0x00FF00)
    Image.new("RGBA", (16, 16), (255, 255, 255, 255)).save(tex_item_dir / "magic_leaf_base.png")
    (items_dir / "potion.json").write_text(
        json.dumps(
            {
                "model": {
                    "type": "minecraft:range_dispatch",
                    "property": "minecraft:custom_model_data",
                    "entries": [
                        {
                            "threshold": 5,
                            "model": {
                                "type": "minecraft:model",
                                "model": "nexo:item/magic_leaf",
                                "tints": [
                                    {
                                        "type": "minecraft:constant",
                                        "value": 0x00FF00,
                                    }
                                ],
                            },
                        }
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    (model_dir / "magic_leaf.json").write_text(
        json.dumps(
            {
                "parent": "minecraft:item/generated",
                "textures": {"layer0": "nexo:item/magic_leaf_base"},
            }
        ),
        encoding="utf-8",
    )

    # 3. Minecraft 26.3 Custom Armor Helmet (equipment/emerald.json + diamond_helmet override)
    Image.new("RGBA", (16, 16), (0, 200, 100, 255)).save(tex_item_dir / "emerald_helmet.png")
    eq_tex_dir = root / "assets" / "nexo" / "textures" / "entity" / "equipment" / "humanoid"
    eq_tex_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (64, 32), (0, 220, 110, 255)).save(eq_tex_dir / "emerald.png")

    eq_json_dir = root / "assets" / "nexo" / "equipment"
    eq_json_dir.mkdir(parents=True, exist_ok=True)
    (eq_json_dir / "emerald.json").write_text(
        json.dumps(
            {
                "layers": {
                    "humanoid": [{"texture": "nexo:emerald"}],
                    "humanoid_leggings": [{"texture": "nexo:emerald"}],
                }
            }
        ),
        encoding="utf-8",
    )

    (items_dir / "diamond_helmet.json").write_text(
        json.dumps(
            {
                "model": {
                    "type": "minecraft:range_dispatch",
                    "property": "minecraft:custom_model_data",
                    "entries": [
                        {
                            "threshold": 77,
                            "model": {
                                "type": "minecraft:model",
                                "model": "nexo:item/emerald_helmet",
                            },
                        }
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    (model_dir / "emerald_helmet.json").write_text(
        json.dumps(
            {
                "parent": "minecraft:item/generated",
                "textures": {"layer0": "nexo:item/emerald_helmet"},
            }
        ),
        encoding="utf-8",
    )


class TestPhase2(unittest.TestCase):
    def test_atlas_tint_and_armor_conversion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pack_dir = tmp_path / "phase2_pack"
            out_dir = tmp_path / "out"
            _create_phase2_mock_pack(pack_dir)

            res = convert_java_pack(pack_dir, out_dir, bedrock_ns="j2b")
            self.assertEqual(res.total_items, 3)

            # 1. Verify 3D hammer atlas is 32x16 and handle UV is shifted by +16 on X
            hammer_model_tex = res.bedrock_pack_dir / "textures" / "models" / "entity" / "j2b" / "nexo_war_hammer_10.png"
            with Image.open(hammer_model_tex) as im:
                self.assertEqual(im.size, (32, 16))

            # Verify isometric GUI icon was generated at 32x32
            hammer_gui_icon = res.bedrock_pack_dir / "textures" / "items" / "j2b" / "nexo_war_hammer_10.png"
            with Image.open(hammer_gui_icon) as im:
                self.assertEqual(im.size, (32, 32))

            hammer_geo = json.loads(
                (res.bedrock_pack_dir / "models" / "entity" / "j2b" / "nexo_war_hammer_10.geo.json").read_text(
                    encoding="utf-8"
                )
            )
            geo_desc = hammer_geo["minecraft:geometry"][0]["description"]
            self.assertEqual(geo_desc["texture_width"], 32)
            self.assertEqual(geo_desc["texture_height"], 16)
            bones = hammer_geo["minecraft:geometry"][0]["bones"]
            handle_cube = bones[0]["cubes"][1]
            north_uv = handle_cube["uv"]["north"]["uv"]
            self.assertEqual(north_uv[0], 16.0)

            # 2. Verify 2D leaf tinting multiplied white (255,255,255) by (0,255,0)
            leaf_tex = res.bedrock_pack_dir / "textures" / "items" / "j2b" / "nexo_magic_leaf_5.png"
            with Image.open(leaf_tex) as im:
                px = im.convert("RGBA").getpixel((8, 8))
                self.assertEqual(px, (0, 255, 0, 255))

            # 3. Verify 26.3 Armor attachable & Geyser v2 equippable component
            armor_attach_path = res.bedrock_pack_dir / "attachables" / "j2b" / "nexo_emerald_helmet_77.json"
            self.assertTrue(armor_attach_path.is_file())
            armor_attach = json.loads(armor_attach_path.read_text(encoding="utf-8"))
            desc = armor_attach["minecraft:attachable"]["description"]
            self.assertEqual(desc["geometry"]["default"], "geometry.humanoid.armor.helmet")
            self.assertEqual(desc["scripts"]["parent_setup"], "v.helmet_layer_visible = 0.0;")

            v2_data = json.loads(res.mappings_v2_path.read_text(encoding="utf-8"))
            helmet_def = v2_data["items"]["minecraft:diamond_helmet"][0]
            self.assertEqual(
                helmet_def["components"]["minecraft:equippable"],
                {"slot": "head"},
            )


if __name__ == "__main__":
    unittest.main()
