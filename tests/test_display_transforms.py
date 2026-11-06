"""Display-transform and icon-size regression tests."""

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from src.converter.attachable_builder import build_bedrock_attachable
from src.converter.math_utils import build_display_animation
from src.packager.zip_packager import _upscale_icon


class TestDisplayAnimation(unittest.TestCase):
    def test_hand_pose_and_axis_split(self):
        disp = {"thirdperson_righthand": {"rotation": [10, 20, 30], "translation": [1, 2, 3], "scale": [0.5, 0.5, 0.5]}}
        doc, amap = build_display_animation("sword", disp)
        b = doc["animations"][amap["third_person"]]["bones"]
        self.assertEqual(b["root_item"]["rotation"], [90, 0, 0])
        self.assertEqual(b["root_item_x"]["rotation"], [-10.0, 0, 0])
        self.assertEqual(b["root_item_x"]["position"], [-1.0, 2.0, 3.0])
        self.assertEqual(b["root_item_y"]["rotation"], [0, -20.0, 0])
        self.assertEqual(b["root_item_z"]["rotation"], [0, 0, 30.0])

    def test_head_uses_block_scale_factor(self):
        disp = {"head": {"translation": [0, 16, -8], "scale": [2.0, 2.0, 2.0]}}
        doc, amap = build_display_animation("fridge", disp)
        x = doc["animations"][amap["head"]]["bones"]["root_item_x"]
        self.assertEqual(x["scale"], [1.25, 1.25, 1.25])
        self.assertEqual(x["position"], [-0.0, 10.0, -5.0])

    def test_head_without_display_defaults(self):
        doc, amap = build_display_animation("hat", {})
        self.assertEqual(doc["animations"][amap["head"]]["bones"]["root_item_x"]["scale"], 0.625)

    def test_attachable_slot_variables(self):
        class M:
            short_name = "x"
            bedrock_identifier = "j2b:x"
        doc, amap = build_display_animation("x", {})
        att = build_bedrock_attachable(M(), "textures/x", amap)["minecraft:attachable"]["description"]
        self.assertEqual(len(att["scripts"]["pre_animation"]), 3)
        self.assertIn("first_person_head", att["animations"])


class TestIconUpscale(unittest.TestCase):
    def test_square_upscaled_non_square_untouched(self):
        with tempfile.TemporaryDirectory() as t:
            a, b = Path(t) / "a.png", Path(t) / "b.png"
            Image.new("RGBA", (16, 16), (255, 0, 0, 255)).save(a)
            Image.new("RGBA", (16, 64), (255, 0, 0, 255)).save(b)
            _upscale_icon(a, 128)
            _upscale_icon(b, 128)
            with Image.open(a) as im_a:
                self.assertEqual(im_a.size, (128, 128))
            with Image.open(b) as im_b:
                self.assertEqual(im_b.size, (16, 64))



    def test_wall_painting_flush_compensation(self):
        # Wall paintings in ItemsAdder: translation=[0, -31.25, -12], scale=[1.5, 1.5, 1.5]
        disp = {
            "head": {
                "rotation": [0, 180, 0],
                "translation": [0, -31.25, -12],
                "scale": [1.5, 1.5, 1.5],
            }
        }
        doc, amap = build_display_animation("painting", disp)
        bones = doc["animations"][amap["head"]]["bones"]
        x_bone = bones["root_item_x"]
        # Z position must be 0.0 (flush against wall surface, not protruding by -7.5px)
        self.assertEqual(x_bone["position"][2], 0.0)
        self.assertEqual(x_bone["position"][1], round(-31.25 * 0.625, 4))
        self.assertEqual(x_bone["scale"], [round(1.5 * 0.625, 4)] * 3)

    def test_golden_models_displays(self):
        # 1. AK-47 (no head display, thirdperson handheld)
        ak_disp = {
            "thirdperson_righthand": {"rotation": [0, -90, 0], "translation": [0, 2.5, 1.75], "scale": [1.5, 1.5, 1.5]}
        }
        doc, amap = build_display_animation("ak47", ak_disp)
        ak_bones = doc["animations"][amap["third_person"]]["bones"]
        self.assertEqual(ak_bones["root_item_x"]["position"], [-0.0, 2.5, 1.75])
        self.assertEqual(ak_bones["root_item_y"]["rotation"], [0, 90.0, 0])

        # 2. Santa Hat (head display)
        santa_disp = {
            "head": {"rotation": [0, 0, 0], "translation": [0, 12.75, 0], "scale": [1.0, 1.0, 1.0]}
        }
        doc, amap = build_display_animation("santa_hat", santa_disp)
        santa_bones = doc["animations"][amap["head"]]["bones"]
        self.assertEqual(santa_bones["root_item_x"]["position"], [-0.0, round(12.75 * 0.625, 4), 0.0])
        self.assertEqual(santa_bones["root_item_x"]["scale"], [0.625, 0.625, 0.625])

if __name__ == "__main__":
    unittest.main()
