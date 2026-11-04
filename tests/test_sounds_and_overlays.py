"""Tests for Sound Conversion and Bedrock Pack Overlay Merging."""

import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from src.converter.sound_converter import convert_java_pack_sounds
from src.packager.zip_packager import convert_java_pack, merge_bedrock_overlay


class TestSoundsAndOverlays(unittest.TestCase):
    def test_sound_conversion(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            # Create mock java pack with sounds.json and .ogg
            sounds_dir = td_path / "assets" / "custom_ns" / "sounds" / "item"
            sounds_dir.mkdir(parents=True)
            (sounds_dir / "laser.ogg").write_bytes(b"OggS mock audio data")

            sounds_json = td_path / "assets" / "custom_ns" / "sounds.json"
            sounds_json.write_text(
                json.dumps(
                    {
                        "item.laser": {
                            "category": "player",
                            "sounds": ["custom_ns:item/laser"],
                        }
                    }
                ),
                encoding="utf-8",
            )

            bedrock_dir = td_path / "bedrock_out"
            copied, warnings = convert_java_pack_sounds(td_path, bedrock_dir)
            self.assertEqual(copied, 1)
            self.assertEqual(len(warnings), 0)

            # Check sound_definitions.json
            sound_defs_path = bedrock_dir / "sounds" / "sound_definitions.json"
            self.assertTrue(sound_defs_path.is_file())
            data = json.loads(sound_defs_path.read_text(encoding="utf-8"))
            self.assertIn("custom_ns.item.laser", data["sound_definitions"])
            def_obj = data["sound_definitions"]["custom_ns.item.laser"]
            self.assertEqual(def_obj["category"], "player")
            self.assertEqual(def_obj["sounds"][0]["name"], "sounds/custom_ns/item/laser")

            # Check copied audio file
            copied_file = bedrock_dir / "sounds" / "custom_ns" / "item" / "laser.ogg"
            self.assertTrue(copied_file.is_file())

    def test_bedrock_overlay_merging(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bedrock_target = td_path / "target_pack"
            bedrock_target.mkdir()

            # Existing item_texture.json
            tex_dir = bedrock_target / "textures"
            tex_dir.mkdir()
            (tex_dir / "item_texture.json").write_text(
                json.dumps({"texture_data": {"item_a": {"textures": "textures/items/a"}}}),
                encoding="utf-8",
            )

            # User overlay pack containing UI file, language text, and extra item texture
            overlay_dir = td_path / "user_overlay"
            (overlay_dir / "ui").mkdir(parents=True)
            (overlay_dir / "ui" / "chest_screen.json").write_text('{"custom_ui": true}', encoding="utf-8")

            (overlay_dir / "texts").mkdir(parents=True)
            (overlay_dir / "texts" / "en_US.lang").write_text("menu.title=Mins Network", encoding="utf-8")

            (overlay_dir / "textures").mkdir(parents=True)
            (overlay_dir / "textures" / "item_texture.json").write_text(
                json.dumps({"texture_data": {"user_item": {"textures": "textures/items/user"}}}),
                encoding="utf-8",
            )

            warns = merge_bedrock_overlay(overlay_dir, bedrock_target)
            self.assertEqual(len(warns), 0)

            # Verify files were merged
            self.assertTrue((bedrock_target / "ui" / "chest_screen.json").is_file())
            self.assertTrue((bedrock_target / "texts" / "en_US.lang").is_file())

            # Verify deep merge of item_texture.json
            merged_tex = json.loads((bedrock_target / "textures" / "item_texture.json").read_text(encoding="utf-8"))
            self.assertIn("item_a", merged_tex["texture_data"])
            self.assertIn("user_item", merged_tex["texture_data"])


if __name__ == "__main__":
    unittest.main()
