"""Structured conversion report builder for Java-to-Bedrock assets."""

from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class AssetStatus(str, Enum):
    CONVERTED = "converted"
    APPROXIMATED = "approximated"
    SKIPPED = "skipped"


@dataclass
class AssetReport:
    """Detailed conversion status and trace for a single asset."""

    id: str
    kind: str  # item, block, furniture, mob, font, sound, armor
    status: AssetStatus = AssetStatus.CONVERTED
    reasons: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "status": self.status.value,
            "reasons": self.reasons,
            "outputs": self.outputs,
        }


@dataclass
class ConversionReport:
    """Full conversion report holding per-asset statuses, totals and warnings."""

    pack: Dict[str, Any] = field(default_factory=dict)
    totals: Dict[str, int] = field(default_factory=dict)
    assets: List[AssetReport] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_asset(
        self,
        asset_id: str,
        kind: str,
        status: AssetStatus = AssetStatus.CONVERTED,
        reasons: Optional[List[str]] = None,
        outputs: Optional[List[str]] = None,
    ) -> AssetReport:
        rep = AssetReport(
            id=asset_id,
            kind=kind,
            status=status,
            reasons=reasons or [],
            outputs=outputs or [],
        )
        self.assets.append(rep)
        return rep

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pack": self.pack,
            "totals": self.totals,
            "summary_by_status": {
                "converted": sum(1 for a in self.assets if a.status == AssetStatus.CONVERTED),
                "approximated": sum(1 for a in self.assets if a.status == AssetStatus.APPROXIMATED),
                "skipped": sum(1 for a in self.assets if a.status == AssetStatus.SKIPPED),
            },
            "assets": [a.to_dict() for a in self.assets],
            "warnings": self.warnings,
        }

    def write_json(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
