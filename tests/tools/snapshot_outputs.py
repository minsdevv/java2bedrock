#!/usr/bin/env python3
"""Snapshot generator for Bedrock pack outputs and Geyser mappings."""

import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Dict


def generate_snapshot(pack_dir: Path, mappings_path: Path) -> Dict[str, Any]:
    snapshot: Dict[str, Any] = {
        "items": {},
        "mappings": {},
    }

    # 1. Parse mappings
    if mappings_path.is_file():
        map_json = json.loads(mappings_path.read_text(encoding="utf-8"))
        for base_item, defs in map_json.get("items", {}).items():
            for d in defs:
                b_id = d.get("bedrock_identifier", "")
                if b_id:
                    snapshot["mappings"][b_id] = {
                        "java_base_item": base_item,
                        "type": d.get("type"),
                        "model": d.get("model"),
                        "custom_model_data": d.get("custom_model_data"),
                        "bedrock_options": d.get("bedrock_options"),
                        "components": d.get("components"),
                    }

    # 2. Parse attachables, animations, and geometries
    attachables_dir = pack_dir / "attachables"
    if attachables_dir.is_dir():
        for att_file in sorted(attachables_dir.rglob("*.json")):
            try:
                data = json.loads(att_file.read_text(encoding="utf-8"))
                att = data.get("minecraft:attachable", {}).get("description", {})
                b_id = att.get("identifier", "")
                if not b_id:
                    continue

                item_info: Dict[str, Any] = {
                    "materials": att.get("materials"),
                    "geometry": att.get("geometry"),
                    "animations": att.get("animations"),
                    "scripts": att.get("scripts"),
                }

                # Read referenced animation file(s)
                anim_map = att.get("animations", {})
                item_info["animation_bones"] = {}
                for anim_slot, anim_id in anim_map.items():
                    # e.g. animation.j2b.xyz.third_person -> search in animations/
                    parts = anim_id.split(".")
                    if len(parts) >= 3:
                        short_name = parts[2]
                        anim_path = pack_dir / "animations" / "j2b" / f"{short_name}.animation.json"
                        if anim_path.is_file():
                            anim_data = json.loads(anim_path.read_text(encoding="utf-8"))
                            anim_def = anim_data.get("animations", {}).get(anim_id, {})
                            if "bones" in anim_def:
                                item_info["animation_bones"][anim_slot] = anim_def["bones"]

                # Read referenced geometry
                geo_id = att.get("geometry", {}).get("default", "")
                if geo_id:
                    parts = geo_id.split(".")
                    if len(parts) >= 3:
                        short_name = parts[2]
                        geo_path = pack_dir / "models" / "entity" / "j2b" / f"{short_name}.geo.json"
                        if geo_path.is_file():
                            geo_text = geo_path.read_text(encoding="utf-8")
                            item_info["geo_hash"] = hashlib.sha256(geo_text.encode("utf-8")).hexdigest()[:16]
                            geo_data = json.loads(geo_text)
                            geos = geo_data.get("minecraft:geometry", [])
                            if geos:
                                bones = geos[0].get("bones", [])
                                item_info["bone_names"] = [b.get("name") for b in bones]
                                item_info["root_binding"] = bones[0].get("binding") if bones else None

                snapshot["items"][b_id] = item_info
            except Exception as e:
                print(f"[WARN] Error reading attachable {att_file}: {e}", file=sys.stderr)

    return snapshot


def main() -> int:
    if len(sys.argv) < 4:
        print("Usage: snapshot_outputs.py <pack_dir> <mappings_json> <out_snapshot_json>")
        return 1
    pack_dir = Path(sys.argv[1])
    mappings_path = Path(sys.argv[2])
    out_path = Path(sys.argv[3])

    snap = generate_snapshot(pack_dir, mappings_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snap, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Snapshot written to {out_path} ({len(snap['items'])} items, {len(snap['mappings'])} mappings)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
