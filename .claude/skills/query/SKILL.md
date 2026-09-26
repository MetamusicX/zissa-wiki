---
name: query
description: Answer a research question from the wiki, navigating cluster → synthesis → related pages and citing the wiki pages used. Use for any question about the content of the research wiki.
argument-hint: <research question>
---

Answer this question by following **Workflow 2: QUERY** in `AGENTS.md`:

$ARGUMENTS

To show how the pages you used connect, `python3 scripts/wiki.py graph --around <page>` prints a Mermaid diagram you can include.
