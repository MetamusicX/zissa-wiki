---
name: query
description: Answer a research question from the wiki, navigating cluster → synthesis → related pages and citing the wiki pages used. Use for any question about the content of the research wiki.
argument-hint: <research question>
---

Answer the question below by following **Workflow 2: QUERY** in `CLAUDE.md`.

**Question:** $ARGUMENTS

- Navigate, don't scan: `index.md` cluster → the cluster's synthesis page if one exists → the `related:` fields of the pages you read. Stop reading once the question is answered.
- Answer from the wiki, citing the wiki pages you drew on as relative links. Open a raw file only to verify a specific quote.
- Say plainly where the wiki is silent or thin. Do not fill the gap from general knowledge without marking it as such.
- If the answer runs past a paragraph and is likely to be asked again, offer to save it as a synthesis page. To show how the pages you used connect, `python3 scripts/wiki.py graph --around <page>` prints a Mermaid diagram you can include.
- Log any gap you found in `log.md` as "gap identified".
