"""Texture Atlas Stitcher, Multi-Layer 2D Compositor & Tintindex Processor."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageChops

from ..parser.item_parser import ParsedJavaModel, resolve_texture_path


def int_color_to_rgb(color_val: Any) -> Tuple[int, int, int]:
    """Convert an integer RGB value (e.g. 0xFF5500) or [r, g, b] list into (R, G, B) 0..255."""
    if isinstance(color_val, int):
        r = (color_val >> 16) & 0xFF
        g = (color_val >> 8) & 0xFF
        b = color_val & 0xFF
        return r, g, b
    if isinstance(color_val, (list, tuple)) and len(color_val) >= 3:
        vals = [float(x) for x in color_val[:3]]
        if all(0.0 <= x <= 1.0 for x in vals) and any(isinstance(x, float) for x in color_val[:3]):
            return int(vals[0] * 255), int(vals[1] * 255), int(vals[2] * 255)
        return int(vals[0]), int(vals[1]), int(vals[2])
    return 255, 255, 255


def apply_rgb_tint(img: Image.Image, rgb: Tuple[int, int, int]) -> Image.Image:
    """Multiply an RGBA image by an (R, G, B) tint color while preserving alpha."""
    rgba = img.convert("RGBA")
    if rgb == (255, 255, 255):
        return rgba
    tint_layer = Image.new("RGBA", rgba.size, (rgb[0], rgb[1], rgb[2], 255))
    multiplied = ImageChops.multiply(rgba, tint_layer)
    # Preserve original alpha channel exactly
    r, g, b, _ = multiplied.split()
    _, _, _, a = rgba.split()
    return Image.merge("RGBA", (r, g, b, a))


def extract_tint_rgb_for_index(tints: List[Dict[str, Any]], index: int) -> Optional[Tuple[int, int, int]]:
    """Extract RGB tint from Minecraft 26.3 tint definition for a given layer/tintindex."""
    if index < 0 or index >= len(tints):
        return None
    tint_entry = tints[index]
    if not isinstance(tint_entry, dict):
        return None
    if "value" in tint_entry:
        return int_color_to_rgb(tint_entry["value"])
    if "default" in tint_entry:
        return int_color_to_rgb(tint_entry["default"])
    # Default fallback colors for grass/foliage/potion if unspecified
    t_type = str(tint_entry.get("type", ""))
    if "grass" in t_type or "foliage" in t_type:
        return (121, 192, 90)
    return None


def compose_2d_layered_texture(
    pack_root: Path,
    model: ParsedJavaModel,
) -> Optional[Image.Image]:
    """Composite layer0, layer1, layer2... for 2D models with optional 26.3 tinting."""
    layer_keys = sorted(
        [k for k in model.textures.keys() if k.startswith("layer") and k[5:].isdigit()],
        key=lambda x: int(x[5:]),
    )
    if not layer_keys:
        # Fallback to any available texture
        for val in model.textures.values():
            p = resolve_texture_path(pack_root, val)
            if p and p.is_file():
                with Image.open(p) as im:
                    base = im.convert("RGBA")
                tint_rgb = extract_tint_rgb_for_index(model.tints, 0)
                if tint_rgb:
                    base = apply_rgb_tint(base, tint_rgb)
                return base
        return None

    composite: Optional[Image.Image] = None
    for lk in layer_keys:
        idx = int(lk[5:])
        tex_ref = model.textures[lk]
        p = resolve_texture_path(pack_root, tex_ref)
        if not p or not p.is_file():
            continue
        with Image.open(p) as im:
            layer_img = im.convert("RGBA")
        tint_rgb = extract_tint_rgb_for_index(model.tints, idx)
        if tint_rgb:
            layer_img = apply_rgb_tint(layer_img, tint_rgb)

        if composite is None:
            composite = layer_img
        else:
            if layer_img.size != composite.size:
                layer_img = layer_img.resize(composite.size, Image.Resampling.NEAREST)
            composite = Image.alpha_composite(composite, layer_img)

    return composite


def build_model_texture_atlas(
    pack_root: Path,
    model: ParsedJavaModel,
) -> Tuple[Optional[Image.Image], int, int, Dict[str, Tuple[int, int, int, int]]]:
    """Stitch multiple 3D model textures into a single Bedrock texture atlas if needed.

    Returns:
        (atlas_image, total_width, total_height, uv_offsets_by_key)
    """
    # Collect all texture keys actually used by element faces or defined in textures
    used_keys: List[str] = []
    face_tint_by_key: Dict[str, int] = {}

    for elem in model.elements:
        for face_data in elem.get("faces", {}).values():
            if isinstance(face_data, dict):
                t_key = str(face_data.get("texture", "")).lstrip("#")
                if t_key and t_key not in used_keys:
                    used_keys.append(t_key)
                if "tintindex" in face_data and t_key:
                    face_tint_by_key[t_key] = int(face_data["tintindex"])

    for k in model.textures.keys():
        if k != "particle" and k not in used_keys:
            used_keys.append(k)

    loaded_by_path: Dict[Path, Image.Image] = {}
    key_to_path: Dict[str, Path] = {}

    for k in used_keys:
        tex_ref = model.textures.get(k)
        if not tex_ref:
            continue
        p = resolve_texture_path(pack_root, tex_ref)
        if p and p.is_file():
            key_to_path[k] = p
            if p not in loaded_by_path:
                with Image.open(p) as im:
                    img = im.convert("RGBA")
                # Apply tint if face has tintindex and model specifies tints
                if k in face_tint_by_key:
                    tint_rgb = extract_tint_rgb_for_index(model.tints, face_tint_by_key[k])
                    if tint_rgb:
                        img = apply_rgb_tint(img, tint_rgb)
                elif model.tints:
                    tint_rgb = extract_tint_rgb_for_index(model.tints, 0)
                    if tint_rgb and any("tintindex" in fd for el in model.elements for fd in el.get("faces", {}).values() if isinstance(fd, dict)):
                        img = apply_rgb_tint(img, tint_rgb)
                loaded_by_path[p] = img

    if not loaded_by_path:
        return None, 16, 16, {}

    # Single unique texture file -> no stitching needed
    if len(loaded_by_path) == 1:
        only_path, only_img = next(iter(loaded_by_path.items()))
        w, h = only_img.size
        uv_offsets = {k: (0, 0, w, h) for k in key_to_path}
        return only_img, w, h, uv_offsets

    # Multiple distinct textures -> stitch horizontally into an atlas
    unique_paths = list(loaded_by_path.keys())
    total_w = sum(loaded_by_path[p].width for p in unique_paths)
    max_h = max(loaded_by_path[p].height for p in unique_paths)

    atlas = Image.new("RGBA", (total_w, max_h), (0, 0, 0, 0))
    path_offsets: Dict[Path, Tuple[int, int, int, int]] = {}
    cur_x = 0
    for p in unique_paths:
        sub_img = loaded_by_path[p]
        atlas.paste(sub_img, (cur_x, 0))
        path_offsets[p] = (cur_x, 0, sub_img.width, sub_img.height)
        cur_x += sub_img.width

    uv_offsets = {k: path_offsets[p] for k, p in key_to_path.items()}
    return atlas, total_w, max_h, uv_offsets
