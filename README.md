# Zissa Wiki

**A research wiki that writes itself as you read, and checks its own quotes.**

[![wiki checks](https://github.com/MetamusicX/zissa-wiki/actions/workflows/wiki.yml/badge.svg)](https://github.com/MetamusicX/zissa-wiki/actions/workflows/wiki.yml)
[![release](https://img.shields.io/github/v/release/MetamusicX/zissa-wiki)](https://github.com/MetamusicX/zissa-wiki/releases)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![python 3.9+](https://img.shields.io/badge/python-3.9%2B-informational)](scripts/README.md)
[![works with any LLM agent](https://img.shields.io/badge/works%20with-any%20LLM%20agent-8b5cf6)](#works-with-any-model)

Zissa Wiki is a personal knowledge base for academic research, kept in plain markdown and maintained by the AI agent of your choice: Claude Code, Codex, Gemini CLI, Cursor, an open-source agent running DeepSeek, Kimi, Qwen or Mistral, or a plain chat window in ChatGPT, Grok, Le Chat or DeepSeek. You drop a source into `raw/` and say *ingest*. The agent reads it, writes a source note, and updates every concept, author, debate and project page the source touches. Every direct quote is then checked, word for word, against the file it came from.

It implements [Andrej Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): rather than re-deriving knowledge from raw documents on every question (RAG), the model builds a **persistent, interlinked wiki** that compounds with each source. No database, no embeddings, no plugins.

> Part of the **Zissa** family of open, agent-driven tooling, a sibling to [Zissa Agent Orchestra](https://github.com/MetamusicX/zissa-agent-orchestra). *(Formerly `llm-research-wiki`; old links still redirect.)*

## Quickstart

```bash
git clone https://github.com/MetamusicX/zissa-wiki.git my-wiki
cd my-wiki
git config core.hooksPath .githooks     # optional: refuse commits that break links or misquote
```

Then open the folder in your agent (`claude`, `codex`, `gemini`, Cursor…), or use a chat app as described [below](#in-any-chat-app).

1. Fill in the **Domain Context** at the end of `AGENTS.md`: your research areas and key thinkers.
2. Write a 2–3 page research map in your own words, save it as `raw/notes/research-map.md`, and say **"ingest raw/notes/research-map.md"**. This seeds the wiki with *your* conceptual framework.
3. Add real sources one at a time (**"ingest raw/articles/&lt;file&gt;.pdf"**), and supervise the first 5–10 closely.
4. Ask research questions in plain language, and say **"lint"** every 10–15 ingests.

## Works with any model

The schema lives in [`AGENTS.md`](AGENTS.md), the cross-tool convention for agent instructions. Nothing in it depends on one vendor, and `scripts/wiki.py` never calls a model: it only reads and checks files. So the wiki is portable. Switch models whenever you like, and the pages, rules and checks stay the same.

| You use | Start with | It reads the schema from |
|---|---|---|
| **Claude Code** | `claude`, then `/ingest`, `/query`, `/lint` | `CLAUDE.md`, which imports `AGENTS.md` |
| **Codex CLI** (OpenAI) | `codex`, then "ingest raw/…" | `AGENTS.md` |
| **Gemini CLI** | `gemini`, then "ingest raw/…" | `GEMINI.md`, which imports `AGENTS.md` |
| **Cursor, GitHub Copilot agent** and other IDE agents | the agent chat, "ingest raw/…" | `AGENTS.md` |
| **Any model through an open-source agent**, e.g. [OpenCode](https://opencode.ai) with DeepSeek, Kimi, Qwen, Grok, Mistral or a local model | the agent, "ingest raw/…" | `AGENTS.md` |
| **A chat app**: ChatGPT, Grok, Le Chat, DeepSeek, Kimi, Claude.ai… | `wiki.py prompt`, paste, then `wiki.py apply` | the prompt itself |

Tested end to end with Claude Code, Codex CLI and, through the chat-app route, a Mistral model: each ingest produced well-formed pages that passed `wiki.py check`.

### In any chat app

A chat app can't open your files, so `wiki.py` carries them across. `prompt` bundles the schema, the page templates, `index.md`, the relevant wiki pages and the full source text into one message. `apply` writes the model's reply back into the wiki and checks it:

```bash
python3 scripts/wiki.py prompt ingest raw/articles/smith-2020.pdf | pbcopy   # 1. copy the prompt
#   2. paste it into the chat, discuss the takeaways, say "go",
#      then copy the one code block the model replies with
pbpaste | python3 scripts/wiki.py apply                                     # 3. write the pages, then check
```

If `apply` finds a broken link or a misquote, paste its report back into the chat, ask for corrected files, and apply again. `prompt query "…"` and `prompt lint` work the same way. When the wiki outgrows the model's context window, `prompt` includes the pages most relevant to the source or question: set the size with `--budget`, and force a page in with `--include`. On Linux use `xclip -selection clipboard` (and `xclip -o`); on Windows, `clip` and `Get-Clipboard`.

## How it works

```mermaid
%%{init: {"flowchart": {"wrappingWidth": 400}}}%%
flowchart LR
    you(["You"])
    agent["<b>Your agent</b><br/>Claude · Codex · Gemini · any chat app<br/>follows AGENTS.md"]
    tool["<b>scripts/wiki.py</b><br/>check · lint · quotes · graph · move"]

    subgraph RAW["raw/ · you add"]
        src[("Sources<br/>PDF · EPUB · notes<br/>transcripts · images")]
    end
    subgraph WIKI["wiki/ · the agent writes"]
        sn["Source notes"]
        pages["Concepts · Authors · Debates<br/>Methods · Themes · Projects"]
        syn["Syntheses"]
    end
    subgraph NAV["navigation"]
        idx["index.md<br/>concept clusters"]
        log["log.md<br/>every change"]
    end

    you -- "add a source" --> src
    you -- "ask" --> agent
    src -. "read, never modified" .-> agent
    agent --> sn & pages & syn
    agent --> idx & log
    agent -- "check before finishing" --> tool
    tool -. "errors to fix" .-> agent

    classDef ai fill:#fbe7df,stroke:#d97757,color:#1f2328
    classDef det fill:#e2e8f0,stroke:#475569,color:#1f2328
    class agent ai
    class tool det
```

| Layer | Contents | Who writes it |
|---|---|---|
| **`raw/`** | Immutable sources: articles, books, chapters, notes, transcripts, annotations, images | You |
| **`wiki/`** | Interlinked markdown pages: source notes, concepts, authors, debates, syntheses, projects | The agent |
| **schema** | `AGENTS.md` (the rules), `templates/` (one per page type), `index.md` (clusters), `log.md` (history) | You and the agent |

Raw sources are read once and never modified. The wiki is the layer that answers questions.

## The three workflows

The rules live in [`AGENTS.md`](AGENTS.md), which your agent loads at the start of every session. You start each workflow in plain language ("ingest …", a question, "lint"). In Claude Code they are also slash commands.

### Ingest: one source in, 10–15 pages updated

```mermaid
sequenceDiagram
    actor You
    participant C as Your agent
    participant W as wiki/ · index · log
    participant T as wiki.py

    You->>C: ingest raw/articles/smith-2020.pdf
    C->>C: read the source in full
    C-->>You: central argument, key claims, pages it will touch
    You->>C: go ahead
    C->>W: write the source note
    C->>T: quotes smith-2020-….md
    T-->>C: p. 45 — the source reads "tensions", not "energies"
    C->>W: fix the quote against the source
    par one subagent per page
        C->>W: concept, author, debate and project pages
    end
    C->>W: index.md and log.md
    C->>T: check (lint + quotes)
    T-->>C: 0 errors
    C-->>You: 12 pages created or updated
```

The agent discusses the source with you **before writing anything**. It reads each page template only when it is about to write that kind of page. If your tool supports subagents, a large ingest can hand independent page updates to them in parallel.

### Query: answers from the wiki, at constant cost

```mermaid
%%{init: {"flowchart": {"wrappingWidth": 400}}}%%
flowchart LR
    q(["Your question"]) --> idx["index.md<br/>find the cluster"]
    idx --> has{"Synthesis for<br/>this cluster?"}
    has -- yes --> syn["Read the synthesis"]
    has -- no --> core["Read the core pages"]
    syn --> rel["Follow <code>related:</code><br/>to neighbours"]
    core --> rel
    rel --> ans(["Answer, citing<br/>wiki pages"])
    ans -. "worth keeping?" .-> save["Save as a<br/>new synthesis"]
```

A flat index gets slow past ~50 pages. So queries run a three-step cascade:

1. **Concept clusters.** `index.md` groups concepts into 4–6 thematic clusters per domain, and a query picks its cluster first.
2. **Synthesis pages.** A cluster's pre-digested overview in `wiki/syntheses/`. One page read instead of six.
3. **`related:` fields.** Every concept and author page lists its 3–5 closest neighbours, so the agent can move between pages without re-scanning the index.

Each step narrows the reading set, which keeps query cost roughly constant at 100+ pages.

### Lint: the tool is the hands, the agent is the head

Mechanical checks run as deterministic Python; judgement checks are left to the agent. The result is one prioritised list, and nothing is fixed without your say.

| `wiki.py` checks, exactly and for free | The agent judges, by reading |
|---|---|
| broken links, orphan pages, index drift | duplicate pages |
| missing or invalid frontmatter | contradictions between pages |
| oversize pages, thin source support | stale pages that new sources should have touched |
| **misquotes** against the raw file, and wrong page numbers | weak or generic pages |

## Quotes you can trust

`AGENTS.md` tells the agent never to invent a citation. `wiki.py quotes` enforces it. For each source note it finds the linked raw file (PDF, EPUB, DOCX, HTML, markdown, text) and checks that every quote appears in it. Only the letters are compared, so PDF extraction noise, ligatures and line-end hyphens don't count as differences. When a quote has drifted, it tells you exactly where:

```text
✗ ERROR (1)
  wiki/source-notes/x-2020.md:14  [quote-differs] departs from the source at
  “…ndividual is a reservoir of energies”; the source reads “…dividual is a reservoir of tensions.”
```

It also catches omissions made without an ellipsis, dropped in-text citations, and page numbers that don't hold the passage. It reads the page numbers printed in the PDF, so book pages and PDF pages don't get confused.

## See your wiki

`wiki.py graph` draws the wiki, or the neighbourhood of one page, as a Mermaid diagram. That renders on GitHub, in Obsidian, and inside any wiki page:

```bash
python3 scripts/wiki.py graph --around individuation
```

```mermaid
flowchart LR
    n0(["Gilbert Simondon"])
    n1(["Gilles Deleuze"])
    n2("Difference in itself")
    n3("Individuation")
    n4("Metastability")
    n5("Preindividual")
    n6("Transduction")
    n7[["Deleuze 1968 — Difference and Repetition"]]
    n8[["Simondon — L'individuation"]]
    n9[/"Individuation from Simondon to Deleuze"/]
    n0 --> n3
    n2 --> n3
    n3 --> n5
    n3 <--> n6
    n3 <--> n7
    n3 <--> n8
    n9 --> n3
    n1 -.- n3
    n4 -.- n3
    classDef author fill:#fce7f3,stroke:#db2777,color:#1f2328
    class n0,n1 author
    classDef concept fill:#dbeafe,stroke:#3b82f6,color:#1f2328
    class n2,n3,n4,n5,n6 concept
    classDef source_note fill:#f1f5f9,stroke:#64748b,color:#1f2328
    class n7,n8 source_note
    classDef synthesis fill:#dcfce7,stroke:#16a34a,color:#1f2328
    class n9 synthesis
    style n3 stroke-width:3px
```

<sub>Shapes and colours by page type: concepts rounded blue, authors pill-shaped pink, source notes grey, syntheses green. Solid arrows are links; dotted lines are `related:` entries. `--depth 2` goes a hop further; `--all-edges` adds the links between neighbours. Illustrative demo pages.</sub>

The wiki is plain markdown with relative links, so the folder also opens as an [Obsidian](https://obsidian.md) vault as it is, graph view included.

## Tools

`scripts/wiki.py` is a single-file, zero-dependency Python tool (3.9+). Full reference: [`scripts/README.md`](scripts/README.md).

| Command | What it does |
|---|---|
| `python3 scripts/wiki.py check` | **The finishing check**: lint errors, plus quotes in every changed source note. |
| `python3 scripts/wiki.py lint` | Links, orphans, index drift, frontmatter, size, thin support. Exits nonzero on any error. |
| `python3 scripts/wiki.py quotes [NOTE]` | Every direct quote against its raw file, plus page numbers. |
| `python3 scripts/wiki.py graph [--around PAGE]` | The wiki's link graph as a Mermaid diagram. |
| `python3 scripts/wiki.py move OLD NEW` | Renames a page and rewrites every link and `related:` entry pointing to it. |
| `python3 scripts/wiki.py prompt ingest\|query\|lint` | Bundles a workflow into one message for any chat app. |
| `python3 scripts/wiki.py apply` | Writes a chat model's reply into the wiki, then runs `check`. |

The finishing check runs whichever agent you use:

- **Every agent** runs `wiki.py check` as the last step of each ingest; `AGENTS.md` requires it.
- **A git pre-commit hook** ([`.githooks/pre-commit`](.githooks/pre-commit)) refuses any commit whose wiki changes break a link or misquote a source, no matter which agent (or person) made them. Turn it on once per clone with `git config core.hooksPath .githooks`.
- **GitHub Actions** ([`.github/workflows/wiki.yml`](.github/workflows/wiki.yml)) checks every push to your fork.
- **`wiki.py apply`** checks everything a chat model sends back.
- **In Claude Code**, a Stop hook ([`.claude/hooks/lint_gate.py`](.claude/hooks/lint_gate.py)) runs the check before Claude finishes a task and sends it back to fix what fails.

## Folder structure

```
raw/                  your sources — immutable
  articles/  books/  chapters/  notes/  annotations/  transcripts/  images/  _staging/
wiki/                 written by the agent
  concepts/  authors/  debates/  themes/  methods/  syntheses/  source-notes/  projects/
templates/            one template per page type, read on demand
outputs/              finished deliverables: essays/  slides/  handouts/  tables/
archive/              superseded pages
conversations/        saved sessions
.githooks/            pre-commit: the finishing check on every commit
.claude/              Claude Code extras: /ingest /query /lint, the Stop hook
scripts/wiki.py       check · lint · quotes · graph · move · prompt · apply
conventions.toml      the machine-checkable rules the tool reads
AGENTS.md             the schema — "the law of the wiki", for every agent
CLAUDE.md, GEMINI.md  one-line imports of AGENTS.md for Claude Code and Gemini CLI
index.md · log.md     navigation and history
```

## Page types

| Type | Location | Purpose |
|---|---|---|
| **Source note** | `wiki/source-notes/` | One per ingested source: summary, key claims, verified quotes, connections |
| **Concept** | `wiki/concepts/` | Definition, key thinkers, related concepts, source support |
| **Author** | `wiki/authors/` | Bio, key works, concepts, relevance to your research |
| **Debate** | `wiki/debates/` | Framed positions, key texts, current state |
| **Synthesis** | `wiki/syntheses/` | Evolving argumentative overview of a cluster |
| **Project** | `wiki/projects/<name>/` | Your active research or writing projects |
| **Method** · **Theme** | `wiki/methods/` · `wiki/themes/` | Research methods; clusters that exceed one concept |

Each type has a template in [`templates/`](templates) with YAML frontmatter (`title`, `type`, `tags`, `related`, `created`, `updated`). The agent reads a template only when it is about to write that kind of page, so the always-loaded `AGENTS.md` stays lean.

## Scaling advice

- Start with your own research map as the first ingest. It seeds the wiki with *your* framework.
- Ingest one source at a time for the first 10–15, and supervise the quality.
- Don't ingest your whole library, only what matters to your active projects. `raw/_staging/` is a holding pen: review it weekly.
- Lint every 10–15 ingests.
- Create the first synthesis when a cluster has 4+ sources and keeps coming up in queries.
- At ~50 sources the wiki becomes a genuine research tool; at ~100 it's indispensable.

## Template vs. live wiki

This repository is the **template**, the unspecialised seed: placeholder Domain Context, empty `raw/` and `wiki/`. Fork it and make it yours. Please keep your own research content in your fork rather than opening PRs with it here; see [CONTRIBUTING](CONTRIBUTING.md).

My own working wiki is a separate version specialised to my research (Continental philosophy of science, new music studies, posthuman music). It uses the same schema, workflows and templates, plus a populated Domain Context and project folders.

Two adjacent systems in my setup share this DNA but serve other ends. The **MetamusicX wiki** builds atomic entities from research-meeting transcripts, and **Alluvium** turns daily journals into PARA-organised atomic notes. This template is the academic-research variant.

## Requirements

- An AI agent: any from the [table above](#works-with-any-model), or just a chat app
- Python 3.9+ for `scripts/wiki.py`: recommended for the checks, and required for the chat-app route (the wiki itself is pure markdown)
- [poppler](https://poppler.freedesktop.org/)'s `pdftotext` so `wiki quotes` can read PDFs (optional; `brew install poppler` / `apt install poppler-utils`)

## Credits

- **Pattern:** [Andrej Karpathy, "LLM Wiki"](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) (April 2026)
- **Tooling ideas:** [engram](https://github.com/jeromeetienne/engram) (the tool is the hands, the agent is the head) and [tome](https://github.com/chicken-noodle-chris/tome) (`conventions.toml`)
- **Adaptation and implementation:** [Paulo de Assis](https://github.com/MetamusicX), built with Claude Code (Anthropic)

See [CHANGELOG](CHANGELOG.md) for what's new. MIT licensed.
