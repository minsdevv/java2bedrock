"""Unit tests for Phase 4: Blockbench (.bbmodel) Custom Mobs, Animations & Geyser Companion Extension."""

import base64
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from PIL import Image

from src.packager.zip_packager import convert_java_pack


def _make_base64_png(w: int = 64, h: int = 64) -> str:
    buf = io.BytesIO()
    Image.new("RGBA", (w, h), (255, 80, 20, 255)).save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _create_phase4_mock_pack(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pack.mcmeta").write_text(
        json.dumps({"pack": {"pack_format": 55, "description": "Phase 4 Pack"}}),
        encoding="utf-8",
    )

    bb_dir = root / "blueprints"
    bb_dir.mkdir(parents=True, exist_ok=True)

    bbmodel_doc = {
        "meta": {"format_version": "4.10", "model_format": "free"},
        "name": "Inferno Drake",
        "model_identifier": "inferno_drake",
        "resolution": {"width": 64, "height": 64},
        "elements": [
            {
                "name": "torso_cube",
                "uuid": "cube-torso-1",
                "from": [-4, 6, -6],
                "to": [4, 14, 6],
                "origin": [0, 10, 0],
                "rotation": [0, 0, 0],
                "faces": {
                    "north": {"uv": [0, 0, 8, 8]},
                    "south": {"uv": [8, 0, 16, 8]},
                    "up": {"uv": [0, 8, 8, 20]},
                },
            },
            {
                "name": "head_cube",
                "uuid": "cube-head-1",
                "from": [-3, 12, -12],
                "to": [3, 18, -6],
                "origin": [0, 14, -6],
                "rotation": [10, 0, 0],
                "faces": {
                    "north": {"uv": [16, 0, 22, 6]},
                },
            },
        ],
        "outliner": [
            {
                "name": "body",
                "uuid": "bone-body",
                "origin": [0, 10, 0],
                "rotation": [0, 0, 0],
                "children": [
                    "cube-torso-1",
                    {
                        "name": "head",
                        "uuid": "bone-head",
                        "origin": [0, 14, -6],
                        "rotation": [0, 0, 0],
                        "children": ["cube-head-1"],
                    },
                ],
            }
        ],
        "textures": [
            {
                "name": "drake_tex.png",
                "source": _make_base64_png(64, 64),
            }
        ],
        "animations": [
            {
                "name": "idle",
                "loop": "loop",
                "length": 2.0,
                "animators": {
                    "bone-head": {
                        "name": "head",
                        "type": "bone",
                        "keyframes": [
                            {
                                "channel": "rotation",
                                "time": 0.0,
                                "data_points": [{"x": 0, "y": 0, "z": 0}],
                            },
                            {
                                "channel": "rotation",
                                "time": 1.0,
                                "data_points": [{"x": 7.5, "y": 0, "z": 0}],
                            },
                        ],
                    }
                },
            },
            {
                "name": "walk",
                "loop": "loop",
                "length": 1.0,
                "animators": {
                    "bone-body": {
                        "name": "body",
                        "type": "bone",
                        "keyframes": [
                            {
                                "channel": "position",
                                "time": 0.0,
                                "data_points": [{"x": 0, "y": 0, "z": 0}],
                            },
                            {
                                "channel": "position",
                                "time": 0.5,
                                "data_points": [{"x": 0, "y": 1.5, "z": 0}],
                            },
                        ],
                    }
                },
            },
        ],
    }

    (bb_dir / "inferno_drake.bbmodel").write_text(
        json.dumps(bbmodel_doc, indent=2),
        encoding="utf-8",
    )


class TestPhase4(unittest.TestCase):
    def test_bbmodel_mob_and_extension_jar(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pack_dir = tmp_path / "phase4_pack"
            out_dir = tmp_path / "out"
            _create_phase4_mock_pack(pack_dir)

            res = convert_java_pack(pack_dir, out_dir, bedrock_ns="j2b")
            self.assertEqual(res.total_mobs, 1)
            self.assertIsNotNone(res.mob_registry_path)

            # 1. Verify Mob Geometry & Bone Hierarchy
            geo_file = (
                res.bedrock_pack_dir
                / "models"
                / "entity"
                / "mobs"
                / "inferno_drake.geo.json"
            )
            self.assertTrue(geo_file.is_file())
            geo_data = json.loads(geo_file.read_text(encoding="utf-8"))
            bones = geo_data["minecraft:geometry"][0]["bones"]
            bone_names = {b["name"]: b for b in bones}
            self.assertIn("body", bone_names)
            self.assertIn("head", bone_names)
            self.assertEqual(bone_names["head"]["parent"], "body")

            # 2. Verify Mob Keyframe Animations & Animation Controller
            anim_file = (
                res.bedrock_pack_dir
                / "animations"
                / "mobs"
                / "inferno_drake.animation.json"
            )
            self.assertTrue(anim_file.is_file())
            anim_data = json.loads(anim_file.read_text(encoding="utf-8"))
            self.assertIn("animation.j2b.inferno_drake.idle", anim_data["animations"])
            self.assertIn("animation.j2b.inferno_drake.walk", anim_data["animations"])

            ctrl_file = (
                res.bedrock_pack_dir
                / "animation_controllers"
                / "mobs"
                / "inferno_drake.animation_controllers.json"
            )
            self.assertTrue(ctrl_file.is_file())
            ctrl_data = json.loads(ctrl_file.read_text(encoding="utf-8"))
            ctrl = ctrl_data["animation_controllers"]["controller.animation.j2b.mob_inferno_drake"]
            self.assertEqual(ctrl["initial_state"], "idle")

            # 3. Verify Mob Registry JSON
            mob_reg = json.loads(res.mob_registry_path.read_text(encoding="utf-8"))
            self.assertEqual(mob_reg["mobs"][0]["bedrock_entity_identifier"], "j2b:mob_inferno_drake")
            self.assertEqual(mob_reg["mobs"][0]["animation_states"], ["idle", "walk"])

            # 4. Verify Compiled Geyser Companion Extension JAR
            ext_jar = Path(__file__).resolve().parent.parent / "extension" / "J2BCompanionExtension.jar"
            self.assertTrue(ext_jar.is_file())
            with zipfile.ZipFile(ext_jar, "r") as zf:
                names = set(zf.namelist())
                self.assertIn("extension.yml", names)
                self.assertIn("org/j2b/extension/J2BCompanionExtension.class", names)


if __name__ == "__main__":
    unittest.main()
