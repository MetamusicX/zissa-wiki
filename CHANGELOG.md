# Changelog

All notable changes to Zissa Wiki are recorded here.

## Unreleased

### Fixed
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
