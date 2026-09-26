# Contributing

Thanks for your interest in the LLM Research Wiki. This repository is a **template** — an unspecialised seed that people fork and make their own. That shapes what "contributing" means here.

## The two kinds of contribution

**1. Improving the template itself.**
Fixes and improvements to the seed everyone forks: the `AGENTS.md` schema, the page templates, the workflows (ingest / query / lint), the folder conventions, and the documentation in `README.md`. These are the changes that belong as pull requests against this repo.

**2. Your own wiki content.**
The concept pages, author pages, source notes, and syntheses you build by ingesting your own sources. These belong in *your fork*, not here. Please don't open pull requests adding your personal research content to the template — keep this repo unspecialised so it stays useful as a starting point for others.

## How to propose a change to the template

1. **Open an issue first** for anything beyond a typo — a bug, a schema improvement, a new page type, a workflow change. It's better to agree on the shape of a change before writing it.
2. **Fork and branch.** Make your change on a branch in your fork.
3. **Keep it focused.** One concern per pull request. A schema change and a README rewrite are two pull requests, not one.
4. **Run the tests if you touch `scripts/wiki.py`**: `python3 -m unittest discover tests`. Add a test for new behaviour.
5. **Test against a real ingest if you touch the schema.** If you change `AGENTS.md`, page templates, or workflows, run at least one ingest in a scratch fork and confirm Claude Code still produces well-formed pages. Note what you tested in the pull request.
6. **Match the existing voice.** The documentation is plain, concrete, and unhyped. Keep it that way.

## Conventions

These mirror the conventions the wiki itself uses (see `README.md` and `AGENTS.md`):

- **Filenames:** lowercase-kebab-case (`simondon-transduction.md`)
- **Markdown:** relative links between pages; YAML frontmatter on every wiki page
- **Schema is the law:** `AGENTS.md` governs how the agent behaves — changes there have wide effects, so explain your reasoning in the pull request

## Questions

If you're unsure whether something belongs in the template or in your fork, open an issue and ask. There are no silly questions about a pattern this new.
