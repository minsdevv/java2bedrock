#!/usr/bin/env python3
"""Command-Line Interface for Java2Bedrock Universal Converter & Scaffolding."""

import argparse
import json
from pathlib import Path
import sys
from typing import List, Optional

from src.packager.zip_packager import convert_java_pack
from src.scaffold.project_scaffold import build_scaffold_project, scaffold_project


def _add_convert_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="Path to Java Resource Pack (.zip file or directory).",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="./output",
        help="Output directory for Bedrock .mcpack and custom_mappings.",
    )
    parser.add_argument(
        "-n",
        "--name",
        default=None,
        help="Optional custom name for the generated Bedrock pack.",
    )
    parser.add_argument(
        "--namespace",
        default="j2b",
        help="Bedrock identifier namespace prefix (default: j2b).",
    )
    parser.add_argument(
        "--bedrock-overlay",
        action="append",
        dest="bedrock_overlays",
        default=None,
        help="Optional path to custom Bedrock pack(s) (folder, .mcpack, or .zip) to merge into the output pack.",
    )
    parser.add_argument(
        "--allow-gui-font-glyphs",
        action="store_true",
        default=False,
        help="Allow oversized GUI background glyphs in font sheets (default: False, filters them out to prevent squished boxes in title).",
    )
    parser.add_argument(
        "--icon-size",
        type=int,
        default=128,
        choices=[16, 32, 64, 128, 256, 512],
        help="Inventory icon resolution in px: 3D item icons are rendered at this size and square 2D icons are NEAREST-upscaled to it (default: 128).",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="Write a detailed asset-by-asset conversion_report.json to the specified file path.",
    )
    parser.add_argument(
        "--summary-json",
        default=None,
        help="Write a JSON conversion summary report to the specified file path.",
    )
    parser.add_argument(
        "--summary-markdown",
        default=None,
        help="Write a Markdown conversion summary report (for GitHub Issues) to the specified path.",
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="java2bedrock",
        description=(
            "Convert Minecraft Java Edition Resource Packs (1.14 - 26.3+) "
            "into Bedrock Edition .mcpack and GeyserMC Custom Mappings, "
            "or scaffold/build multi-platform packs from YAML."
        ),
    )
    _add_convert_arguments(parser)
    return parser


