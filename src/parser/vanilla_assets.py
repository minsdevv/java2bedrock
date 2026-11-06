"""Persistent vanilla Java texture cache used when a pack references `minecraft:` textures.

Resolution order for the cache:
  1. $J2B_VANILLA_ASSETS (directory containing assets/minecraft/textures)
  2. ~/.cache/java2bedrock/vanilla_assets (auto-populated)
Population sources, first that works:
  a. a local client jar (PrismLauncher libraries, ~/.minecraft/versions, $J2B_VANILLA_JAR)
  b. download of the latest release client jar from Mojang's version manifest.
"""

import json
import os
import re
from pathlib import Path
import shutil
import tempfile
from typing import List, Optional
import urllib.request
import zipfile

_MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
_cached: Optional[Path] = None
_attempted = False


def _cache_root() -> Path:
    env = os.environ.get("J2B_VANILLA_ASSETS")
    if env:
        return Path(env)
    return Path.home() / ".cache" / "java2bedrock" / "vanilla_assets"


def _textures_dir(root: Path) -> Path:
    return root / "assets" / "minecraft" / "textures"


def _version_key(p: Path):
    nums = re.findall(r"\d+", p.name)
    return [int(n) for n in nums]


def _local_client_jars() -> List[Path]:
    jars: List[Path] = []
    env = os.environ.get("J2B_VANILLA_JAR")
    if env and Path(env).is_file():
        jars.append(Path(env))
    home = Path.home()
    patterns = [
        (home / ".local/share/PrismLauncher/libraries/com/mojang/minecraft", "*/minecraft-*-client.jar"),
        (home / ".minecraft/versions", "*/*.jar"),
    ]
    for base, pat in patterns:
        if base.is_dir():
            found = [p for p in base.glob(pat) if "intermediary" not in p.name]
            jars.extend(sorted(found, key=lambda p: _version_key(p), reverse=True))
    return jars


def _extract_textures(jar: Path, root: Path) -> bool:
    try:
        with zipfile.ZipFile(jar) as zf:
            names = [n for n in zf.namelist() if n.startswith("assets/minecraft/textures/")]
            if not names:
                return False
            tmp = Path(tempfile.mkdtemp(prefix="j2b_vanilla_"))
            for n in names:
                zf.extract(n, tmp)
        root.parent.mkdir(parents=True, exist_ok=True)
        if root.exists():
            shutil.rmtree(root)
        shutil.move(str(tmp), str(root))
        return True
    except Exception:
        return False


def _download_client_jar() -> Optional[Path]:
    try:
        with urllib.request.urlopen(_MANIFEST_URL, timeout=30) as r:
            manifest = json.load(r)
        latest = manifest["latest"]["release"]
        url = next(v["url"] for v in manifest["versions"] if v["id"] == latest)
        with urllib.request.urlopen(url, timeout=30) as r:
            ver = json.load(r)
        jar_url = ver["downloads"]["client"]["url"]
        dest = Path(tempfile.mkdtemp(prefix="j2b_client_")) / "client.jar"
        with urllib.request.urlopen(jar_url, timeout=300) as r, open(dest, "wb") as f:
            shutil.copyfileobj(r, f)
        return dest
    except Exception:
        return None


def get_vanilla_textures_dir() -> Optional[Path]:
    """Return the vanilla textures directory, populating the persistent cache if needed."""
    global _cached, _attempted
    if _cached is not None:
        return _cached
    root = _cache_root()
    if _textures_dir(root).is_dir():
        _cached = _textures_dir(root)
        return _cached
    if _attempted:
        return None
    _attempted = True
    for jar in _local_client_jars():
        if _extract_textures(jar, root):
            _cached = _textures_dir(root)
            return _cached
    jar = _download_client_jar()
    if jar and _extract_textures(jar, root):
        _cached = _textures_dir(root)
        return _cached
    return None
