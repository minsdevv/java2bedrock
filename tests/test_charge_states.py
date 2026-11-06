"""Unit tests for bow pulling and crossbow charged state overrides."""

import json
from pathlib import Path
import tempfile
import unittest

from src.mappings.geyser_mappings import build_geyser_item_mappings_v2
from src.parser.item_parser import parse_java_pack_items


class TestChargeStates(unittest.TestCase):
    def test_bow_pulling_states_parsed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            item_models = root / "assets" / "minecraft" / "models" / "item"
            custom_models = root / "assets" / "custom" / "models" / "item"
            textures_dir = root / "assets" / "custom" / "textures" / "item"
            item_models.mkdir(parents=True, exist_ok=True)
            custom_models.mkdir(parents=True, exist_ok=True)
            textures_dir.mkdir(parents=True, exist_ok=True)

            # Dummy texture
            (textures_dir / "bow.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")

            # Vanilla bow item override
            (item_models / "bow.json").write_text(
                json.dumps({
                    "parent": "item/generated",
                    "overrides": [
                        {"predicate": {"custom_model_data": 501}, "model": "custom:item/dragon_bow"},
                        {"predicate": {"custom_model_data": 501, "pulling": 1}, "model": "custom:item/dragon_bow_pull_0"},
                        {"predicate": {"custom_model_data": 501, "pulling": 1, "pull": 0.65}, "model": "custom:item/dragon_bow_pull_1"},
                        {"predicate": {"custom_model_data": 501, "pulling": 1, "pull": 0.9}, "model": "custom:item/dragon_bow_pull_2"},
                    ],
                }),
                encoding="utf-8",
            )

            for name in ["dragon_bow", "dragon_bow_pull_0", "dragon_bow_pull_1", "dragon_bow_pull_2"]:
                (custom_models / f"{name}.json").write_text(
                    json.dumps({
                        "parent": "item/handheld",
                        "textures": {"layer0": "custom:item/bow"},
                    }),
                    encoding="utf-8",
                )

            models = parse_java_pack_items(root, bedrock_ns="j2b")
            bow_models = [m for m in models if m.custom_model_data_int == 501]
            # Should have all 4 states: idle + pulling 0, 1, 2
            self.assertEqual(len(bow_models), 4)

            # Test Geyser v2 mappings output
            v2 = build_geyser_item_mappings_v2(bow_models)
            defs = v2["items"]["minecraft:bow"]
            self.assertEqual(len(defs), 4)

            # Check pulling_2 has both pulling condition and pull range_dispatch
            pull2_def = next(d for d in defs if "dragon_bow_pull_2" in d["bedrock_identifier"])
            preds = pull2_def["predicate"]
            props = [p["property"] for p in preds]
            self.assertIn("custom_model_data", props)
            self.assertIn("pulling", props)
            self.assertIn("pull", props)

    def test_bow_attachable_generation(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            item_models = root / "assets" / "minecraft" / "models" / "item"
            custom_models = root / "assets" / "custom" / "models" / "item"
            textures_dir = root / "assets" / "custom" / "textures" / "item"
            item_models.mkdir(parents=True, exist_ok=True)
            custom_models.mkdir(parents=True, exist_ok=True)
            textures_dir.mkdir(parents=True, exist_ok=True)

            Image.new("RGBA", (16, 16), (255, 0, 0, 255)).save(textures_dir / "bow.png")

            (item_models / "bow.json").write_text(
                json.dumps({
                    "parent": "item/generated",
                    "overrides": [
                        {"predicate": {"custom_model_data": 777}, "model": "custom:item/magic_bow"},
                        {"predicate": {"custom_model_data": 777, "pulling": 1}, "model": "custom:item/magic_bow_pull_0"},
                        {"predicate": {"custom_model_data": 777, "pulling": 1, "pull": 0.65}, "model": "custom:item/magic_bow_pull_1"},
                        {"predicate": {"custom_model_data": 777, "pulling": 1, "pull": 0.9}, "model": "custom:item/magic_bow_pull_2"},
                    ],
                }),
                encoding="utf-8",
            )
            for name in ["magic_bow", "magic_bow_pull_0", "magic_bow_pull_1", "magic_bow_pull_2"]:
                (custom_models / f"{name}.json").write_text(
                    json.dumps({
                        "parent": "item/handheld",
                        "textures": {"layer0": "custom:item/bow"},
                    }),
                    encoding="utf-8",
                )

            (root / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 15, "description": "Test"}}))

            from src.packager.zip_packager import convert_java_pack
            out = root / "output"
            convert_java_pack(root, out, pack_name="TestBow")

            att_file = out / "TestBow_bedrock" / "attachables" / "j2b" / "custom_magic_bow_777.json"
            self.assertTrue(att_file.is_file(), "Bow attachable should be generated")
            att = json.loads(att_file.read_text(encoding="utf-8"))["minecraft:attachable"]["description"]
            self.assertEqual(att["render_controllers"], ["controller.render.item_default"])
            self.assertIn("bow_pulling_0", att["textures"])
            self.assertIn("bow_pulling_1", att["textures"])
            self.assertIn("bow_pulling_2", att["textures"])
            self.assertEqual(att["geometry"]["default"], "geometry.bow_standby")
            self.assertEqual(att["geometry"]["bow_pulling_2"], "geometry.bow_pulling_2")
            self.assertIn("wield", att["animations"])
            self.assertIn("wield_first_person_pull", att["animations"])


if __name__ == "__main__":
    unittest.main()
