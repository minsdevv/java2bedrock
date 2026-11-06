"""Unit tests for ConversionReport and structured asset reporting."""

import tempfile
import unittest
from pathlib import Path

from src.report import AssetReport, AssetStatus, ConversionReport


class TestConversionReport(unittest.TestCase):
    def test_report_structure(self):
        rep = ConversionReport()
        rep.pack = {"name": "TestPack", "pack_format": 84}
        rep.totals = {"total_items": 2}
        rep.warnings = ["Warning 1"]

        rep.add_asset("j2b:sword", "item", AssetStatus.CONVERTED, outputs=["attachables/sword.json"])
        rep.add_asset(
            "j2b:missing",
            "item",
            AssetStatus.APPROXIMATED,
            reasons=["missing_texture"],
            outputs=["textures/missing.png"],
        )

        d = rep.to_dict()
        self.assertEqual(d["pack"]["name"], "TestPack")
        self.assertEqual(d["summary_by_status"]["converted"], 1)
        self.assertEqual(d["summary_by_status"]["approximated"], 1)
        self.assertEqual(d["summary_by_status"]["skipped"], 0)
        self.assertEqual(len(d["assets"]), 2)
        self.assertEqual(d["assets"][1]["reasons"], ["missing_texture"])

    def test_report_write_json(self):
        rep = ConversionReport()
        rep.pack = {"name": "Pack"}
        rep.add_asset("j2b:block", "block", AssetStatus.CONVERTED)

        with tempfile.TemporaryDirectory() as td:
            out_file = Path(td) / "sub" / "report.json"
            rep.write_json(out_file)
            self.assertTrue(out_file.is_file())


if __name__ == "__main__":
    unittest.main()
