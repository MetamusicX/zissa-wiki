# `wiki` — the deterministic tooling layer

> *The tool is the hands; the agent is the head.* — the [engram](https://github.com/jeromeetienne/engram) philosophy, adapted here.

The wiki's schema (`AGENTS.md`) already **specifies** every mechanical check —
broken links, orphans, index drift, missing frontmatter. But running those by
having the *agent* hand-scan every page is slow, token-expensive, and easy to
get wrong. This script moves the mechanical half out of the model into
deterministic Python. The agent keeps the irreducibly semantic work (reading,
synthesising, judging); the tool does the counting.

Idea and structure borrowed from two sibling projects in the same
[Karpathy LLM-wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
lineage: **[engram](https://github.com/jeromeetienne/engram)** (a validator-only
CLI with relative-link resolution) and
**[tome](https://github.com/chicken-noodle-chris/tome)** (a `conventions.toml`
that splits *data-shaped* rules out of the prose schema).

## Usage

```bash
python3 scripts/wiki.py lint                      # full report (error + warn + info)
python3 scripts/wiki.py lint --min-severity warn  # hide info
python3 scripts/wiki.py lint --min-severity error # errors only — the commit gate
python3 scripts/wiki.py lint --type concept       # restrict to one page type
python3 scripts/wiki.py lint --root /path/to/wiki # explicit root (else walks up for conventions.toml)
```

Exit code is **nonzero iff there is an ERROR-tier finding**, so it can gate a
commit or CI run: *"`wiki lint` must pass error-free as the last step of any
wiki-touching task."* No third-party dependencies (stdlib only; ships its own
minimal TOML reader for Python 3.9, and prefers `tomllib`/`tomli` when present).
**An empty wiki lints clean** — a freshly cloned template with no pages yet
reports `0 pages` and exits 0.

## What it checks

| Check | Tier | Meaning |
|---|---|---|
| `frontmatter-missing` / `frontmatter-field` | **error** | no YAML block, or a missing base required field (`title`/`type`/`tags`/`created`/`updated`) |
| `type-unknown` / `type-folder` | **error** | `type:` not in the enum, or disagreeing with the page's folder |
| `link-broken` (into `wiki/**.md`) | **error** | a real knowledge-graph link points at a missing page |
| `frontmatter-type-field` | warn | a per-type field is missing (e.g. a source-note without `author`/`date`/`source-type`) |
| `source-type` | warn | `source-type:` value not in the enum |
| `related-broken` | warn | a `related:` stem resolves to no page |
| `marker-relevance` / `marker-overview` | warn | *(optional)* an epistemic-marker header without its marker — only if enabled in `conventions.toml` |
| `orphan` | warn | a page no other wiki page links to (index/log/README don't count) |
| `oversize` (hard cap) | warn | page longer than the hard cap — consider splitting |
| `link-broken` (into `raw/`) | info | a provenance pointer to immutable source material (often gitignored / absent) |
| `index-drift` | info | a tracked-type page not linked from `index.md` |
| `thin-support` | info | a concept/debate citing fewer than the minimum source-notes |
| `related-missing` / `related-count` | info | concept/author `related:` absent or outside 3–5 |
| `oversize` (soft cap) / `stale` | info | length / staleness nudges |

Link resolution is **relative to each file's own directory**, so it correctly
handles both `index.md` (at root, links as `wiki/concepts/x.md`) and pages
inside `wiki/` (cross-linking as `../concepts/x.md`). Targets are URL-decoded
before the existence check; links inside fenced code blocks and `` `inline code` ``
are ignored (they're examples, not real links). The index and meta-file checks
run only once the wiki has at least one content page.

## `wiki quotes` — are the quotes really in the sources?

The schema says *"never invent citations"*; this is the check that enforces it.
For every source note it takes each blockquote that opens with a quote mark, finds
the raw file(s) the note links to (markdown links or `` `raw/...` `` paths), and
checks that the quoted words are actually there.

```bash
python3 scripts/wiki.py quotes                                   # every source note
python3 scripts/wiki.py quotes wiki/source-notes/smith-2020-x.md # just one (e.g. after an ingest)
python3 scripts/wiki.py quotes --min-severity error              # errors only
```

**What counts as a match.** Only the letters are compared — punctuation, spacing,
case, accents, ligatures, line-end hyphens, `*emphasis*` and footnote numbers are
ignored, because PDF extraction disturbs all of them. An ellipsis (`...`, `…`,
`[...]`) or a `[bracketed insertion]` in the quote splits it into fragments that are
checked one by one. Running heads, page numbers and footers that fall inside a
passage at a page break are recognised and skipped.

When a quote does not match, the checker lines it up against the source and says
where the two part and what the source actually reads:

| Check | Tier | Meaning |
|---|---|---|
| `quote-differs` | **error** | the wording differs — the message shows the quote and the source side by side |
| `quote-omits` | **error** | words are left out without an ellipsis (this can reverse the sense: "is [not] a concept") |
| `quote-missing` | **error** | nothing in the raw file resembles the quote (paraphrase? wrong file?) |
| `quote-citation` | warn | the quote silently drops an in-text citation such as "(Krohn 2010: 31–2)" |
| `quote-page` | warn | the cited page does not hold the passage, or the note cites PDF page numbers throughout |
| `quote-no-source` | warn (**error** in `wiki check`) | the note quotes but links no raw file, so nothing can be checked |
| `quote-unchecked` | info | raw file absent, no text layer (scanned PDF), translation, or too short |

**Page numbers.** A PDF's page 63 is often the book's printed page 45. The
checker reads the page numbers the PDF itself prints to learn the offset; when a
file has none it falls back on the offset most of the note's quotes agree on.
Citations marked `approx.` or `cf.` are not page-checked.

**Formats.** PDF needs `pdftotext` from poppler (`brew install poppler` on macOS,
`poppler-utils` on Linux); without it PDF quotes are reported as unchecked.
`.md`, `.txt`, `.html`, `.docx` and `.epub` are read with the standard library.
Scanned PDFs need OCR first.

**Translations.** A quote whose citation says `trans.`, `translated` or
`my translation` is skipped — it cannot match the original-language source.

## `wiki graph` — see the wiki as a diagram

Prints the link graph as a [Mermaid](https://mermaid.js.org) flowchart, which
renders on GitHub, in Obsidian, and inside any wiki page. Node shape and colour
follow the page type; solid arrows are links (`<-->` when mutual), dotted lines
are `related:` entries.

```bash
python3 scripts/wiki.py graph                                  # the whole wiki (best-connected 60 pages)
python3 scripts/wiki.py graph --around transduction            # one page and its neighbours
python3 scripts/wiki.py graph --around transduction --depth 2  # …and theirs
python3 scripts/wiki.py graph --around transduction --all-edges  # plus links among the neighbours
python3 scripts/wiki.py graph --type concept --type author     # only some page types
python3 scripts/wiki.py graph --raw > docs/graph.mmd           # without the ```mermaid fence
```

`--around` accepts a stem, a filename or a path. By default it draws only the
edge by which each page was reached, a tree out from the centre, because a full
neighbourhood quickly becomes unreadable. `--max-nodes` (default 60) keeps the
best-connected pages when the selection is larger.

## `wiki move` — rename without breaking links

Because pages use relative links, renaming one by hand breaks every link to it.
`move` renames the page and rewrites, in one pass, every inbound link across
`wiki/` and `index.md` (keeping `#anchors`), every `related:` entry naming its
stem, and the moved page's own outgoing links if it changes folder.

```bash
python3 scripts/wiki.py move wiki/concepts/transduction.md wiki/concepts/transduction-simondon.md --dry-run
python3 scripts/wiki.py move wiki/concepts/transduction.md wiki/concepts/transduction-simondon.md
```

It refuses to overwrite an existing page. `log.md` is history and is left as
written. Links inside code are examples and are left alone.

## `wiki check` — the finishing check

One command for the end of every wiki-changing task, whatever agent did the work:
lint errors across the wiki, plus the quote check on each source note changed since
the last commit (or on every note, outside git). Exits nonzero on any error.

```bash
python3 scripts/wiki.py check                         # before an agent says it is done
python3 scripts/wiki.py check --staged --if-changed   # what .githooks/pre-commit runs
```

`--if-changed` does nothing when no wiki file has changed, so errors that were
already there never hold up unrelated work. The same command backs the git
pre-commit hook (`git config core.hooksPath .githooks`), the Claude Code Stop hook,
and `wiki apply`.

## `wiki prompt` / `wiki apply` — the workflows in any chat app

For models you reach only through a chat window (ChatGPT, Grok, Le Chat, DeepSeek,
Kimi, Claude.ai…). `prompt` writes one self-contained message: the `AGENTS.md`
schema, the task, the answer format, the page templates (for ingest), `index.md`, a
catalogue of every page, the page contents, and the source text. PDF sources are
given with their printed page numbers, so the model can cite them correctly. `apply`
reads the model's reply and writes the files back.

```bash
python3 scripts/wiki.py prompt ingest raw/articles/smith-2020.pdf > prompt.md
python3 scripts/wiki.py prompt query "How does Simondon define transduction?"
python3 scripts/wiki.py prompt lint                    # carries the lint + quotes findings along
python3 scripts/wiki.py apply answer.md --dry-run      # or pipe the reply in on stdin
```

The reply format is one code block (so the chat's copy button yields the raw
text) of `=== FILE: path ===` … `=== END FILE ===` sections, plus `=== APPEND: log.md ===`
for the log. `apply` accepts only `wiki/**.md`, `index.md` and `log.md`, then runs
`wiki check` and prints any error to paste back into the chat.

If the wiki is larger than `--budget` characters (default 200,000, roughly 50k tokens),
`prompt` includes the pages whose title, stem or tags share the most words with the
source or question. `--include PAGE` forces a page in. The size of the prompt is
reported on stderr.

## Tests

```bash
python3 -m unittest discover tests
```

The suite builds a small wiki in a temporary folder and exercises every
command against it. It also checks that the template itself
lints clean, both empty and after its first page. CI runs it on Python 3.9 and 3.13.

## Configuration — `conventions.toml`

Data-shaped rules live in `../conventions.toml`: the type enum, required
frontmatter (base + per-type), the folder↔type map, the `source-type` enum,
`related` bounds, size caps, staleness thresholds, the index's tracked types,
and skip-lists. The linter is **schema-agnostic** — it does exactly what that
file says, so the same script serves this template and any specialised fork.
Edit the TOML to retune the checks; keep it in sync with `AGENTS.md`.

**Epistemic markers are opt-in.** This template ships without them. If you adopt
a provenance-tagging convention (e.g. `[P]` for your own research claims, `[W]`
for the wiki's cross-source synthesis), uncomment the `[markers]` block in
`conventions.toml` and the two marker checks activate.

## Roadmap

The CLI is built as a subcommand seam: `check`, `lint`, `quotes`, `graph`,
`move`, `prompt` and `apply` so far. Natural next tenants, in rough priority order:

- `wiki search <query>` — BM25 over frontmatter + body, an index-fallback for query.
- `wiki whois <name>` — resolve an author name/alias to its page.
- `wiki index` — regenerate / diff `index.md` from page frontmatter.
