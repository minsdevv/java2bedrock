"""Regression test to guarantee golden items never unexpectedly change."""

import json
from pathlib import Path
import unittest

from tests.tools.snapshot_outputs import generate_snapshot


class TestGoldenItems(unittest.TestCase):
    def test_golden_items_match_baseline(self):
        root = Path(__file__).resolve().parent.parent
        pack_dir = root / "output" / "mins_net" / "MinsNetworkPack_bedrock"
        mappings_file = root / "output" / "mins_net" / "custom_mappings" / "items_v2.json"
        golden_file = root / "tests" / "golden_items.json"

        if not pack_dir.is_dir() or not mappings_file.is_file() or not golden_file.is_file():
            self.skipTest("Pack or golden file not present on disk")

        golden = json.loads(golden_file.read_text(encoding="utf-8"))
        current = generate_snapshot(pack_dir, mappings_file)

        # Check mappings
        for k, expected in golden.get("mappings", {}).items():
            self.assertIn(k, current["mappings"], f"Missing golden mapping for {k}")
            self.assertEqual(current["mappings"][k], expected, f"Mapping changed for {k}")

        # Check items
        for k, expected in golden.get("items", {}).items():
            self.assertIn(k, current["items"], f"Missing golden item for {k}")
            cur = current["items"][k]
            self.assertEqual(cur.get("materials"), expected.get("materials"), f"Materials changed for {k}")
            self.assertEqual(cur.get("geometry"), expected.get("geometry"), f"Geometry changed for {k}")
            self.assertEqual(cur.get("animations"), expected.get("animations"), f"Animations changed for {k}")
            self.assertEqual(cur.get("scripts"), expected.get("scripts"), f"Scripts changed for {k}")
            self.assertEqual(cur.get("animation_bones"), expected.get("animation_bones"), f"Animation bones changed for {k}")
            self.assertEqual(cur.get("root_binding"), expected.get("root_binding"), f"Root binding changed for {k}")


if __name__ == "__main__":
    unittest.main()
