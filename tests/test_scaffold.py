"""End-to-end unit tests for Nexo-style scaffolding (cli.py scaffold & cli.py build)."""

import json
from pathlib import Path
import tempfile
import unittest

import cli
from src.scaffold import build_scaffold_project, scaffold_project


class TestScaffoldWorkflow(unittest.TestCase):
    def test_scaffold_and_build_end_to_end(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            proj_dir = scaffold_project("DemoServerPack", output_root=root, namespace="demons")
            self.assertTrue((proj_dir / "j2b.yml").is_file())
            self.assertTrue((proj_dir / "items" / "weapons.yml").is_file())
            self.assertTrue((proj_dir / "blocks" / "ores.yml").is_file())
            self.assertTrue((proj_dir / "furniture" / "chairs.yml").is_file())
            self.assertTrue((proj_dir / "mobs" / "mini_golem.bbmodel").is_file())

            build_res = build_scaffold_project(proj_dir)
            self.assertTrue(build_res.java_pack_zip.is_file())
            self.assertTrue(build_res.conversion_result.mcpack_path.is_file())
            self.assertTrue(build_res.conversion_result.mappings_v2_path.is_file())

            conv = build_res.conversion_result
            self.assertGreaterEqual(conv.total_items, 2)
            self.assertEqual(conv.total_blocks, 1)
            self.assertEqual(conv.total_furniture, 1)
            self.assertEqual(conv.total_mobs, 1)

            v2 = json.loads(conv.mappings_v2_path.read_text(encoding="utf-8"))
            self.assertIn("minecraft:diamond_sword", v2["items"])
            self.assertIn("minecraft:trident", v2["items"])

    def test_cli_scaffold_and_build_subcommands(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            rc1 = cli.main(["scaffold", "CliPack", "--output", str(root)])
            self.assertEqual(rc1, 0)
            proj = root / "CliPack"
            rc2 = cli.main(["build", "--project", str(proj)])
            self.assertEqual(rc2, 0)
            self.assertTrue((proj / "build" / "CliPack.mcpack").is_file())
            self.assertTrue((proj / "build" / "CliPack_java.zip").is_file())


if __name__ == "__main__":
    unittest.main()
