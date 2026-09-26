# Changelog

All notable changes to Zissa Wiki are recorded here.

## v1.1.0 — 2026-09-26

### Added
- **Slash commands for the three workflows**: `/ingest`, `/query`, `/lint`
  (`.claude/skills/`). They add working notes to `CLAUDE.md`'s workflows: stop
  for the researcher's go-ahead before writing, search rather than read to find
  affected pages, and parallel subagents for large ingests.
- **A Stop hook that enforces the finishing check** (`.claude/hooks/lint_gate.py`).
  When a task changed `wiki/` or `index.md`, Claude cannot finish until
  `wiki lint` is error-free and the quotes in changed source notes match their
  raw files. It blocks once, so an error Claude cannot fix never traps a session.
- **`wiki graph`** — draws the wiki, or the neighbourhood of one page, as a
  Mermaid diagram that renders on GitHub and in Obsidian.
- **`wiki move`** — renames a page and rewrites every inbound link, `related:`
  entry and (when it changes folder) its own outgoing links.
- **`templates/`** — one file per page type, now including `method` and `theme`,
  which never had a template.
- **Tests and CI.** `tests/test_wiki.py` covers all four commands; a GitHub
  Actions workflow runs the tests, `wiki lint` and `wiki quotes` on every push —
  on this template and, unchanged, on every fork's own wiki.
- **`AGENTS.md`**, so Codex, Gemini CLI, Cursor and other agents follow the same
  schema and checks.
- **A redesigned README** with native Mermaid diagrams of the architecture, the
  ingest sequence, the query cascade and a sample `wiki graph`. They follow
  GitHub's light or dark theme. The overview PNG and its `.mmd` source are retired.
- **`wiki quotes` — checks every direct quote against its source.** For each
  source note, the quotes are compared word for word with the raw file(s) the
  note links to (PDF via poppler's `pdftotext`; `.md`, `.txt`, `.html`, `.docx`,
  `.epub` natively). When a quote has drifted, the report shows where it parts
  from the source and what the source actually reads; unmarked omissions,
  dropped in-text citations, and wrong page numbers are flagged too. PDF page
  offsets are read from the page numbers the PDF prints. Exits nonzero on any
  misquote. See `scripts/README.md`.
- The INGEST workflow now runs the quote check on each new source note, and the
  source-note template spells out the quoting conventions it enforces.

### Changed
- **`CLAUDE.md` is leaner.** The page templates moved out to `templates/` and
  are read only when a page of that type is about to be written, so the file
  loaded into every session (and every subagent) is ~2.8 KB smaller despite
  gaining a Tools section. INGEST gained a closing lint step and guidance on
  finding affected pages by search.

### Fixed
- **A fork's first ingest no longer fails lint.** `index.md` shipped its
  example clusters and author groups as live links to pages that do not exist,
  which became 19 `link-broken` errors the moment the first page was written.
  The examples now sit in fenced blocks, which the linter ignores.
- `thin-support` now counts distinct source notes. It used to count links, so
  a concept citing the same note twice passed the two-source minimum.
- **`CLAUDE.md` is neutral again.** Since the v2 update (April 2026) the
  template's `CLAUDE.md` had shipped with the maintainer's personal Domain
  Context, project folders, and name in place of the placeholders. It now
  addresses "the researcher" and ships with the "Customize this section"
  placeholders, as the README describes. All v2 improvements (cluster
  navigation, `related:` fields, the annotations folder, the `wiki lint` note)
  are kept. If you forked between April and now, replace the Domain Context
  and any mention of "Paulo" with your own.
- `conventions.toml`: the optional relevance-marker header now matches the
  template's "Relevance to Your Research".

## v1.0.0 — 2026-07-18

### Renamed
- The project was renamed from **`llm-research-wiki`** to **`zissa-wiki`** — now
  part of the Zissa family, alongside
  [Zissa Agent Orchestra](https://github.com/MetamusicX/zissa-agent-orchestra).
  Old GitHub URLs and clone URLs redirect automatically, so existing links and
  clones keep working.

### Added
- **`scripts/wiki.py` — a deterministic `wiki lint` tool.** The mechanical
  health checks the schema always described (broken links, orphan pages, index
  drift, missing frontmatter, and optional epistemic markers) now run as a
  small, zero-dependency Python tool instead of by hand. Exits nonzero on any
  error, so it can gate a commit; an empty template lints clean.
- **`conventions.toml`** — the data-shaped rules the linter reads (type enum,
  required frontmatter, folder↔type map, size caps, staleness thresholds).
- **`scripts/README.md`** — usage, the full check list, and roadmap.

### Changed
- `README.md` and `CLAUDE.md` now document the `wiki lint` tooling in the LINT
  workflow.

The design follows the "the tool is the hands; the agent is the head" split,
borrowed from [engram](https://github.com/jeromeetienne/engram) and
[tome](https://github.com/chicken-noodle-chris/tome).
