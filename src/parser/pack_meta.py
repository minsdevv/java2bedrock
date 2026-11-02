"""Parser for Minecraft Java Edition pack.mcmeta and namespace discovery."""

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class PackMetadata:
    """Represents metadata of a Java Edition Resource Pack."""

    name: str
    description: str
    pack_format: int
    supported_formats: Optional[Any] = None
    namespaces: List[str] = field(default_factory=list)
    root_dir: Path = field(default_factory=Path)


def _extract_text_from_component(desc: Any) -> str:
    """Extract plain text from string or modern JSON text component."""
    if isinstance(desc, str):
        return desc
    if isinstance(desc, dict):
        parts = []
        if "text" in desc and isinstance(desc["text"], str):
            parts.append(desc["text"])
        if "translate" in desc and isinstance(desc["translate"], str):
            parts.append(desc["translate"])
        if "extra" in desc and isinstance(desc["extra"], list):
            for item in desc["extra"]:
                parts.append(_extract_text_from_component(item))
        return "".join(parts)
    if isinstance(desc, list):
        return "".join(_extract_text_from_component(x) for x in desc)
    return str(desc)


def parse_pack_meta(pack_dir: Path, fallback_name: str = "ConvertedBedrockPack") -> PackMetadata:
    """Parse pack.mcmeta and discover asset namespaces in a Java pack directory."""
    pack_dir = Path(pack_dir).resolve()
    mcmeta_path = pack_dir / "pack.mcmeta"

    pack_format = 46  # Default to 1.21.4+ / 26.x format
    description = "Converted by Java2Bedrock Universal"
    supported_formats = None

    if mcmeta_path.is_file():
        try:
            raw = json.loads(mcmeta_path.read_text(encoding="utf-8-sig"))
            pack_section: Dict[str, Any] = raw.get("pack", {})
            pack_format = int(pack_section.get("pack_format", pack_format))
            supported_formats = pack_section.get("supported_formats")
            if "description" in pack_section:
                description = _extract_text_from_component(pack_section["description"]).strip()
        except Exception:
            pass

    assets_dir = pack_dir / "assets"
    namespaces: List[str] = []
    if assets_dir.is_dir():
        for child in sorted(assets_dir.iterdir()):
            if child.is_dir() and not child.name.startswith("."):
                namespaces.append(child.name)

    name = pack_dir.name if pack_dir.name and pack_dir.name != "." else fallback_name
    return PackMetadata(
        name=name,
        description=description or "Converted by Java2Bedrock Universal",
        pack_format=pack_format,
        supported_formats=supported_formats,
        namespaces=namespaces,
        root_dir=pack_dir,
    )
