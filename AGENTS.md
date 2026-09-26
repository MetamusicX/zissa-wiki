# AGENTS.md

This repository is a research wiki maintained by an AI agent. The schema that governs it is **[`CLAUDE.md`](CLAUDE.md)**. It is written for Claude Code, but nothing in it is Claude-specific: whichever agent you are, read it in full and follow it as your operating instructions.

Two things Claude Code does automatically that you must do yourself:

- **The workflows as commands.** `.claude/skills/ingest`, `query` and `lint` hold short working notes for the three workflows. Read the relevant one when the researcher asks you to ingest, query or lint.
- **The finishing check.** Before you end any task that changed `wiki/` or `index.md`, run `python3 scripts/wiki.py lint --min-severity error`, and `python3 scripts/wiki.py quotes <note>` for each source note you wrote or changed. Fix every error.
