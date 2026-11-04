"""Unit tests for Phase 3: Custom Blocks & Display Furniture."""

import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from src.packager.zip_packager import convert_java_pack


def _create_phase3_mock_pack(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pack.mcmeta").write_text(
        json.dumps({"pack": {"pack_format": 55, "description": "Phase 3 Pack"}}),
        encoding="utf-8",
    )

    # Textures for custom blocks and furniture
    blk_tex_dir = root / "assets" / "nexo" / "textures" / "block"
    blk_tex_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (16, 16), (220, 20, 60, 255)).save(blk_tex_dir / "ruby_ore.png")
    Image.new("RGBA", (16, 16), (100, 220, 255, 255)).save(blk_tex_dir / "crystal_lantern.png")

    furn_tex_dir = root / "assets" / "nexo" / "textures" / "furniture"
    furn_tex_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (16, 16), (139, 90, 43, 255)).save(furn_tex_dir / "oak_chair.png")

    # 1. Custom Block Models (1 unit cube, 1 3D custom geometry)
    blk_model_dir = root / "assets" / "nexo" / "models" / "block"
    blk_model_dir.mkdir(parents=True, exist_ok=True)
    (blk_model_dir / "ruby_ore.json").write_text(
        json.dumps(
            {
                "parent": "minecraft:block/cube_all",
                "textures": {"all": "nexo:block/ruby_ore"},
            }
        ),
        encoding="utf-8",
    )
    (blk_model_dir / "crystal_lantern.json").write_text(
        json.dumps(
            {
                "textures": {"0": "nexo:block/crystal_lantern"},
                "elements": [
                    {
                        "from": [4, 0, 4],
                        "to": [12, 14, 12],
                        "faces": {
                            "north": {"uv": [0, 0, 8, 14], "texture": "#0"},
                            "south": {"uv": [0, 0, 8, 14], "texture": "#0"},
                            "east": {"uv": [0, 0, 8, 14], "texture": "#0"},
                            "west": {"uv": [0, 0, 8, 14], "texture": "#0"},
                            "up": {"uv": [0, 0, 8, 8], "texture": "#0"},
                            "down": {"uv": [0, 0, 8, 8], "texture": "#0"},
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    # NoteBlock blockstates
    bs_dir = root / "assets" / "minecraft" / "blockstates"
    bs_dir.mkdir(parents=True, exist_ok=True)
    (bs_dir / "note_block.json").write_text(
        json.dumps(
            {
                "variants": {
                    "instrument=harp,note=1,powered=false": {
                        "model": "nexo:block/ruby_ore",
                    },
                    "instrument=harp,note=2,powered=false": {
                        "model": "nexo:block/crystal_lantern",
                        "y": 90,
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    # 2. Display Furniture Model + furniture.json
    furn_model_dir = root / "assets" / "nexo" / "models" / "furniture"
    furn_model_dir.mkdir(parents=True, exist_ok=True)
    (furn_model_dir / "oak_chair.json").write_text(
        json.dumps(
            {
                "textures": {"0": "nexo:furniture/oak_chair"},
                "elements": [
                    {
                        "name": "seat",
                        "from": [2, 6, 2],
                        "to": [14, 8, 14],
                        "faces": {
                            "up": {"uv": [0, 0, 12, 12], "texture": "#0"},
                            "north": {"uv": [0, 0, 12, 2], "texture": "#0"},
                        },
                    },
                    {
                        "name": "backrest",
                        "from": [2, 8, 12],
                        "to": [14, 20, 14],
                        "faces": {
                            "north": {"uv": [0, 0, 12, 12], "texture": "#0"},
                            "south": {"uv": [0, 0, 12, 12], "texture": "#0"},
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (root / "furniture.json").write_text(
        json.dumps(
            {
                "furniture": {
                    "nexo:oak_chair": {
                        "model": "nexo:furniture/oak_chair",
                        "item": "minecraft:paper",
                        "custom_model_data": 3001,
                        "hitbox": {"width": 0.9, "height": 1.25},
                        "seat_height": 0.5,
                    }
                }
            }
        ),
        encoding="utf-8",
    )


class TestPhase3(unittest.TestCase):
    def test_blocks_and_furniture_conversion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pack_dir = tmp_path / "phase3_pack"
            out_dir = tmp_path / "out"
            _create_phase3_mock_pack(pack_dir)

            res = convert_java_pack(pack_dir, out_dir, bedrock_ns="j2b")
            self.assertEqual(res.total_blocks, 2)
            self.assertEqual(res.total_furniture, 1)
            self.assertIsNotNone(res.block_mappings_path)
            self.assertIsNotNone(res.furniture_registry_path)

            # Verify Bedrock blocks.json & terrain_texture.json
            blocks_json = json.loads(
                (res.bedrock_pack_dir / "blocks.json").read_text(encoding="utf-8")
            )
            self.assertIn("j2b:block_nexo_ruby_ore", blocks_json)
            self.assertIn("j2b:block_nexo_crystal_lantern", blocks_json)

            # Verify 3D block geometry generated for crystal_lantern
            lantern_geo_path = (
                res.bedrock_pack_dir
                / "models"
                / "blocks"
                / "j2b"
                / "nexo_crystal_lantern.geo.json"
            )
            self.assertTrue(lantern_geo_path.is_file())

            # Verify Geyser custom_mappings/blocks.json (BlockMappingsReader_v1 schema)
            geyser_blocks = json.loads(
                res.block_mappings_path.read_text(encoding="utf-8")
            )
            self.assertEqual(geyser_blocks["format_version"], 1)
            nb_entry = geyser_blocks["blocks"]["minecraft:note_block"]
            self.assertTrue(nb_entry["only_override_states"])
            overrides = nb_entry["state_overrides"]
            self.assertTrue(
                overrides["instrument=harp,note=1,powered=false"]["unit_cube"]
            )
            self.assertEqual(
                overrides["instrument=harp,note=2,powered=false"]["geometry"],
                "geometry.j2b.block_nexo_crystal_lantern",
            )
            self.assertEqual(
                overrides["instrument=harp,note=2,powered=false"]["transformation"][
                    "rotation"
                ],
                [0, 90, 0],
            )

            # Verify Furniture entity & registry
            furn_entity_path = (
                res.bedrock_pack_dir
                / "entity"
                / "furniture"
                / "nexo_furniture_oak_chair.entity.json"
            )
            self.assertTrue(furn_entity_path.is_file())
            furn_reg = json.loads(
                res.furniture_registry_path.read_text(encoding="utf-8")
            )
            self.assertEqual(len(furn_reg["furniture"]), 1)
            self.assertEqual(furn_reg["furniture"][0]["custom_model_data"], 3001)
            self.assertEqual(furn_reg["furniture"][0]["seat_height"], 0.5)


if __name__ == "__main__":
    unittest.main()
