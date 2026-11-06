"""Texture Atlas Stitcher, Multi-Layer 2D Compositor & Tintindex Processor."""

import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageChops, ImageDraw

from ..parser.item_parser import ParsedJavaModel, resolve_texture_path
from .armor_builder import KNOWN_ARMOR_HEX_COLORS, detect_armor_slot


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


def tint_armor_icon(img: Image.Image, rgb: Tuple[int, int, int]) -> Image.Image:
    """Tint a grayscale/iron armor icon into a custom material color (e.g. ruby, bronze)."""
    rgba = img.convert("RGBA")
    r_tint, g_tint, b_tint = rgb
    out_pixels = []
    for p in rgba.getdata():
        if p[3] > 0:
            gray = int(p[0] * 0.299 + p[1] * 0.587 + p[2] * 0.114)
            nr = min(255, int((gray / 255.0) * r_tint * 1.15))
            ng = min(255, int((gray / 255.0) * g_tint * 1.15))
            nb = min(255, int((gray / 255.0) * b_tint * 1.15))
            out_pixels.append((nr, ng, nb, p[3]))
        else:
            out_pixels.append((0, 0, 0, 0))
    out = Image.new("RGBA", rgba.size)
    out.putdata(out_pixels)
    return out


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
    """Composite layer0, layer1, layer2... for 2D models with optional 26.3 tinting and armor coloring."""
    armor_slot = detect_armor_slot(model)
    armor_tint_rgb = None
    if armor_slot:
        for name, rgb in KNOWN_ARMOR_HEX_COLORS.items():
            if name in model.short_name:
                armor_tint_rgb = rgb
                break

    layer_keys = sorted(
        [k for k in model.textures.keys() if k.startswith("layer") and k[5:].isdigit()],
        key=lambda x: int(x[5:]),
    )
    if not layer_keys:
        # Fallback to any available texture
        for val in model.textures.values():
            if "empty" in val:
                continue
            p = resolve_texture_path(pack_root, val, allow_vanilla_fallback=True)
            if p and p.is_file():
                with Image.open(p) as im:
                    base = im.convert("RGBA")
                if armor_tint_rgb:
                    base = tint_armor_icon(base, armor_tint_rgb)
                else:
                    tint_rgb = extract_tint_rgb_for_index(model.tints, 0)
                    if tint_rgb:
                        base = apply_rgb_tint(base, tint_rgb)
                return base
        return None

    composite: Optional[Image.Image] = None
    for lk in layer_keys:
        idx = int(lk[5:])
        tex_ref = model.textures[lk]
        if tex_ref.endswith("/empty") or tex_ref.endswith(":empty") or "empty.png" in tex_ref:
            continue
        p = resolve_texture_path(pack_root, tex_ref, allow_vanilla_fallback=True)
        if not p or not p.is_file():
            continue
        with Image.open(p) as im:
            layer_img = im.convert("RGBA")

        # Skip layers that are 100% transparent
        if layer_img.split()[3].getextrema()[1] == 0:
            continue

        if armor_tint_rgb and any(part in tex_ref for part in ("iron_helmet", "iron_chestplate", "iron_leggings", "iron_boots", "leather_")):
            layer_img = tint_armor_icon(layer_img, armor_tint_rgb)
        else:
            tint_rgb = extract_tint_rgb_for_index(model.tints, idx)
            if tint_rgb:
                layer_img = apply_rgb_tint(layer_img, tint_rgb)

        if composite is None:
            composite = layer_img
        else:
            if layer_img.size != composite.size:
                layer_img = layer_img.resize(composite.size, Image.Resampling.NEAREST)
            composite = Image.alpha_composite(composite, layer_img)

    if composite is None:
        for val in model.textures.values():
            if "empty" in val:
                continue
            p = resolve_texture_path(pack_root, val, allow_vanilla_fallback=True)
            if p and p.is_file():
                with Image.open(p) as im:
                    base = im.convert("RGBA")
                if armor_tint_rgb:
                    base = tint_armor_icon(base, armor_tint_rgb)
                else:
                    tint_rgb = extract_tint_rgb_for_index(model.tints, 0)
                    if tint_rgb:
                        base = apply_rgb_tint(base, tint_rgb)
                return base

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
        p = resolve_texture_path(pack_root, tex_ref, allow_vanilla_fallback=True)
        if p and p.is_file():
            key_to_path[k] = p
            if p not in loaded_by_path:
                with Image.open(p) as im:
                    img = im.convert("RGBA")
                # If image is a vertical animated sprite strip (e.g. 16x96 with 6 stacked frames),
                # crop the first square frame so static block and item models have crisp 1:1 UVs.
                if img.height > img.width and img.height % img.width == 0:
                    img = img.crop((0, 0, img.width, img.width))
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


