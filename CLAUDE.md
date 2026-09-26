# CLAUDE.md

The schema for this wiki is in `AGENTS.md`, shared by every agent that works here. Claude Code loads it through the import below. Edit `AGENTS.md`, not this file.

@AGENTS.md

## Claude Code extras

- `/ingest`, `/query` and `/lint` (`.claude/skills/`) start the three workflows.
- A Stop hook (`.claude/settings.json`) runs `python3 scripts/wiki.py check` before you finish any task that changed `wiki/` or `index.md`. If it sends you back, fix what it reports.
