---
name: ingest
description: Ingest a source from raw/ into the research wiki — source note, quote check, and every concept, author, debate and project page it touches. Use when the researcher says "ingest <file>".
argument-hint: <path in raw/>
---

Ingest `$ARGUMENTS` by following **Workflow 1: INGEST** in `CLAUDE.md`, step by step. It is the authority; this skill only adds how to run it well.

- **Stop after step 3.** Present the takeaways and the list of pages you plan to create or update, and wait for the researcher before writing anything.
- **Templates on demand.** Read `templates/<type>.md` just before creating a page of that type, not before.
- **Quotes are checked, not trusted.** After writing the source note, run `python3 scripts/wiki.py quotes <note>`. Fix every error against the raw file. A passage you cannot find is not a quote: paraphrase it without quote marks, or drop it.
- **Find impact with search, not reading.** Use grep over `wiki/` for each concept and author name to find pages that mention them. Read only those.
- **Parallelise large ingests.** When more than a handful of existing pages need a Source Support line or a new claim, give each page to its own subagent with the source-note path and exactly what to add. One page per subagent; `index.md` and `log.md` stay with you.
- **Finish clean.** Run `python3 scripts/wiki.py lint --min-severity error` and fix every error before you report. End with the list of pages created and updated, as written to `log.md`.