def _solve_affine(
    src_tri: List[Tuple[float, float]], dst_tri: List[Tuple[float, float]]
) -> Optional[Tuple[float, ...]]:
    """Solve 2D affine transform matrix mapping src_tri to dst_tri."""
    (x0, y0), (x1, y1), (x2, y2) = dst_tri
    (u0, v0), (u1, v1), (u2, v2) = src_tri
    det = (x0 - x2) * (y1 - y2) - (x1 - x2) * (y0 - y2)
    if abs(det) < 1e-6:
        return None
    a = ((u0 - u2) * (y1 - y2) - (u1 - u2) * (y0 - y2)) / det
    b = ((x0 - x2) * (u1 - u2) - (x1 - x2) * (u0 - u2)) / det
    c = u0 - a * x0 - b * y0
    d = ((v0 - v2) * (y1 - y2) - (v1 - v2) * (y0 - y2)) / det
    e = ((x0 - x2) * (v1 - v2) - (x1 - x2) * (v0 - v2)) / det
    f = v0 - d * x0 - e * y0
    return (a, b, c, d, e, f)


def render_model_isometric(
    pack_root: Path,
    model: ParsedJavaModel,
    size: int = 32,
) -> Image.Image:
    """Render a 3D Java item/block model into an isometric 2D icon for Bedrock GUI/inventory."""
    elements = model.elements
    if not elements:
        comp = compose_2d_layered_texture(pack_root, model)
        if comp:
            return comp.resize((size, size), Image.Resampling.NEAREST)
        return Image.new("RGBA", (size, size), (255, 0, 255, 255))

    # Preload textures used by model
    loaded_textures: Dict[str, Image.Image] = {}
    for k, v in model.textures.items():
        if not v or v.startswith("#"):
            continue
        p = resolve_texture_path(pack_root, v, allow_vanilla_fallback=True)
        if p and p.is_file():
            try:
                with Image.open(p) as raw:
                    loaded_im = raw.convert("RGBA")
                    if loaded_im.height > loaded_im.width and loaded_im.height % loaded_im.width == 0:
                        loaded_im = loaded_im.crop((0, 0, loaded_im.width, loaded_im.width))
                    loaded_textures[k] = loaded_im
            except Exception:
                pass

    min_x = min(float(el.get("from", [0, 0, 0])[0]) for el in elements)
    max_x = max(float(el.get("to", [16, 16, 16])[0]) for el in elements)
    min_y = min(float(el.get("from", [0, 0, 0])[1]) for el in elements)
    max_y = max(float(el.get("to", [16, 16, 16])[1]) for el in elements)
    min_z = min(float(el.get("from", [0, 0, 0])[2]) for el in elements)
    max_z = max(float(el.get("to", [16, 16, 16])[2]) for el in elements)

    cx = (min_x + max_x) / 2.0
    cy = (min_y + max_y) / 2.0
    cz = (min_z + max_z) / 2.0

    # Extract display.gui rotation if available, otherwise default to standard Minecraft GUI Isometric
    gui_disp = model.display.get("gui", {}) if hasattr(model, "display") and model.display else {}
    gui_rot = gui_disp.get("rotation") if gui_disp else None

    # [30, 225, 0] in Minecraft coordinates is isometric (Pitch 30 deg, Yaw -45 deg)
    if not gui_rot or gui_rot == [30, 225, 0] or gui_rot == [30, -45, 0]:
        rx_deg, ry_deg, rz_deg = 30.0, -45.0, 0.0
        is_standard_iso = True
    else:
        rx_deg = float(gui_rot[0])
        ry_deg = float(gui_rot[1])
        rz_deg = float(gui_rot[2])
        is_standard_iso = False

    rad_x = math.radians(rx_deg)
    rad_y = math.radians(ry_deg)
    rad_z = math.radians(rz_deg)

    def _rot_x(x: float, y: float, z: float) -> Tuple[float, float, float]:
        return x, y * math.cos(rad_x) - z * math.sin(rad_x), y * math.sin(rad_x) + z * math.cos(rad_x)

    def _rot_y(x: float, y: float, z: float) -> Tuple[float, float, float]:
        return x * math.cos(rad_y) + z * math.sin(rad_y), y, -x * math.sin(rad_y) + z * math.cos(rad_y)

    def _rot_z(x: float, y: float, z: float) -> Tuple[float, float, float]:
        return x * math.cos(rad_z) - y * math.sin(rad_z), x * math.sin(rad_z) + y * math.cos(rad_z), z

    def _rotate(x: float, y: float, z: float) -> Tuple[float, float, float]:
        """Apply the GUI rotation.

        Java builds it as Quaternionf.rotationXYZ(rx, ry, rz) = Rx * Ry * Rz, so a vertex is
        rotated about Z first, then Y, then X. The legacy standard-isometric preset keeps its
        tuned X -> Y -> Z order so existing block icons do not change.
        """
        if is_standard_iso:
            return _rot_z(*_rot_y(*_rot_x(x, y, z)))
        return _rot_x(*_rot_y(*_rot_z(x, y, z)))

    def project_point(pt: Tuple[float, float, float]) -> Tuple[float, float, float]:
        return _rotate(pt[0] - cx, pt[1] - cy, pt[2] - cz)

    def rotate_normal(norm: Tuple[float, float, float]) -> float:
        return _rotate(norm[0], norm[1], norm[2])[2]

    # Dynamic scaling: compute projected bounding box to fit slot perfectly
    if is_standard_iso:
        max_dim = max(max_x - min_x, max_y - min_y, max_z - min_z, 1.0)
        scale = (size * 0.88) / (max_dim * 1.57)
    else:
        bbox_corners = [
            (min_x, min_y, min_z), (max_x, min_y, min_z),
            (min_x, max_y, min_z), (max_x, max_y, min_z),
            (min_x, min_y, max_z), (max_x, min_y, max_z),
            (min_x, max_y, max_z), (max_x, max_y, max_z),
        ]
        proj_corners = [project_point(c) for c in bbox_corners]
        span_x = max(p[0] for p in proj_corners) - min(p[0] for p in proj_corners)
        span_y = max(p[1] for p in proj_corners) - min(p[1] for p in proj_corners)
        span_max = max(span_x, span_y, 1.0)
        scale = (size * 0.90) / span_max

    # Face definitions with 3D normal vector & vertex winding order matching UV [top-left, top-right, bottom-right, bottom-left]
    face_defs = {
        "up":    ([3, 2, 6, 7], (0.0, 1.0, 0.0), 1.0),
        "down":  ([4, 5, 1, 0], (0.0, -1.0, 0.0), 0.5),
        "south": ([7, 6, 5, 4], (0.0, 0.0, 1.0), 0.8),
        "east":  ([6, 2, 1, 5], (1.0, 0.0, 0.0), 0.75),
        "north": ([2, 3, 0, 1], (0.0, 0.0, -1.0), 0.7),
        "west":  ([3, 7, 4, 0], (-1.0, 0.0, 0.0), 0.6),
    }

    quads = []
    for el in elements:
        x1, y1, z1 = [float(c) for c in el.get("from", [0, 0, 0])]
        x2, y2, z2 = [float(c) for c in el.get("to", [16, 16, 16])]
        v = [
            (x1, y1, z1), (x2, y1, z1), (x2, y2, z1), (x1, y2, z1),
            (x1, y1, z2), (x2, y1, z2), (x2, y2, z2), (x1, y2, z2),
        ]
        faces = el.get("faces", {})
        for f_name, f_data in faces.items():
            if f_name not in face_defs or not isinstance(f_data, dict):
                continue
            idx_list, normal_vec, shade = face_defs[f_name]

            # 3D Normal Back-face Culling: only faces pointing toward the camera are visible
            if rotate_normal(normal_vec) <= 0.05:
                continue

            pts_proj = [project_point(v[i]) for i in idx_list]

            avg_z = sum(p[2] for p in pts_proj) / 4.0
            t_key = str(f_data.get("texture", "")).lstrip("#")
            tex_img = loaded_textures.get(t_key)
            if not tex_img and loaded_textures:
                tex_img = next(iter(loaded_textures.values()))

            tintindex = f_data.get("tintindex")
            quads.append({
                "pts_proj": pts_proj,
                "avg_z": avg_z,
                "shade": shade,
                "tex_img": tex_img,
                "uv": f_data.get("uv", [0, 0, 16, 16]),
                "tintindex": tintindex,
            })

    quads.sort(key=lambda q: q["avg_z"])

    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    half = size / 2.0

    for q in quads:
        pts_2d = [(half + p[0] * scale, half - p[1] * scale) for p in q["pts_proj"]]
        tex = q["tex_img"]
        shade = q["shade"]
        fill_color = None
        painted = False

        if tex:
            uv = q["uv"]
            tw, th = tex.size
            u1 = int((uv[0] / 16.0) * tw)
            v1 = int((uv[1] / 16.0) * th)
            u2 = int((uv[2] / 16.0) * tw)
            v2 = int((uv[3] / 16.0) * th)
            box = (max(0, min(u1, u2)), max(0, min(v1, v2)), min(tw, max(u1, u2)), min(th, max(v1, v2)))
            if box[2] > box[0] and box[3] > box[1]:
                sub = tex.crop(box)
            else:
                sub = tex

            if q.get("tintindex") is not None and model.tints:
                t_rgb = extract_tint_rgb_for_index(model.tints, q["tintindex"])
                if t_rgb:
                    sub = apply_rgb_tint(sub, t_rgb)

            # Try textured quad mapping with affine transform
            if sub.width > 0 and sub.height > 0:
                sw, sh = sub.size
                if shade != 1.0:
                    sr, sg, sb, sa = sub.split()
                    sr = sr.point(lambda p: int(p * shade))
                    sg = sg.point(lambda p: int(p * shade))
                    sb = sb.point(lambda p: int(p * shade))
                    sub_shaded = Image.merge("RGBA", (sr, sg, sb, sa))
                else:
                    sub_shaded = sub

                params = _solve_affine([(0, 0), (sw, 0), (0, sh)], [pts_2d[0], pts_2d[1], pts_2d[3]])
                if params:
                    try:
                        warped = sub_shaded.transform(canvas.size, Image.Transform.AFFINE, params, resample=Image.Resampling.NEAREST)
                        mask = Image.new("L", canvas.size, 0)
                        ImageDraw.Draw(mask).polygon(pts_2d, fill=255)
                        canvas.paste(warped, (0, 0), mask)
                        draw.polygon(pts_2d, fill=None, outline=(0, 0, 0, 45))
                        painted = True
                    except Exception:
                        painted = False

            if not painted:
                avg_c = sub.resize((1, 1), Image.Resampling.BOX).getpixel((0, 0))
                if avg_c[3] > 0:
                    r = int(avg_c[0] * shade)
                    g = int(avg_c[1] * shade)
                    b = int(avg_c[2] * shade)
                    fill_color = (r, g, b, avg_c[3])

        if not painted:
            if not fill_color:
                c = int(180 * shade)
                fill_color = (c, c, c, 255)

            outline_color = (
                int(fill_color[0] * 0.8),
                int(fill_color[1] * 0.8),
                int(fill_color[2] * 0.8),
                fill_color[3],
            )
            draw.polygon(pts_2d, fill=fill_color, outline=outline_color)

    # Check if anything was rendered
    if canvas.split()[3].getextrema()[1] == 0:
        if loaded_textures:
            first_tex = next(iter(loaded_textures.values()))
            return first_tex.resize((size, size), Image.Resampling.NEAREST)
        return Image.new("RGBA", (size, size), (255, 0, 255, 255))

    return canvas
