#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SRC_DIR="$ROOT_DIR/skills"
DEST_DIR="${CODEX_HOME:-$HOME/.codex}/skills"

if [ ! -d "$SRC_DIR" ]; then
  echo "[ERROR] skills directory not found: $SRC_DIR" >&2
  exit 1
fi

mkdir -p "$DEST_DIR"

for skill_dir in "$SRC_DIR"/*; do
  [ -d "$skill_dir" ] || continue
  skill_name="$(basename "$skill_dir")"
  target_dir="$DEST_DIR/$skill_name"
  mkdir -p "$target_dir"
  cp -R "$skill_dir"/. "$target_dir"/
  echo "[OK] synced: $skill_name -> $target_dir"
done
