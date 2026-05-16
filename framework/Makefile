.PHONY: plugins plugins-copy plugins-clean dev-install dev-uninstall

# Materialise plugins/{claude,codex}/{skills,reference}/ from src/model/skills/.
# Default uses symlinks for fast in-place iteration. Use `make plugins-copy`
# when packaging a release tarball that needs to stand alone.
plugins:
	plugins/shared/skills-link.sh link

plugins-copy:
	plugins/shared/skills-link.sh copy

plugins-clean:
	rm -rf plugins/claude/skills plugins/claude/reference plugins/codex/skills plugins/codex/reference

# Install/uninstall the plugin locally into Claude Code for dev testing.
# After `make dev-install`, run `/plugin install sweet@sweet-dev` in Claude Code.
dev-install: plugins
	plugins/shared/install.sh

dev-uninstall:
	plugins/shared/uninstall.sh
