#!/usr/bin/env bash
# Remove the local model plugin installation from Claude Code.
# Run this before reinstalling to test a fresh state, or to clean up.
#
# Usage:
#   plugins/shared/uninstall.sh

set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
SKILLS_SRC="$REPO/src/sweet/skills"
CC_SKILLS="${HOME}/.claude/skills"
CC_MARKETPLACE="${HOME}/.claude/plugins/marketplaces/sweet-dev"
CC_KNOWN="${HOME}/.claude/plugins/known_marketplaces.json"

# Remove installed skills
for skill_dir in "$SKILLS_SRC"/*/; do
  [[ -d "$skill_dir" ]] || continue
  name="$(basename "$skill_dir")"
  dst="$CC_SKILLS/$name"
  if [[ -e "$dst" || -L "$dst" ]]; then
    rm -rf "$dst"
    echo "removed skill: $name"
  fi
done

# Remove marketplace directory
if [[ -e "$CC_MARKETPLACE" || -L "$CC_MARKETPLACE" ]]; then
  rm -rf "$CC_MARKETPLACE"
  echo "removed marketplace: sweet-dev"
fi

# Remove from known_marketplaces.json
python3 - <<PYEOF
import json, pathlib

path = pathlib.Path("$CC_KNOWN")
try:
    data = json.loads(path.read_text())
except (FileNotFoundError, json.JSONDecodeError):
    data = {}

if "sweet-dev" in data:
    del data["sweet-dev"]
    path.write_text(json.dumps(data, indent=2) + "\n")
    print("unregistered sweet-dev from", path)
else:
    print("sweet-dev not found in", path, "(already clean)")
PYEOF

echo ""
echo "Done. If the plugin was installed in Claude Code, also run:"
echo "  /plugin uninstall sweet"
