"""Unit tests for Bedrock flipbook_textures.json builder from Java .mcmeta."""

import json
from pathlib import Path
import tempfile
import unittest

from src.converter.flipbook_builder import build_flipbook_entry, parse_mcmeta_animation


class TestFlipbookBuilder(unittest.TestCase):
    def test_parse_simple_frametime(self):
        with tempfile.TemporaryDirectory() as td:
            meta = Path(td) / "test.png.mcmeta"
            meta.write_text(json.dumps({"animation": {"frametime": 4, "interpolate": True}}), encoding="utf-8")
            params = parse_mcmeta_animation(meta)
            self.assertIsNotNone(params)
            self.assertEqual(params["ticks_per_frame"], 4)
            self.assertTrue(params["blend_frames"])
            self.assertIsNone(params["frames"])

            entry = build_flipbook_entry("textures/items/j2b/test.png", "j2b_test", params)
            self.assertEqual(entry["flipbook_texture"], "textures/items/j2b/test")
            self.assertEqual(entry["atlas_tile"], "j2b_test")
            self.assertEqual(entry["ticks_per_frame"], 4)
            self.assertTrue(entry["blend_frames"])

    def test_parse_custom_frame_objects(self):
        with tempfile.TemporaryDirectory() as td:
            meta = Path(td) / "ore.png.mcmeta"
            meta.write_text(
                json.dumps({
                    "animation": {
                        "interpolate": True,
                        "frames": [{"index": 0, "time": 8}, {"index": 1, "time": 8}, {"index": 2, "time": 8}],
                    }
                }),
                encoding="utf-8",
            )
            params = parse_mcmeta_animation(meta)
            self.assertIsNotNone(params)
            self.assertEqual(params["ticks_per_frame"], 8)
            self.assertEqual(params["frames"], [0, 1, 2])


if __name__ == "__main__":
    unittest.main()
