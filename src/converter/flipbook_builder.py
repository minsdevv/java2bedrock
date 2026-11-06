"""Converter for Java .mcmeta animations to Bedrock textures/flipbook_textures.json."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def parse_mcmeta_animation(mcmeta_path: Path) -> Optional[Dict[str, Any]]:
    """Parse a Java .png.mcmeta file and extract Bedrock flipbook parameters."""
    if not mcmeta_path.is_file():
        return None

    try:
        data = json.loads(mcmeta_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    anim = data.get("animation")
    if not isinstance(anim, dict):
        return None

    frametime = int(anim.get("frametime", 1))
    if frametime <= 0:
        frametime = 1

    interpolate = bool(anim.get("interpolate", False))
    raw_frames = anim.get("frames")

    frame_indices: Optional[List[int]] = None
    ticks_per_frame = frametime

    if isinstance(raw_frames, list) and raw_frames:
        if all(isinstance(f, int) for f in raw_frames):
            frame_indices = [int(f) for f in raw_frames]
        elif all(isinstance(f, dict) for f in raw_frames):
            # Check if all frame objects share the same frame time
            times = [f.get("time", frametime) for f in raw_frames]
            if len(set(times)) == 1:
                ticks_per_frame = int(times[0])
                frame_indices = [int(f.get("index", 0)) for f in raw_frames]
            else:
                # Expand variable time frames into repeated indices
                ticks_per_frame = 1
                expanded: List[int] = []
                for f in raw_frames:
                    idx = int(f.get("index", 0))
                    duration = max(1, int(f.get("time", frametime)))
                    expanded.extend([idx] * duration)
                frame_indices = expanded

    return {
        "ticks_per_frame": ticks_per_frame,
        "blend_frames": interpolate,
        "frames": frame_indices,
    }


def build_flipbook_entry(
    texture_rel: str,
    atlas_tile: str,
    anim_params: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a single entry for Bedrock textures/flipbook_textures.json."""
    clean_tex = texture_rel[:-4] if texture_rel.endswith(".png") else texture_rel
    entry: Dict[str, Any] = {
        "flipbook_texture": clean_tex,
        "atlas_tile": atlas_tile,
        "ticks_per_frame": int(anim_params.get("ticks_per_frame", 1)),
    }
    if anim_params.get("blend_frames"):
        entry["blend_frames"] = True
    if anim_params.get("frames"):
        entry["frames"] = anim_params["frames"]
    return entry
