#!/usr/bin/env bash
# Materialise plugins/{claude,codex}/{skills,reference}/ from the canonical
# sources so each plugin is self-contained. Default mode is `link` (relative
# symlinks, fast iteration in dev); pass `copy` for self-contained tarballs.
#
# Sources:
#   src/model/skills/        → plugins/<host>/skills/
#   SPECIFICATION.md         → plugins/<host>/reference/SPECIFICATION.md
#   docs/DOCS.md             → plugins/<host>/reference/DOCS.md
#
# Usage:
#   plugins/shared/skills-link.sh           # relative symlinks
#   plugins/shared/skills-link.sh copy      # plain copies

set -euo pipefail

mode="${1:-link}"
case "$mode" in
  link|copy) ;;
  *) echo "usage: $0 [link|copy]" >&2; exit 2 ;;
esac

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
src_skills="$repo_root/src/sweet/skills"
plugins=("claude" "codex")

# Paths are relative to the plugins/<host>/{skills,reference}/ directories,
# which are always three levels below the repo root.
# The source paths below are relative to repo root.
ref_files=("SPECIFICATION.md:SPECIFICATION.md" "docs/DOCS.md:DOCS.md")

if [[ ! -d "$src_skills" ]]; then
  echo "source skills dir not found: $src_skills" >&2
  exit 1
fi

for plugin in "${plugins[@]}"; do
  skills_dst="$repo_root/plugins/$plugin/skills"
  ref_dst="$repo_root/plugins/$plugin/reference"
  rm -rf "$skills_dst" "$ref_dst"
  mkdir -p "$skills_dst" "$ref_dst"

  for skill_dir in "$src_skills"/*/; do
    [[ -d "$skill_dir" ]] || continue
    skill_name="$(basename "$skill_dir")"
    if [[ "$mode" == "link" ]]; then
      # Relative path from plugins/<host>/skills/ back to repo root is ../../..
      ln -s "../../../src/sweet/skills/$skill_name" "$skills_dst/$skill_name"
    else
      cp -R "$skill_dir" "$skills_dst/$skill_name"
    fi
  done

  for entry in "${ref_files[@]}"; do
    src_rel="${entry%%:*}"
    dst_name="${entry##*:}"
    src_path="$repo_root/$src_rel"
    if [[ ! -f "$src_path" ]]; then
      echo "warning: reference source missing: $src_path" >&2
      continue
    fi
    if [[ "$mode" == "link" ]]; then
      # Relative path from plugins/<host>/reference/ back to repo root is ../../..
      ln -s "../../../$src_rel" "$ref_dst/$dst_name"
    else
      cp "$src_path" "$ref_dst/$dst_name"
    fi
  done

  echo "[$mode] $plugin: $(ls "$skills_dst" | wc -l | tr -d ' ') skills, $(ls "$ref_dst" | wc -l | tr -d ' ') references"
done