def _run_convert(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[ERROR] Input path does not exist: {input_path}", file=sys.stderr)
        return 1

    result = convert_java_pack(
        input_path=input_path,
        output_dir=Path(args.output),
        pack_name=args.name,
        bedrock_ns=args.namespace,
        bedrock_overlays=args.bedrock_overlays,
        filter_gui_font_glyphs=not args.allow_gui_font_glyphs,
        icon_size=args.icon_size,
        report_path=args.report,
    )

    print(f"✅ Conversion completed for '{result.pack_meta.name}'")
    print(f"   • Pack Format     : {result.pack_meta.pack_format}")
    print(f"   • Namespaces      : {', '.join(result.pack_meta.namespaces) or 'none'}")
    print(f"   • Total Items     : {result.total_items} ({result.items_3d} 3D, {result.items_2d} 2D)")
    print(f"   • Custom Blocks   : {result.total_blocks}")
    print(f"   • Display Furn.   : {result.total_furniture}")
    print(f"   • Custom Mobs     : {result.total_mobs}")
    print(f"   • Font Glyphs     : {result.total_font_glyphs}")
    print(f"   • Sounds Audio    : {result.total_sounds}")
    print(f"   • Bedrock .mcpack : {result.mcpack_path}")
    print(f"   • Geyser v2 Map   : {result.mappings_v2_path}")
    print(f"   • Geyser v1 Map   : {result.mappings_v1_path}")
    if result.report:
        counts = result.report.to_dict().get("summary_by_status", {})
        print(
            f"   • Asset Statuses  : {counts.get('converted', 0)} converted, "
            f"{counts.get('approximated', 0)} approximated, {counts.get('skipped', 0)} skipped"
        )
    if args.report:
        print(f"   • Detailed Report : {args.report}")

    if args.summary_json:
        summary_data = {
            "pack_name": result.pack_meta.name,
            "description": result.pack_meta.description,
            "pack_format": result.pack_meta.pack_format,
            "namespaces": result.pack_meta.namespaces,
            "total_items": result.total_items,
            "items_3d": result.items_3d,
            "items_2d": result.items_2d,
            "total_blocks": result.total_blocks,
            "total_furniture": result.total_furniture,
            "total_mobs": result.total_mobs,
            "total_font_glyphs": result.total_font_glyphs,
            "total_sounds": result.total_sounds,
            "mcpack_path": str(result.mcpack_path),
            "mappings_v2_path": str(result.mappings_v2_path),
            "mappings_v1_path": str(result.mappings_v1_path),
            "warnings": result.warnings,
        }
        Path(args.summary_json).write_text(
            json.dumps(summary_data, indent=2), encoding="utf-8"
        )

    if args.summary_markdown:
        md_lines = [
            f"## 🎉 Chuyển đổi Resource Pack thành công: `{result.pack_meta.name}`",
            "",
            "| Thông số | Giá trị |",
            "| :--- | :--- |",
            f"| **Tên Pack** | `{result.pack_meta.name}` |",
            f"| **Mô tả** | {result.pack_meta.description} |",
            f"| **Java Pack Format** | `{result.pack_meta.pack_format}` (Tương thích Minecraft 26.3+) |",
            f"| **Namespaces** | `{', '.join(result.pack_meta.namespaces) or 'minecraft'}` |",
            f"| **Tổng số Custom Items** | **{result.total_items}** (`{result.items_3d}` 3D models, `{result.items_2d}` 2D sprites) |",
            f"| **Tổng số Custom Blocks** | **{result.total_blocks}** |",
            f"| **Tổng số Display Furniture** | **{result.total_furniture}** |",
            f"| **Tổng số Custom Mobs (.bbmodel)** | **{result.total_mobs}** |",
            f"| **Tổng số Custom Font Glyphs** | **{result.total_font_glyphs}** |",
            f"| **File Bedrock Pack** | `{result.mcpack_path.name}` |",
            f"| **Geyser Mappings (v2 / 26.3)** | `custom_mappings/items_v2.json` |",
            f"| **Geyser Mappings (v1 Legacy)** | `custom_mappings/items_v1_legacy.json.bak` |",
            "",
        ]
        if result.warnings:
            md_lines.append("### ⚠️ Cảnh báo trong quá trình chuyển đổi")
            for w in result.warnings[:15]:
                md_lines.append(f"- {w}")
            md_lines.append("")
        Path(args.summary_markdown).write_text("\n".join(md_lines), encoding="utf-8")

    return 0


def main(argv: Optional[List[str]] = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)

    if raw_args and raw_args[0] == "scaffold":
        sp = argparse.ArgumentParser(
            prog="java2bedrock scaffold",
            description="Generate a Nexo-style scaffold project directory.",
        )
        sp.add_argument("name", help="Name of the new pack project.")
        sp.add_argument(
            "-o",
            "--output",
            default=".",
            help="Parent directory where the scaffold folder will be created (default: current directory).",
        )
        sp.add_argument(
            "--namespace",
            default=None,
            help="Java namespace for custom assets (defaults to sanitized project name).",
        )
        sp.add_argument(
            "--bedrock-namespace",
            default="j2b",
            help="Bedrock identifier namespace prefix (default: j2b).",
        )
        ns_args = sp.parse_args(raw_args[1:])
        proj_dir = scaffold_project(
            project_name=ns_args.name,
            output_root=Path(ns_args.output),
            namespace=ns_args.namespace,
            bedrock_ns=ns_args.bedrock_namespace,
        )
        print(f"✅ Scaffold project created at: {proj_dir}")
        print(f"   • Config : {proj_dir / 'j2b.yml'}")
        print(f"   • Build  : python3 cli.py build --project \"{proj_dir}\"")
        return 0

    if raw_args and raw_args[0] == "build":
        bp = argparse.ArgumentParser(
            prog="java2bedrock build",
            description="Build Java Pack + Bedrock .mcpack + Geyser Mappings from a scaffold project.",
        )
        bp.add_argument(
            "-p",
            "--project",
            default=".",
            help="Path to the scaffold project directory containing j2b.yml (default: current directory).",
        )
        bp.add_argument(
            "-o",
            "--output",
            default=None,
            help="Output build directory (default: <project>/build).",
        )
        bp.add_argument(
            "--icon-size",
            type=int,
            default=None,
            choices=[16, 32, 64, 128, 256, 512],
            help="Override inventory icon resolution in px.",
        )
        b_args = bp.parse_args(raw_args[1:])
        proj_path = Path(b_args.project)
        if not (proj_path / "j2b.yml").is_file():
            print(f"[ERROR] j2b.yml not found in project path: {proj_path}", file=sys.stderr)
            return 1
        res = build_scaffold_project(
            project_dir=proj_path,
            output_dir=Path(b_args.output) if b_args.output else None,
            icon_size=b_args.icon_size,
        )
        conv = res.conversion_result
        print(f"✅ Scaffold build completed for '{conv.pack_meta.name}'")
        print(f"   • Java Pack (.zip): {res.java_pack_zip}")
        print(f"   • Bedrock .mcpack : {conv.mcpack_path}")
        print(f"   • Geyser v2 Map   : {conv.mappings_v2_path}")
        print(f"   • Total Items     : {conv.total_items} ({conv.items_3d} 3D, {conv.items_2d} 2D)")
        print(f"   • Custom Blocks   : {conv.total_blocks}")
        print(f"   • Display Furn.   : {conv.total_furniture}")
        print(f"   • Custom Mobs     : {conv.total_mobs}")
        return 0

    if raw_args and raw_args[0] == "convert":
        raw_args = raw_args[1:]

    parser = build_arg_parser()
    args = parser.parse_args(raw_args)
    return _run_convert(args)


if __name__ == "__main__":
    raise SystemExit(main())
