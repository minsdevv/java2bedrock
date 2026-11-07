"""Nexo-style Project Scaffolding & Unified Builder (Java Pack + Bedrock .mcpack + Geyser Mappings)."""

import base64
from dataclasses import dataclass
import io
import json
from pathlib import Path
import re
import shutil
from typing import Any, Dict, List, Optional, Tuple
import zipfile

from PIL import Image
import yaml

from ..packager.zip_packager import ConversionResult, convert_java_pack


@dataclass
class ScaffoldBuildResult:
    """Summary of a completed scaffold project build."""

    project_dir: Path
    java_pack_dir: Path
    java_pack_zip: Path
    conversion_result: ConversionResult


def _sanitize_namespace(raw: str) -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", raw.strip().lower()).strip("_")
    return slug or "custom_pack"


def _make_sample_png_bytes(color_rgba: Tuple[int, int, int, int], accent_rgba: Tuple[int, int, int, int]) -> bytes:
    """Create a 16x16 pixel-art PNG image in memory."""
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    px = img.load()
    for y in range(2, 14):
        for x in range(2, 14):
            px[x, y] = color_rgba
    for i in range(3, 13):
        px[i, i] = accent_rgba
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def scaffold_project(
    project_name: str,
    output_root: Path = Path("."),
    namespace: Optional[str] = None,
    bedrock_ns: str = "j2b",
) -> Path:
    """Generate a Nexo-style scaffold project directory with sample YAML configs and assets."""
    output_root = Path(output_root).resolve()
    project_dir = output_root / project_name
    ns = _sanitize_namespace(namespace or project_name)

    for sub in (
        "items",
        "blocks",
        "furniture",
        "mobs",
        "textures/item",
        "textures/block",
        "models/item",
        "models/furniture",
    ):
        (project_dir / sub).mkdir(parents=True, exist_ok=True)

    # 1. Project manifest (j2b.yml)
    project_cfg = {
        "name": project_name,
        "description": f"{project_name} - Built with Java2Bedrock Scaffolding",
        "namespace": ns,
        "bedrock_namespace": bedrock_ns,
        "pack_format": 48,
        "icon_size": 128,
    }
    (project_dir / "j2b.yml").write_text(
        yaml.safe_dump(project_cfg, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    # 2. Sample textures
    (project_dir / "textures/item/ruby_sword.png").write_bytes(
        _make_sample_png_bytes((220, 40, 60, 255), (255, 210, 80, 255))
    )
    (project_dir / "textures/block/ruby_ore.png").write_bytes(
        _make_sample_png_bytes((110, 110, 120, 255), (230, 30, 50, 255))
    )
    (project_dir / "textures/block/oak_wood.png").write_bytes(
        _make_sample_png_bytes((160, 115, 65, 255), (120, 85, 45, 255))
    )

    # 3. Sample 3D Item model (emerald_spear.json)
    spear_model = {
        "credit": "Java2Bedrock Scaffold",
        "textures": {
            "0": f"{ns}:block/oak_wood",
            "1": f"{ns}:item/ruby_sword",
            "particle": f"{ns}:item/ruby_sword",
        },
        "elements": [
            {
                "from": [7.5, -8.0, 7.5],
                "to": [8.5, 20.0, 8.5],
                "faces": {
                    "north": {"uv": [0, 0, 2, 16], "texture": "#0"},
                    "east": {"uv": [0, 0, 2, 16], "texture": "#0"},
                    "south": {"uv": [0, 0, 2, 16], "texture": "#0"},
                    "west": {"uv": [0, 0, 2, 16], "texture": "#0"},
                    "up": {"uv": [0, 0, 2, 2], "texture": "#0"},
                    "down": {"uv": [0, 0, 2, 2], "texture": "#0"},
                },
            },
            {
                "from": [7.0, 20.0, 7.0],
                "to": [9.0, 26.0, 9.0],
                "faces": {
                    "north": {"uv": [2, 2, 6, 14], "texture": "#1"},
                    "east": {"uv": [2, 2, 6, 14], "texture": "#1"},
                    "south": {"uv": [2, 2, 6, 14], "texture": "#1"},
                    "west": {"uv": [2, 2, 6, 14], "texture": "#1"},
                    "up": {"uv": [2, 2, 6, 6], "texture": "#1"},
                    "down": {"uv": [2, 2, 6, 6], "texture": "#1"},
                },
            },
        ],
        "display": {
            "thirdperson_righthand": {"translation": [0, 2, 0], "scale": [1, 1, 1]},
            "firstperson_righthand": {"translation": [1, -1, 0], "scale": [0.8, 0.8, 0.8]},
            "gui": {"rotation": [-90, 45, 90], "scale": [0.65, 0.65, 0.65]},
        },
    }
    (project_dir / "models/item/emerald_spear.json").write_text(
        json.dumps(spear_model, indent=2), encoding="utf-8"
    )

    # 4. Sample 3D Furniture model (oak_chair.json)
    chair_model = {
        "credit": "Java2Bedrock Scaffold",
        "textures": {
            "0": f"{ns}:block/oak_wood",
            "particle": f"{ns}:block/oak_wood",
        },
        "elements": [
            {
                "from": [3, 0, 3],
                "to": [13, 8, 13],
                "faces": {
                    "north": {"uv": [0, 0, 10, 8], "texture": "#0"},
                    "east": {"uv": [0, 0, 10, 8], "texture": "#0"},
                    "south": {"uv": [0, 0, 10, 8], "texture": "#0"},
                    "west": {"uv": [0, 0, 10, 8], "texture": "#0"},
                    "up": {"uv": [0, 0, 10, 10], "texture": "#0"},
                    "down": {"uv": [0, 0, 10, 10], "texture": "#0"},
                },
            },
            {
                "from": [3, 8, 11],
                "to": [13, 18, 13],
                "faces": {
                    "north": {"uv": [0, 0, 10, 10], "texture": "#0"},
                    "east": {"uv": [0, 0, 2, 10], "texture": "#0"},
                    "south": {"uv": [0, 0, 10, 10], "texture": "#0"},
                    "west": {"uv": [0, 0, 2, 10], "texture": "#0"},
                    "up": {"uv": [0, 0, 10, 2], "texture": "#0"},
                    "down": {"uv": [0, 0, 10, 2], "texture": "#0"},
                },
            },
        ],
    }
    (project_dir / "models/furniture/oak_chair.json").write_text(
        json.dumps(chair_model, indent=2), encoding="utf-8"
    )

    # 5. Sample .bbmodel mob (mini_golem.bbmodel)
    mob_png_b64 = base64.b64encode(
        _make_sample_png_bytes((90, 180, 220, 255), (240, 240, 255, 255))
    ).decode("ascii")
    sample_bbmodel = {
        "meta": {"format_version": "4.5", "model_format": "free"},
        "name": "mini_golem",
        "model_identifier": "mini_golem",
        "resolution": {"width": 16, "height": 16},
        "elements": [
            {
                "name": "body",
                "uuid": "cube-body-1",
                "from": [-4, 0, -4],
                "to": [4, 8, 4],
                "origin": [0, 4, 0],
                "faces": {
                    "north": {"uv": [0, 0, 8, 8], "texture": 0},
                    "east": {"uv": [0, 0, 8, 8], "texture": 0},
                    "south": {"uv": [0, 0, 8, 8], "texture": 0},
                    "west": {"uv": [0, 0, 8, 8], "texture": 0},
                    "up": {"uv": [0, 0, 8, 8], "texture": 0},
                    "down": {"uv": [0, 0, 8, 8], "texture": 0},
                },
            }
        ],
        "outliner": [
            {
                "name": "body",
                "uuid": "bone-body-1",
                "origin": [0, 4, 0],
                "rotation": [0, 0, 0],
                "children": ["cube-body-1"],
            }
        ],
        "textures": [
            {
                "name": "mini_golem.png",
                "source": f"data:image/png;base64,{mob_png_b64}",
            }
        ],
        "animations": [
            {
                "name": "idle",
                "loop": "loop",
                "length": 1.0,
                "animators": {
                    "bone-body-1": {
                        "name": "body",
                        "keyframes": [
                            {
                                "channel": "position",
                                "time": 0.0,
                                "data_points": [{"x": 0, "y": 0, "z": 0}],
                            },
                            {
                                "channel": "position",
                                "time": 0.5,
                                "data_points": [{"x": 0, "y": 1, "z": 0}],
                            },
                            {
                                "channel": "position",
                                "time": 1.0,
                                "data_points": [{"x": 0, "y": 0, "z": 0}],
                            },
                        ],
                    }
                },
            }
        ],
    }
    (project_dir / "mobs/mini_golem.bbmodel").write_text(
        json.dumps(sample_bbmodel, indent=2), encoding="utf-8"
    )

    # 6. Sample YAML configurations
    items_yaml = {
        "items": {
            "ruby_sword": {
                "material": "DIAMOND_SWORD",
                "custom_model_data": 1001,
                "parent": "item/handheld",
                "texture": "item/ruby_sword",
            },
            "emerald_spear": {
                "material": "TRIDENT",
                "custom_model_data": 1002,
                "model": "item/emerald_spear",
            },
        }
    }
    (project_dir / "items/weapons.yml").write_text(
        yaml.safe_dump(items_yaml, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    blocks_yaml = {
        "blocks": {
            "ruby_ore": {
                "carrier": "note_block",
                "state": "instrument=harp,note=1,powered=false",
                "texture": "block/ruby_ore",
                "custom_model_data": 2001,
            }
        }
    }
    (project_dir / "blocks/ores.yml").write_text(
        yaml.safe_dump(blocks_yaml, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    furniture_yaml = {
        "furniture": {
            "oak_chair": {
                "material": "PAPER",
                "custom_model_data": 3001,
                "model": "furniture/oak_chair",
                "hitbox": {"width": 0.8, "height": 1.2},
                "seat_height": 0.5,
            }
        }
    }
    (project_dir / "furniture/chairs.yml").write_text(
        yaml.safe_dump(furniture_yaml, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    # 7. Short README
    readme_text = f"""# {project_name} (Java2Bedrock Scaffold)

Khung dự án kiểu **Nexo / ItemsAdder** tự động biên dịch ra đồng thời:
1. **Java Resource Pack** (`build/{project_name}_java.zip`)
2. **Bedrock Resource Pack** (`build/{project_name}.mcpack`)
3. **GeyserMC Custom Mappings v2** (`build/custom_mappings/items_v2.json`, `blocks.json`, `furniture_registry.json`, `mob_registry.json`, `trident_registry.json`)

## Cấu trúc thư mục
- `j2b.yml`: Cấu hình chung của pack (`name`, `namespace`, `bedrock_namespace`, `pack_format`, `icon_size`).
- `items/*.yml`: Khai báo vật phẩm 2D (tự sinh model từ `texture`) hoặc 3D (trỏ tới `model`).
- `blocks/*.yml`: Khai báo khối tùy chỉnh (`note_block`, `mushroom_stem`, `tripwire`).
- `furniture/*.yml`: Khai báo nội thất `ItemDisplay` 3D kèm hitbox & `seat_height`.
- `mobs/*.bbmodel`: Mô hình quái/thú cưng Blockbench (`.bbmodel`).
- `textures/` & `models/`: Chứa ảnh `.png` và model `.json`.

## Lệnh Build
```bash
python3 cli.py build --project "{project_dir}" --output "{project_dir / 'build'}"
```
"""
    (project_dir / "README.md").write_text(readme_text, encoding="utf-8")
    return project_dir


def _load_yaml_files(directory: Path) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    if not directory.is_dir():
        return docs
    for f in sorted(list(directory.glob("*.yml")) + list(directory.glob("*.yaml"))):
        try:
            loaded = yaml.safe_load(f.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                docs.append(loaded)
        except Exception:
            continue
    return docs


def build_scaffold_project(
    project_dir: Path,
    output_dir: Optional[Path] = None,
    icon_size: Optional[int] = None,
) -> ScaffoldBuildResult:
    """Compile a scaffold project into a Java Resource Pack + Bedrock .mcpack + Geyser mappings."""
    project_dir = Path(project_dir).resolve()
    cfg_file = project_dir / "j2b.yml"
    if not cfg_file.is_file():
        raise FileNotFoundError(f"Missing j2b.yml in scaffold project: {project_dir}")

    cfg = yaml.safe_load(cfg_file.read_text(encoding="utf-8")) or {}
    pack_name = str(cfg.get("name", project_dir.name))
    description = str(cfg.get("description", f"{pack_name} Resource Pack"))
    ns = _sanitize_namespace(str(cfg.get("namespace", pack_name)))
    bedrock_ns = str(cfg.get("bedrock_namespace", "j2b"))
    pack_format = int(cfg.get("pack_format", 48))
    final_icon_size = int(icon_size if icon_size is not None else cfg.get("icon_size", 128))

    out_root = Path(output_dir).resolve() if output_dir else (project_dir / "build").resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    java_dir = out_root / f"{pack_name}_java"
    if java_dir.exists():
        shutil.rmtree(java_dir)
    java_dir.mkdir(parents=True, exist_ok=True)

    # 1. Write pack.mcmeta
    mcmeta = {
        "pack": {
            "pack_format": pack_format,
            "description": description,
        }
    }
    (java_dir / "pack.mcmeta").write_text(json.dumps(mcmeta, indent=2), encoding="utf-8")

    # 2. Copy raw textures and models into assets/<ns>/
    ns_assets = java_dir / "assets" / ns
    src_textures = project_dir / "textures"
    if src_textures.is_dir():
        shutil.copytree(src_textures, ns_assets / "textures", dirs_exist_ok=True)
    src_models = project_dir / "models"
    if src_models.is_dir():
        shutil.copytree(src_models, ns_assets / "models", dirs_exist_ok=True)

    # Copy .bbmodel files into assets/<ns>/bbmodel/
    src_mobs = project_dir / "mobs"
    if src_mobs.is_dir():
        for bbm in sorted(src_mobs.glob("*.bbmodel")):
            dest_bbm = ns_assets / "bbmodel" / bbm.name
            dest_bbm.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bbm, dest_bbm)

    overrides_by_base_item: Dict[str, List[Dict[str, Any]]] = {}

    def _add_item_override(base_item: str, cmd: int, model_ref: str, extra_preds: Optional[Dict[str, Any]] = None) -> None:
        clean_base = base_item.lower().replace("minecraft:", "")
        pred: Dict[str, Any] = {"custom_model_data": int(cmd)}
        if extra_preds:
            pred.update(extra_preds)
        overrides_by_base_item.setdefault(clean_base, []).append(
            {"predicate": pred, "model": model_ref}
        )

    # 3. Compile items/*.yml
    for doc in _load_yaml_files(project_dir / "items"):
        items_dict = doc.get("items", doc)
        if not isinstance(items_dict, dict):
            continue
        for item_id, spec in items_dict.items():
            if not isinstance(spec, dict):
                continue
            material = str(spec.get("material", "PAPER")).lower()
            cmd = int(spec.get("custom_model_data", 1000))
            model_rel = spec.get("model")
            if model_rel:
                full_model_ref = model_rel if ":" in str(model_rel) else f"{ns}:{model_rel}"
            else:
                tex_rel = str(spec.get("texture", f"item/{item_id}"))
                full_tex_ref = tex_rel if ":" in tex_rel else f"{ns}:{tex_rel}"
                parent_model = str(spec.get("parent", "item/generated"))
                gen_model_path = ns_assets / "models" / "item" / f"{item_id}.json"
                gen_model_path.parent.mkdir(parents=True, exist_ok=True)
                gen_model_doc = {
                    "parent": parent_model,
                    "textures": {"layer0": full_tex_ref},
                }
                gen_model_path.write_text(json.dumps(gen_model_doc, indent=2), encoding="utf-8")
                full_model_ref = f"{ns}:item/{item_id}"

            _add_item_override(material, cmd, full_model_ref)

    # 4. Compile blocks/*.yml -> block model + blockstates/<carrier>.json + item override
    blockstate_variants: Dict[str, Dict[str, Any]] = {}
    for doc in _load_yaml_files(project_dir / "blocks"):
        blocks_dict = doc.get("blocks", doc)
        if not isinstance(blocks_dict, dict):
            continue
        for blk_id, spec in blocks_dict.items():
            if not isinstance(spec, dict):
                continue
            carrier = str(spec.get("carrier", "note_block")).lower().replace("minecraft:", "")
            state_str = str(spec.get("state", "instrument=harp,note=1,powered=false")).strip("[]")
            model_rel = spec.get("model")
            if model_rel:
                full_model_ref = str(model_rel) if ":" in str(model_rel) else f"{ns}:{model_rel}"
            else:
                tex_rel = str(spec.get("texture", f"block/{blk_id}"))
                full_tex_ref = tex_rel if ":" in tex_rel else f"{ns}:{tex_rel}"
                blk_model_path = ns_assets / "models" / "block" / f"{blk_id}.json"
                blk_model_path.parent.mkdir(parents=True, exist_ok=True)
                blk_model_doc = {
                    "parent": "block/cube_all",
                    "textures": {"all": full_tex_ref},
                }
                blk_model_path.write_text(json.dumps(blk_model_doc, indent=2), encoding="utf-8")
                full_model_ref = f"{ns}:block/{blk_id}"

            blockstate_variants.setdefault(carrier, {})[state_str] = {"model": full_model_ref}
            if "custom_model_data" in spec:
                _add_item_override(carrier, int(spec["custom_model_data"]), full_model_ref)

    for carrier, variants in blockstate_variants.items():
        bs_path = java_dir / "assets" / "minecraft" / "blockstates" / f"{carrier}.json"
        bs_path.parent.mkdir(parents=True, exist_ok=True)
        bs_path.write_text(json.dumps({"variants": variants}, indent=2), encoding="utf-8")

    # 5. Compile furniture/*.yml -> furniture.json + item override
    furniture_entries: Dict[str, Any] = {}
    for doc in _load_yaml_files(project_dir / "furniture"):
        furn_dict = doc.get("furniture", doc)
        if not isinstance(furn_dict, dict):
            continue
        for furn_id, spec in furn_dict.items():
            if not isinstance(spec, dict):
                continue
            material = str(spec.get("material", "PAPER")).lower().replace("minecraft:", "")
            cmd = int(spec.get("custom_model_data", 3000))
            model_rel = str(spec.get("model", f"furniture/{furn_id}"))
            full_model_ref = model_rel if ":" in model_rel else f"{ns}:{model_rel}"
            hitbox = spec.get("hitbox", {"width": 1.0, "height": 1.0})
            seat_height = spec.get("seat_height")

            furniture_entries[f"{ns}:{furn_id}"] = {
                "model": full_model_ref,
                "item": f"minecraft:{material}",
                "custom_model_data": cmd,
                "hitbox": hitbox,
                "seat_height": seat_height,
            }
            _add_item_override(material, cmd, full_model_ref)

    if furniture_entries:
        (java_dir / "furniture.json").write_text(
            json.dumps({"furniture": furniture_entries}, indent=2), encoding="utf-8"
        )

    # 6. Write Legacy (assets/minecraft/models/item/*.json) & Modern (assets/minecraft/items/*.json)
    for base_item, ov_list in overrides_by_base_item.items():
        ov_sorted = sorted(ov_list, key=lambda x: x["predicate"].get("custom_model_data", 0))
        legacy_path = java_dir / "assets" / "minecraft" / "models" / "item" / f"{base_item}.json"
        legacy_path.parent.mkdir(parents=True, exist_ok=True)
        legacy_doc = {
            "parent": "item/handheld" if "sword" in base_item or "axe" in base_item or "trident" in base_item else "item/generated",
            "textures": {"layer0": f"item/{base_item}"},
            "overrides": ov_sorted,
        }
        legacy_path.write_text(json.dumps(legacy_doc, indent=2), encoding="utf-8")

        modern_entries = [
            {
                "threshold": ov["predicate"]["custom_model_data"],
                "model": {"type": "minecraft:model", "model": ov["model"]},
            }
            for ov in ov_sorted
            if len(ov["predicate"]) == 1 and "custom_model_data" in ov["predicate"]
        ]
        if modern_entries:
            modern_path = java_dir / "assets" / "minecraft" / "items" / f"{base_item}.json"
            modern_path.parent.mkdir(parents=True, exist_ok=True)
            modern_doc = {
                "model": {
                    "type": "minecraft:range_dispatch",
                    "property": "minecraft:custom_model_data",
                    "index": 0,
                    "fallback": {"type": "minecraft:model", "model": f"minecraft:item/{base_item}"},
                    "entries": modern_entries,
                }
            }
            modern_path.write_text(json.dumps(modern_doc, indent=2), encoding="utf-8")

    # 7. Zip the compiled Java Resource Pack
    java_zip_path = out_root / f"{pack_name}_java.zip"
    with zipfile.ZipFile(java_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(java_dir.rglob("*")):
            if f.is_file():
                zf.write(f, f.relative_to(java_dir).as_posix())

    # 8. Run Java2Bedrock conversion on the compiled Java Pack
    conv_result = convert_java_pack(
        input_path=java_dir,
        output_dir=out_root,
        pack_name=pack_name,
        bedrock_ns=bedrock_ns,
        icon_size=final_icon_size,
        report_path=out_root / "conversion_report.json",
    )

    return ScaffoldBuildResult(
        project_dir=project_dir,
        java_pack_dir=java_dir,
        java_pack_zip=java_zip_path,
        conversion_result=conv_result,
    )
