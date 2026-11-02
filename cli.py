#!/usr/bin/env python3
"""Command-Line Interface for Java2Bedrock Universal Converter."""

import argparse
import json
from pathlib import Path
import sys

from src.packager.zip_packager import convert_java_pack


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="java2bedrock",
        description=(
            "Convert Minecraft Java Edition Resource Packs (1.14 - 26.3+) "
            "into Bedrock Edition .mcpack and GeyserMC Custom Mappings."
        ),
    )
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
        "--summary-json",
        default=None,
        help="Write a JSON conversion summary report to the specified file path.",
    )
    parser.add_argument(
        "--summary-markdown",
        default=None,
        help="Write a Markdown conversion summary report (for GitHub Issues) to the specified path.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[ERROR] Input path does not exist: {input_path}", file=sys.stderr)
        return 1

    result = convert_java_pack(
        input_path=input_path,
        output_dir=Path(args.output),
        pack_name=args.name,
        bedrock_ns=args.namespace,
    )

    print(f"✅ Conversion completed for '{result.pack_meta.name}'")
    print(f"   • Pack Format     : {result.pack_meta.pack_format}")
    print(f"   • Namespaces      : {', '.join(result.pack_meta.namespaces) or 'none'}")
    print(f"   • Total Items     : {result.total_items} ({result.items_3d} 3D, {result.items_2d} 2D)")
    print(f"   • Bedrock .mcpack : {result.mcpack_path}")
    print(f"   • Geyser v2 Map   : {result.mappings_v2_path}")
    print(f"   • Geyser v1 Map   : {result.mappings_v1_path}")

    if args.summary_json:
        summary_data = {
            "pack_name": result.pack_meta.name,
            "description": result.pack_meta.description,
            "pack_format": result.pack_meta.pack_format,
            "namespaces": result.pack_meta.namespaces,
            "total_items": result.total_items,
            "items_3d": result.items_3d,
            "items_2d": result.items_2d,
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
            f"| **File Bedrock Pack** | `{result.mcpack_path.name}` |",
            f"| **Geyser Mappings (v2 / 26.3)** | `custom_mappings/items_v2.json` |",
            f"| **Geyser Mappings (v1 Legacy)** | `custom_mappings/items_v1.json` |",
            "",
        ]
        if result.warnings:
            md_lines.append("### ⚠️ Cảnh báo trong quá trình chuyển đổi")
            for w in result.warnings[:15]:
                md_lines.append(f"- {w}")
            md_lines.append("")
        Path(args.summary_markdown).write_text("\n".join(md_lines), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
