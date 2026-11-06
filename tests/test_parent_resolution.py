"""Unit tests for Java model parent resolution and deep inheritance chains."""

import json
from pathlib import Path
import tempfile
import unittest

from src.parser.item_parser import load_resolved_model_json


class TestParentResolution(unittest.TestCase):
    def test_deep_inheritance_and_chain(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            models_dir = root / "assets" / "minecraft" / "models" / "item"
            models_dir.mkdir(parents=True, exist_ok=True)

            # Level 3: base tool with display and handheld root
            (models_dir / "base_tool.json").write_text(
                json.dumps({
                    "parent": "item/handheld",
                    "display": {"thirdperson_righthand": {"rotation": [0, 90, -35]}},
                    "textures": {"layer0": "item/iron_sword"},
                }),
                encoding="utf-8",
            )

            # Level 2: custom sword inheriting base_tool, adds extra display and texture
            (models_dir / "custom_sword.json").write_text(
                json.dumps({
                    "parent": "minecraft:item/base_tool",
                    "display": {"gui": {"rotation": [0, 0, 0]}},
                    "textures": {"layer1": "item/fire_overlay"},
                }),
                encoding="utf-8",
            )

            # Level 1: leaf ruby_sword overriding layer0
            (models_dir / "ruby_sword.json").write_text(
                json.dumps({
                    "parent": "minecraft:item/custom_sword",
                    "textures": {"layer0": "custom:item/ruby_blade"},
                }),
                encoding="utf-8",
            )

            resolved = load_resolved_model_json(root, "minecraft:item/ruby_sword")

            # 1. Texture merging: layer0 overridden, layer1 inherited
            self.assertEqual(resolved["textures"]["layer0"], "custom:item/ruby_blade")
            self.assertEqual(resolved["textures"]["layer1"], "item/fire_overlay")

            # 2. Display merging: both thirdperson_righthand and gui present
            self.assertIn("thirdperson_righthand", resolved["display"])
            self.assertIn("gui", resolved["display"])

            # 3. Root parent and parent chain
            self.assertEqual(resolved.get("_root_parent"), "item/handheld")
            chain = resolved.get("_parent_chain", [])
            self.assertIn("item/handheld", chain)
            self.assertIn("minecraft:item/base_tool", chain)
            self.assertIn("minecraft:item/custom_sword", chain)

    def test_cycle_detection(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            models_dir = root / "assets" / "minecraft" / "models" / "item"
            models_dir.mkdir(parents=True, exist_ok=True)

            (models_dir / "cycle_a.json").write_text(
                json.dumps({"parent": "minecraft:item/cycle_b"}), encoding="utf-8"
            )
            (models_dir / "cycle_b.json").write_text(
                json.dumps({"parent": "minecraft:item/cycle_a"}), encoding="utf-8"
            )

            # Should not hang or raise RecursionError
            resolved = load_resolved_model_json(root, "minecraft:item/cycle_a")
            self.assertIsInstance(resolved, dict)


if __name__ == "__main__":
    unittest.main()
