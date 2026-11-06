#!/usr/bin/env python3
"""Diff two snapshot JSON files and report changed items only."""

import json
from pathlib import Path
import sys
from typing import Any, Dict, List


def diff_snapshots(snap_a: Dict[str, Any], snap_b: Dict[str, Any]) -> List[str]:
    changes: List[str] = []

    # Compare mappings
    all_map_keys = sorted(set(snap_a.get("mappings", {}).keys()) | set(snap_b.get("mappings", {}).keys()))
    for k in all_map_keys:
        val_a = snap_a.get("mappings", {}).get(k)
        val_b = snap_b.get("mappings", {}).get(k)
        if val_a != val_b:
            changes.append(f"[MAPPING CHANGED] {k}")

    # Compare items
    all_item_keys = sorted(set(snap_a.get("items", {}).keys()) | set(snap_b.get("items", {}).keys()))
    for k in all_item_keys:
        item_a = snap_a.get("items", {}).get(k)
        item_b = snap_b.get("items", {}).get(k)
        if item_a != item_b:
            subchanges = []
            if not item_a:
                subchanges.append("added")
            elif not item_b:
                subchanges.append("removed")
            else:
                for prop in ["materials", "geometry", "animations", "scripts", "animation_bones", "geo_hash", "bone_names", "root_binding"]:
                    if item_a.get(prop) != item_b.get(prop):
                        subchanges.append(prop)
            changes.append(f"[ITEM CHANGED] {k} ({', '.join(subchanges)})")

    return changes


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: diff_snapshots.py <snapshot_a.json> <snapshot_b.json>")
        return 1
    file_a = Path(sys.argv[1])
    file_b = Path(sys.argv[2])

    snap_a = json.loads(file_a.read_text(encoding="utf-8"))
    snap_b = json.loads(file_b.read_text(encoding="utf-8"))

    diffs = diff_snapshots(snap_a, snap_b)
    if diffs:
        print(f"Found {len(diffs)} difference(s):")
        for d in diffs:
            print(f"  • {d}")
        return 2
    else:
        print("Snapshots are identical!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
