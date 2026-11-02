"""Blockbench (.bbmodel) Parser for Custom Mobs (ModelEngine / MythicMobs)."""

import base64
from dataclasses import dataclass, field
import io
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image


@dataclass
class BBModelBone:
    """Resolved bone in a Blockbench outliner hierarchy."""

    name: str
    uuid: str
    pivot: Tuple[float, float, float]
    rotation: Tuple[float, float, float]
    parent_name: Optional[str] = None
    cube_uuids: List[str] = field(default_factory=list)


@dataclass
class BBModelAnimation:
    """Parsed Blockbench keyframe animation."""

    name: str
    loop: str  # "loop" | "once" | "hold"
    length: float
    bone_channels: Dict[str, Dict[str, Dict[str, List[float]]]] = field(default_factory=dict)


@dataclass
class ParsedBBModelMob:
    """Complete parsed Blockbench .bbmodel mob blueprint."""

    mob_name: str  # e.g. "inferno_drake"
    bedrock_entity_id: str  # e.g. "j2b:mob_inferno_drake"
    tex_width: int
    tex_height: int
    elements_by_uuid: Dict[str, Dict[str, Any]]
    bones: List[BBModelBone]
    texture_image: Optional[Image.Image]
    animations: List[BBModelAnimation]


def _decode_bbmodel_texture(textures_list: List[Dict[str, Any]]) -> Optional[Image.Image]:
    """Decode the first embedded base64 data:image/png texture from a .bbmodel."""
    for tex in textures_list:
        if not isinstance(tex, dict):
            continue
        source = str(tex.get("source", ""))
        if "base64," in source:
            b64_part = source.split("base64,", 1)[1]
            try:
                raw_bytes = base64.b64decode(b64_part)
                with Image.open(io.BytesIO(raw_bytes)) as im:
                    return im.convert("RGBA")
            except Exception:
                continue
    return None


def _walk_outliner(
    nodes: List[Any],
    parent_name: Optional[str],
    bones_out: List[BBModelBone],
    uuid_to_bone_name: Dict[str, str],
) -> List[str]:
    """Recursively traverse Blockbench outliner tree, returning direct cube UUIDs at this level."""
    direct_cube_uuids: List[str] = []
    for item in nodes:
        if isinstance(item, str):
            direct_cube_uuids.append(item)
        elif isinstance(item, dict):
            b_name = str(item.get("name", f"bone_{len(bones_out)}")).replace(" ", "_").lower()
            b_uuid = str(item.get("uuid", b_name))
            orig = item.get("origin", [0.0, 0.0, 0.0])
            rot = item.get("rotation", [0.0, 0.0, 0.0])
            pivot = (float(orig[0]), float(orig[1]), float(orig[2]))
            rotation = (float(rot[0]), float(rot[1]), float(rot[2]))

            children = item.get("children", [])
            bone = BBModelBone(
                name=b_name,
                uuid=b_uuid,
                pivot=pivot,
                rotation=rotation,
                parent_name=parent_name,
                cube_uuids=[],
            )
            bones_out.append(bone)
            uuid_to_bone_name[b_uuid] = b_name
            bone.cube_uuids = _walk_outliner(
                children,
                parent_name=b_name,
                bones_out=bones_out,
                uuid_to_bone_name=uuid_to_bone_name,
            )
    return direct_cube_uuids


