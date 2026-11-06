"""Unit tests for dyeable and tinted models."""

import unittest
from PIL import Image

from src.converter.texture_processor import (
    apply_rgb_tint,
    extract_tint_rgb_for_index,
    int_color_to_rgb,
)
from src.parser.item_parser import ParsedJavaModel


class TestTintProcessor(unittest.TestCase):
    def test_int_color_conversions(self):
        # Hex 0xFF0000 = Red
        self.assertEqual(int_color_to_rgb(0xFF0000), (255, 0, 0))
        # Negative signed 32-bit int
        self.assertEqual(int_color_to_rgb(-65536), (255, 0, 0))

    def test_extract_tint_from_tints_list(self):
        tints = [
            {"type": "constant", "value": 0x00FF00},
            {"type": "minecraft:dye", "default": 0x0000FF},
        ]
        self.assertEqual(extract_tint_rgb_for_index(tints, 0), (0, 255, 0))
        self.assertEqual(extract_tint_rgb_for_index(tints, 1), (0, 0, 255))
        self.assertIsNone(extract_tint_rgb_for_index(tints, 2))

    def test_apply_rgb_tint_multiplication(self):
        im = Image.new("RGBA", (2, 2), (255, 255, 255, 255))
        tinted = apply_rgb_tint(im, (255, 0, 0))
        self.assertEqual(tinted.getpixel((0, 0)), (255, 0, 0, 255))


if __name__ == "__main__":
    unittest.main()
