#!/usr/bin/env bash
# Install the model plugin into a local Claude Code for dev testing.
# Idempotent — safe to re-run after making changes.
#
# What this does:
#   1. Symlinks each skill to ~/.claude/skills/<name>/
#   2. Creates ~/.claude/plugins/marketplaces/expression-dev/ pointing at
#      plugins/claude/ and registers it in known_marketplaces.json.
#
# After running, inside Claude Code:
#   /plugin install expression@expression-dev
#
# Usage:
#   plugins/shared/install.sh

set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
SKILLS_SRC="$REPO/src/expression/skills"
CC_SKILLS="${HOME}/.claude/skills"
CC_MARKETPLACE="${HOME}/.claude/plugins/marketplaces/expression-dev"
CC_KNOWN="${HOME}/.claude/plugins/known_marketplaces.json"
NOW="$(date -u +%Y-%m-%dT%H:%M:%S.000Z)"

# --------------------------------------------------------------------------
# 1. Install skills into ~/.claude/skills/
# --------------------------------------------------------------------------
mkdir -p "$CC_SKILLS"

for skill_dir in "$SKILLS_SRC"/*/; do
  [[ -d "$skill_dir" ]] || continue
  name="$(basename "$skill_dir")"
  dst="$CC_SKILLS/$name"

  rm -rf "$dst"
  mkdir -p "$dst"
  ln -s "$skill_dir/SKILL.md" "$dst/SKILL.md"

  # expression-framework: also wire up references so the agent can read the spec/docs
  if [[ "$name" == "expression-framework" ]]; then
    mkdir -p "$dst/references"
    ln -s "$REPO/SPECIFICATION.md" "$dst/references/SPECIFICATION.md"
    ln -s "$REPO/docs/DOCS.md"     "$dst/references/DOCS.md"
  fi

  echo "skill: $name"
done

# --------------------------------------------------------------------------
# 2. Set up marketplace structure at ~/.claude/plugins/marketplaces/expression-dev/
# --------------------------------------------------------------------------
rm -rf "$CC_MARKETPLACE"
mkdir -p "$CC_MARKETPLACE/plugins"

# Symlink our plugin directory as the "model" plugin inside the marketplace.
# Claude Code resolves <marketplace_install_location>/plugins/<plugin_name>/
ln -s "$REPO/plugins/claude" "$CC_MARKETPLACE/plugins/expression"
echo "marketplace: expression-dev → $CC_MARKETPLACE"

# --------------------------------------------------------------------------
# 3. Register marketplace in known_marketplaces.json
# --------------------------------------------------------------------------
python3 - <<PYEOF
import json, pathlib, sys

path = pathlib.Path("$CC_KNOWN")
try:
    data = json.loads(path.read_text())
except (FileNotFoundError, json.JSONDecodeError):
    data = {}

data["expression-dev"] = {
    "source": {"source": "local", "path": "$REPO/plugins/claude"},
    "installLocation": "$CC_MARKETPLACE",
    "lastUpdated": "$NOW",
}

path.write_text(json.dumps(data, indent=2) + "\n")
print("registered expression-dev in", path)
PYEOF

echo ""
echo "Done. In Claude Code run:"
echo "  /plugin install expression@expression-dev"
