#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GEYSER_JAR="${GEYSER_JAR:-/home/minsdev/Workspaces/Minecraft/mcsrv/plugins/Geyser-Spigot.jar}"
CLASSES_DIR="${SCRIPT_DIR}/build/classes"
OUT_JAR="${SCRIPT_DIR}/J2BCompanionExtension.jar"

rm -rf "${CLASSES_DIR}"
mkdir -p "${CLASSES_DIR}"

javac --release 17 \
  -cp "${GEYSER_JAR}" \
  -d "${CLASSES_DIR}" \
  "${SCRIPT_DIR}/src/main/java/org/j2b/extension/J2BCompanionExtension.java"

cp "${SCRIPT_DIR}/src/main/resources/extension.yml" "${CLASSES_DIR}/extension.yml"
jar --create --file "${OUT_JAR}" -C "${CLASSES_DIR}" .
rm -rf "${SCRIPT_DIR}/build"

echo "✅ Built ${OUT_JAR}"
