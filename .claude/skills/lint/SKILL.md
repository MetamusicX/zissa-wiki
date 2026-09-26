---
name: lint
description: Audit the research wiki — mechanical checks via scripts/wiki.py plus judgement checks for duplicates, contradictions, stale and weak pages. Reports a prioritised issue list; fixes nothing. Use when the researcher says "lint".
---

Run **Workflow 3: LINT** from `CLAUDE.md`.

1. Run `python3 scripts/wiki.py lint` and `python3 scripts/wiki.py quotes`. Their findings cover broken links, orphans, index drift, frontmatter, size, thin support and misquotes. Don't re-check any of these by hand.
2. Spend your own reading on what the tools cannot judge: duplicates (1), stale drift (2), contradictions (3), weak or generic pages (7). Pages with many inbound links or `thin-support` findings are the best places to start.
3. Report one prioritised list that merges both sources: errors first, then the judgement findings, then warnings, then info. For each item give the page, the problem, and the fix you propose.

Do not fix anything. The researcher decides.
