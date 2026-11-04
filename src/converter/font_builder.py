"""Converter for Java Custom Font Bitmap Providers (default.json) -> Bedrock Glyph Sheets (font/glyph_XX.png)."""

import json
from pathlib import Path
import re
from typing import Dict, List, Tuple

from PIL import Image

from ..parser.item_parser import normalize_identifier


def _load_json_lenient(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    # Remove leading zeros in numeric values (e.g. : 010811 -> : 10811)
    cleaned = re.sub(r"(:\s*)0+([1-9]\d*)", r"\1\2", raw)
    # Remove trailing commas before } or ]
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
    return json.loads(cleaned)


def convert_java_bitmap_fonts(
    pack_root: Path,
    bedrock_dir: Path,
    filter_gui_backgrounds: bool = True,
) -> int:
    """Convert Java assets/*/font/*.json bitmap glyphs (PUA U+E000..U+F8FF) into Bedrock font/glyph_XX.png sheets.

    Returns:
        Total number of custom bitmap characters converted.
    """
    assets_dir = pack_root / "assets"
    if not assets_dir.is_dir():
        return 0

    # page_hex (e.g. 0xE8) -> {(row, col): Image}
    glyphs_by_page: Dict[int, Dict[Tuple[int, int], Image.Image]] = {}
    total_chars = 0

    for ns_dir in sorted(assets_dir.iterdir()):
        font_dir = ns_dir / "font"
        if not font_dir.is_dir():
            continue
        for font_file in sorted(font_dir.rglob("*.json")):
            try:
                data = _load_json_lenient(font_file)
            except Exception:
                continue

            providers = data.get("providers", [])
            if not isinstance(providers, list):
                continue

            for prov in providers:
                if not isinstance(prov, dict) or prov.get("type") != "bitmap":
                    continue
                file_ref = prov.get("file", "")
                chars_rows: List[str] = prov.get("chars", [])
                if not file_ref or not chars_rows:
                    continue

                ns, rel_tex = normalize_identifier(file_ref, default_namespace=ns_dir.name)
                if rel_tex.startswith("textures/"):
                    rel_tex = rel_tex[len("textures/") :]
                if not rel_tex.endswith(".png"):
                    rel_tex = f"{rel_tex}.png"

                png_path = pack_root / "assets" / ns / "textures" / rel_tex
                if not png_path.is_file():
                    continue

                try:
                    with Image.open(png_path) as src_im:
                        full_img = src_im.convert("RGBA")
                except Exception:
                    continue

                # Filter out oversized GUI background sheets (e.g. 192x170 chest backgrounds)
                # that Java uses for title-based fullscreen overlays, as Bedrock cannot overflow them.
                if filter_gui_backgrounds:
                    prov_h = int(prov.get("height", 0))
                    if prov_h > 48 or full_img.width > 96 or full_img.height > 96:
                        continue

                num_rows = len(chars_rows)
                num_cols = max((len(r) for r in chars_rows), default=1)
                if num_rows == 0 or num_cols == 0:
                    continue

                cell_w = max(1, full_img.width // num_cols)
                cell_h = max(1, full_img.height // num_rows)

                for r_idx, row_str in enumerate(chars_rows):
                    for c_idx, ch in enumerate(row_str):
                        codepoint = ord(ch)
                        if codepoint == 0 or codepoint < 0xE000 or codepoint > 0xFFFF:
                            continue
                        page = (codepoint >> 8) & 0xFF
                        low = codepoint & 0xFF
                        grid_row = (low >> 4) & 0x0F
                        grid_col = low & 0x0F

                        crop_box = (
                            c_idx * cell_w,
                            r_idx * cell_h,
                            (c_idx + 1) * cell_w,
                            (r_idx + 1) * cell_h,
                        )
                        sub_glyph = full_img.crop(crop_box)
                        glyphs_by_page.setdefault(page, {})[(grid_row, grid_col)] = sub_glyph
                        total_chars += 1

    if not glyphs_by_page:
        return 0

    out_font_dir = bedrock_dir / "font"
    out_font_dir.mkdir(parents=True, exist_ok=True)

    for page, cell_map in sorted(glyphs_by_page.items()):
        # Determine cell size (minimum 16x16, or power-of-two multiple up to 64x64)
        max_dim = max(
            max(im.width, im.height) for im in cell_map.values()
        )
        slot_size = 16
        while slot_size < max_dim and slot_size < 64:
            slot_size *= 2

        sheet_size = slot_size * 16
        sheet = Image.new("RGBA", (sheet_size, sheet_size), (0, 0, 0, 0))

        for (g_row, g_col), glyph_img in cell_map.items():
            # Fit glyph proportionally inside slot_size x slot_size
            gw, gh = glyph_img.size
            if gw > slot_size or gh > slot_size:
                scale = min(slot_size / gw, slot_size / gh)
                new_w = max(1, int(round(gw * scale)))
                new_h = max(1, int(round(gh * scale)))
                glyph_img = glyph_img.resize((new_w, new_h), Image.Resampling.NEAREST)
                gw, gh = glyph_img.size

            paste_x = g_col * slot_size + (slot_size - gw) // 2
            paste_y = g_row * slot_size + (slot_size - gh) // 2
            sheet.paste(glyph_img, (paste_x, paste_y))

        sheet_path = out_font_dir / f"glyph_{page:02X}.png"
        sheet.save(sheet_path)

    return total_chars
