---
name: ingest
description: Ingest a source from raw/ into the research wiki — source note, quote check, and every concept, author, debate and project page it touches. Use when the researcher says "ingest <file>".
argument-hint: <path in raw/>
---

Ingest `$ARGUMENTS` by following **Workflow 1: INGEST** in `AGENTS.md`, step by step. Stop after step 3 for the researcher's go-ahead. For large ingests, hand independent page updates to parallel subagents, one page each. Finish with `python3 scripts/wiki.py check`.
