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
        # Toward-wall Z: java_tz + 5 → -7; Y=0 (y=16 was ~1 block too high); full Java scale.
        disp = {
            "head": {
                "rotation": [0, 180, 0],
                "translation": [0, -31.25, -12],
                "scale": [1.5, 1.5, 1.5],
            }
        }
        doc, amap = build_display_animation("painting", disp)
        bones = doc["animations"][amap["head"]]["bones"]
        root = bones["root_item"]
        self.assertEqual(root["position"], [0.0, 0.0, -7.0])
        self.assertEqual(root["scale"], [1.5, 1.5, 1.5])
        self.assertEqual(root["rotation"], [0.0, -180.0, 0.0])
        self.assertNotIn("root_item_x", bones)

    def test_battle_axe_not_furniture_fp_scale(self):
        # Battle axe has decorative head ty=-14.5 but must keep weapon FP scale 1.5
        disp = {
            "head": {"translation": [4.5, -14.5, 5.5], "scale": [1.6, 1.6, 1.6]},
            "firstperson_righthand": {"rotation": [0, -90, 25], "translation": [1.13, 3.2, 1.13], "scale": [0.68, 0.68, 0.68]},
        }
        doc, amap = build_display_animation("battle_axe", disp)
        fp = doc["animations"][amap["first_person"]]["bones"]["root_item"]
        self.assertEqual(fp["scale"], 1.5)

    def test_lefthand_inherits_missing_scale(self):
        disp = {
            "thirdperson_righthand": {
                "rotation": [0, 90, 0],
                "translation": [0, 2.5, 1.75],
                "scale": [1.5, 1.5, 1.5],
            },
            "thirdperson_lefthand": {
                "rotation": [0, 90, 0],
                "translation": [0, 1.5, 1],
                # scale omitted on purpose (common in Java packs)
            },
        }
        doc, amap = build_display_animation("katana", disp)
        left = doc["animations"][amap["third_person_left"]]["bones"]["root_item_x"]
        self.assertEqual(left["scale"], [1.5, 1.5, 1.5])

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
