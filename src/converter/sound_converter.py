"""Converter for Java Resource Pack Sounds -> Bedrock sound_definitions.json & Audio Assets."""

import json
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional, Tuple, Union


VALID_BEDROCK_CATEGORIES = {
    "ambient",
    "block",
    "bottle",
    "bucket",
    "fizz",
    "furnace",
    "hostile",
    "item",
    "music",
    "neutral",
    "player",
    "record",
    "ui",
    "weather",
}


def _infer_category(event_name: str, file_path_str: str, raw_category: Optional[str] = None) -> str:
    """Infer a valid Bedrock sound category."""
    if raw_category and raw_category.lower() in VALID_BEDROCK_CATEGORIES:
        return raw_category.lower()

    lower = (event_name + " " + file_path_str).lower()
    if "music_disc" in lower or "record" in lower:
        return "record"
    if "music" in lower:
        return "music"
    if "ambient" in lower or "creepy" in lower:
        return "ambient"
    if "ui" in lower or "click" in lower:
        return "ui"
    if "block" in lower or "step" in lower or "dig" in lower:
        return "block"
    if "hostile" in lower or "monster" in lower:
        return "hostile"
    if "player" in lower:
        return "player"
    return "neutral"


def convert_java_pack_sounds(
    pack_root: Path,
    bedrock_dir: Path,
    bedrock_ns: str = "j2b",
) -> Tuple[int, List[str]]:
    """Convert Java assets/<ns>/sounds.json and .ogg audio files to Bedrock.

    Returns:
        (total_sounds_converted, warnings_list)
    """
    pack_root = Path(pack_root)
    bedrock_dir = Path(bedrock_dir)
    sounds_dest_dir = bedrock_dir / "sounds"
    sounds_dest_dir.mkdir(parents=True, exist_ok=True)

    warnings: List[str] = []
    sound_definitions: Dict[str, Any] = {}
    copied_files_count = 0

    assets_dir = pack_root / "assets"
    if not assets_dir.is_dir():
        return 0, warnings

    for ns_dir in sorted(assets_dir.iterdir()):
        if not ns_dir.is_dir() or ns_dir.name.startswith("."):
            continue
        ns = ns_dir.name

        # 1. Copy all audio files (.ogg, .fsb, .wav) into sounds/<ns>/...
        src_sounds_dir = ns_dir / "sounds"
        if src_sounds_dir.is_dir():
            for audio_file in src_sounds_dir.rglob("*"):
                if audio_file.is_file() and audio_file.suffix.lower() in (".ogg", ".fsb", ".wav"):
                    rel = audio_file.relative_to(src_sounds_dir)
                    dest_file = sounds_dest_dir / ns / rel
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(audio_file, dest_file)
                    copied_files_count += 1

        # 2. Parse assets/<ns>/sounds.json if present
        sounds_json = ns_dir / "sounds.json"
        parsed_events = set()
        if sounds_json.is_file():
            try:
                data = json.loads(sounds_json.read_text(encoding="utf-8"))
                for event_name, event_data in data.items():
                    if not isinstance(event_data, dict):
                        continue
                    parsed_events.add(event_name)
                    raw_cat = event_data.get("category")
                    raw_sounds = event_data.get("sounds", [])

                    bedrock_sound_list: List[Dict[str, Any]] = []
                    for s_item in raw_sounds:
                        if isinstance(s_item, str):
                            raw_path = s_item
                            vol = 1.0
                            pitch = 1.0
                        elif isinstance(s_item, dict):
                            raw_path = str(s_item.get("name", ""))
                            vol = float(s_item.get("volume", 1.0))
                            pitch = float(s_item.get("pitch", 1.0))
                        else:
                            continue

                        # Parse namespace prefix: "iaalchemy:ambient/creepy1" -> "sounds/iaalchemy/ambient/creepy1"
                        if ":" in raw_path:
                            target_ns, sound_subpath = raw_path.split(":", 1)
                        else:
                            target_ns, sound_subpath = ns, raw_path

                        sound_rel_bedrock = f"sounds/{target_ns}/{sound_subpath}".replace("\\", "/")
                        bedrock_sound_list.append(
                            {
                                "name": sound_rel_bedrock,
                                "volume": vol,
                                "pitch": pitch,
                            }
                        )

                    category = _infer_category(event_name, str(raw_sounds), raw_cat)
                    def_obj = {
                        "category": category,
                        "sounds": bedrock_sound_list if bedrock_sound_list else [],
                    }

                    # Register both namespaced event and short event name
                    namespaced_key = f"{ns}.{event_name}"
                    sound_definitions[namespaced_key] = def_obj
                    if event_name not in sound_definitions:
                        sound_definitions[event_name] = def_obj

            except Exception as e:
                warnings.append(f"Failed to parse {sounds_json}: {e}")

        # 3. Auto-register any audio files in sounds/<ns>/ that were not explicitly in sounds.json
        if src_sounds_dir.is_dir():
            for audio_file in src_sounds_dir.rglob("*.ogg"):
                rel_stem = str(audio_file.relative_to(src_sounds_dir).with_suffix("")).replace("\\", "/")
                auto_key = f"{ns}.{rel_stem.replace('/', '.')}"
                if auto_key not in sound_definitions:
                    category = _infer_category(rel_stem, rel_stem)
                    def_obj = {
                        "category": category,
                        "sounds": [
                            {
                                "name": f"sounds/{ns}/{rel_stem}",
                                "volume": 1.0,
                                "pitch": 1.0,
                            }
                        ],
                    }
                    sound_definitions[auto_key] = def_obj
                    if rel_stem not in sound_definitions:
                        sound_definitions[rel_stem] = def_obj

    if sound_definitions:
        doc = {
            "format_version": "1.20.20",
            "sound_definitions": sound_definitions,
        }
        out_file = bedrock_dir / "sounds" / "sound_definitions.json"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    return copied_files_count, warnings
