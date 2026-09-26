<!--
This repository is a template others fork. Pull requests should improve the
template itself (schema, page templates, workflows, docs) — not add personal
wiki content. See CONTRIBUTING.md.
-->

## What does this change?

<!-- One or two sentences. What does the template do after this PR that it didn't before? -->

## Why?

<!-- The problem this solves, or a link to the issue it closes (e.g. "Closes #12"). -->

## Type of change

- [ ] Documentation (README, comments)
- [ ] Schema change (`AGENTS.md`, `templates/`)
- [ ] Tooling (`scripts/wiki.py`, hooks, agent-specific extras)
- [ ] Workflow change (ingest / query / lint)
- [ ] Folder conventions / structure
- [ ] Other:

## If this touches the schema or a workflow

- [ ] I ran at least one ingest in a scratch fork and confirmed the agent still produces well-formed pages (say which agent and model)
- [ ] I described what I tested below

<!-- What did you test, and what was the result? -->

## Checklist

- [ ] One focused concern per PR
- [ ] No personal research content added to the template
- [ ] Documentation updated if behaviour changed
- [ ] `python3 -m unittest discover tests` passes (if `scripts/wiki.py` changed)