def _parse_bbmodel_animations(
    raw_anims: List[Dict[str, Any]],
    uuid_to_bone_name: Dict[str, str],
) -> List[BBModelAnimation]:
    """Convert Blockbench animation keyframes into Bedrock-ready bone channels."""
    parsed_anims: List[BBModelAnimation] = []
    for anim in raw_anims:
        if not isinstance(anim, dict):
            continue
        name = str(anim.get("name", "idle")).lower().replace(" ", "_")
        loop_mode = str(anim.get("loop", "loop"))
        length = float(anim.get("length", 1.0))
        animators = anim.get("animators", {})

        bone_channels: Dict[str, Dict[str, Dict[str, List[float]]]] = {}
        if isinstance(animators, dict):
            for anim_key, animator_data in animators.items():
                if not isinstance(animator_data, dict):
                    continue
                bone_name = uuid_to_bone_name.get(
                    anim_key,
                    str(animator_data.get("name", anim_key)).lower().replace(" ", "_"),
                )
                keyframes = animator_data.get("keyframes", [])
                if not isinstance(keyframes, list):
                    continue

                channels: Dict[str, Dict[str, List[float]]] = {}
                for kf in keyframes:
                    if not isinstance(kf, dict):
                        continue
                    ch_name = str(kf.get("channel", "rotation"))
                    if ch_name not in ("rotation", "position", "scale"):
                        continue
                    t_str = f"{float(kf.get('time', 0.0)):.4f}".rstrip("0").rstrip(".")
                    if not t_str:
                        t_str = "0.0"
                    dp_list = kf.get("data_points", [])
                    if dp_list and isinstance(dp_list[0], dict):
                        dp = dp_list[0]
                        x = float(dp.get("x", 0.0))
                        y = float(dp.get("y", 0.0))
                        z = float(dp.get("z", 0.0))
                        # Convert Blockbench keyframe signs to Bedrock bone space
                        if ch_name == "rotation":
                            vec = [round(-x, 4), round(-y, 4), round(z, 4)]
                        elif ch_name == "position":
                            vec = [round(-x, 4), round(y, 4), round(z, 4)]
                        else:
                            vec = [round(x, 4), round(y, 4), round(z, 4)]
                        channels.setdefault(ch_name, {})[t_str] = vec

                if channels:
                    bone_channels[bone_name] = channels

        parsed_anims.append(
            BBModelAnimation(
                name=name,
                loop=loop_mode,
                length=length,
                bone_channels=bone_channels,
            )
        )
    return parsed_anims


def parse_bbmodel_file(
    bbmodel_path: Path,
    bedrock_ns: str = "j2b",
) -> Optional[ParsedBBModelMob]:
    """Parse a single Blockbench .bbmodel file into a ParsedBBModelMob."""
    try:
        data = json.loads(bbmodel_path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None

    raw_name = data.get("model_identifier") or data.get("name") or bbmodel_path.stem
    mob_name = str(raw_name).lower().replace(" ", "_").replace("-", "_")

    res = data.get("resolution", {})
    tex_w = int(res.get("width", 64))
    tex_h = int(res.get("height", 64))

    elements_by_uuid: Dict[str, Dict[str, Any]] = {}
    for el in data.get("elements", []):
        if isinstance(el, dict) and "uuid" in el:
            elements_by_uuid[str(el["uuid"])] = el

    bones: List[BBModelBone] = []
    uuid_to_bone_name: Dict[str, str] = {}
    outliner = data.get("outliner", [])
    loose_cubes = _walk_outliner(outliner, None, bones, uuid_to_bone_name)

    if loose_cubes or not bones:
        root_bone = BBModelBone(
            name="root",
            uuid="root",
            pivot=(0.0, 0.0, 0.0),
            rotation=(0.0, 0.0, 0.0),
            parent_name=None,
            cube_uuids=loose_cubes or list(elements_by_uuid.keys()),
        )
        bones.insert(0, root_bone)

    tex_img = _decode_bbmodel_texture(data.get("textures", []))
    animations = _parse_bbmodel_animations(data.get("animations", []), uuid_to_bone_name)

    return ParsedBBModelMob(
        mob_name=mob_name,
        bedrock_entity_id=f"{bedrock_ns}:mob_{mob_name}",
        tex_width=tex_w,
        tex_height=tex_h,
        elements_by_uuid=elements_by_uuid,
        bones=bones,
        texture_image=tex_img,
        animations=animations,
    )


def parse_java_pack_bbmodels(
    pack_root: Path,
    bedrock_ns: str = "j2b",
) -> List[ParsedBBModelMob]:
    """Scan a pack or directory for all Blockbench .bbmodel mob blueprints."""
    results: List[ParsedBBModelMob] = []
    for bb_file in sorted(pack_root.rglob("*.bbmodel")):
        parsed = parse_bbmodel_file(bb_file, bedrock_ns=bedrock_ns)
        if parsed:
            results.append(parsed)
    return results
