"""Tests for scripts/wiki.py. Run: python3 -m unittest discover tests"""
import io
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "scripts"))
import wiki  # noqa: E402

RAW = """The pattern of individuation is not a concept that can be reduced to a
single moment; it unfolds across the whole field of the preindividual.
"""

NOTE = """---
title: "Doe 2020 — Individuation"
type: source-note
author: "Jane Doe"
date: 2020
source-type: article
tags: [individuation]
created: 2026-01-01
updated: 2026-01-01
---

# Individuation

**Raw file:** [doe-2020.md](../../raw/articles/doe-2020.md)

See [Individuation](../concepts/individuation.md) and [Jane Doe](../authors/jane-doe.md).

## Direct Quotes
> "The pattern of individuation is not a concept that can be reduced to a single moment" (p. 1)
"""

CONCEPT = """---
title: "Individuation"
type: concept
tags: [individuation]
related: [jane-doe, doe-2020-individuation, preindividual]
created: 2026-01-01
updated: 2026-01-01
---

# Individuation

Discussed in [Doe 2020](../source-notes/doe-2020-individuation.md#summary). Close to the
[preindividual](preindividual.md). Example only: `[x](../concepts/nowhere.md)`.
"""

PRE = """---
title: "Preindividual"
type: concept
tags: [test]
related: [individuation, jane-doe, doe-2020-individuation]
created: 2026-01-01
updated: 2026-01-01
---

# Preindividual

The ground of [individuation](individuation.md).
"""

AUTHOR = """---
title: "Jane Doe"
type: author
tags: [test]
related: [individuation, preindividual, doe-2020-individuation]
created: 2026-01-01
updated: 2026-01-01
---

# Jane Doe

Wrote [Doe 2020](../source-notes/doe-2020-individuation.md).
"""

INDEX = """# Index
- [Individuation](wiki/concepts/individuation.md)
- [Preindividual](wiki/concepts/preindividual.md)
- [Jane Doe](wiki/authors/jane-doe.md)
- [Doe 2020](wiki/source-notes/doe-2020-individuation.md)
"""


class WikiFixture(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        shutil.copy(os.path.join(REPO, "conventions.toml"), self.root)
        self.write("raw/articles/doe-2020.md", RAW)
        self.write("wiki/source-notes/doe-2020-individuation.md", NOTE)
        self.write("wiki/concepts/individuation.md", CONCEPT)
        self.write("wiki/concepts/preindividual.md", PRE)
        self.write("wiki/authors/jane-doe.md", AUTHOR)
        self.write("index.md", INDEX)
        self.cfg = wiki._load_toml(os.path.join(self.root, "conventions.toml"))

    def tearDown(self):
        shutil.rmtree(self.root)

    def write(self, rel, text):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def read(self, rel):
        with open(os.path.join(self.root, rel), encoding="utf-8") as fh:
            return fh.read()

    def codes(self, findings, sev=None):
        return [f.code for f in findings if sev is None or f.sev == sev]

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = wiki.main(list(argv) + ["--root", self.root])
        return code, out.getvalue(), err.getvalue()


class TestLint(WikiFixture):
    def test_fixture_is_clean(self):
        findings, n = wiki.lint(self.root, self.cfg)
        self.assertEqual(n, 4)
        self.assertEqual(self.codes(findings, "error"), [])
        self.assertNotIn("orphan", self.codes(findings))

    def test_broken_link_is_an_error(self):
        self.write("wiki/concepts/preindividual.md", PRE + "\nSee [gone](gone.md).\n")
        findings, _ = wiki.lint(self.root, self.cfg)
        self.assertIn("link-broken", self.codes(findings, "error"))
        self.assertEqual(self.run_cli("lint")[0], 1)

    def test_thin_support_counts_distinct_notes(self):
        # individuation links the same source note twice: still only one source
        self.write("wiki/concepts/individuation.md", CONCEPT + "\nAgain: [Doe](../source-notes/doe-2020-individuation.md).\n")
        findings, _ = wiki.lint(self.root, self.cfg)
        thin = [f.relpath for f in findings if f.code == "thin-support"]
        self.assertIn(os.path.join("wiki", "concepts", "individuation.md"), thin)

    def test_links_in_code_are_ignored(self):
        findings, _ = wiki.lint(self.root, self.cfg)
        self.assertFalse(any("nowhere" in f.msg for f in findings))

    def test_orphan_and_type_folder(self):
        self.write("wiki/concepts/lonely.md", PRE.replace("Preindividual", "Lonely").replace("type: concept", "type: author"))
        findings, _ = wiki.lint(self.root, self.cfg)
        self.assertIn("type-folder", self.codes(findings, "error"))
        self.assertIn("orphan", self.codes(findings, "warn"))

    def test_empty_template_lints_clean(self):
        code, out, _ = self.run_cli_on_repo()
        self.assertEqual(code, 0, out)

    def test_first_page_in_fresh_template_lints_clean(self):
        # a fork's first ingest must not trip over the template's own placeholders
        fork = os.path.join(self.root, "fork")
        shutil.copytree(REPO, fork, ignore=shutil.ignore_patterns(".git", "tests"))
        with open(os.path.join(fork, "wiki/concepts/first.md"), "w", encoding="utf-8") as fh:
            fh.write(PRE.split("The ground")[0])
        findings, n = wiki.lint(fork, self.cfg)
        self.assertEqual(n, 1)
        self.assertEqual([f"{f.loc()} {f.msg}" for f in findings if f.sev == "error"], [])

    def run_cli_on_repo(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = wiki.main(["lint", "--root", REPO, "--min-severity", "error"])
        return code, out.getvalue(), ""


class TestQuotes(WikiFixture):
    def check(self):
        notes = [wiki.Page(self.root, "wiki/source-notes/doe-2020-individuation.md")]
        return wiki.check_quotes(self.root, notes)

    def test_verbatim_quote_passes(self):
        findings, tally = self.check()
        self.assertEqual(tally["exact"], 1, [f.msg for f in findings])
        self.assertEqual(self.codes(findings, "error"), [])

    def test_changed_word_is_caught(self):
        self.write("wiki/source-notes/doe-2020-individuation.md", NOTE.replace("reduced to", "limited to"))
        findings, _ = self.check()
        self.assertIn("quote-differs", self.codes(findings, "error"))

    def test_silent_omission_is_caught(self):
        self.write("wiki/source-notes/doe-2020-individuation.md", NOTE.replace("is not a concept", "is a concept"))
        findings, _ = self.check()
        self.assertTrue({"quote-omits", "quote-differs"} & set(self.codes(findings, "error")))

    def test_marked_ellipsis_passes(self):
        self.write("wiki/source-notes/doe-2020-individuation.md",
                   NOTE.replace("is not a concept that can be reduced", "is not a concept … reduced"))
        findings, _ = self.check()
        self.assertEqual(self.codes(findings, "error"), [])


class TestGraph(WikiFixture):
    def pages(self):
        return [wiki.Page(self.root, r) for r in sorted(wiki.iter_wiki_pages(self.root))]

    def test_whole_wiki(self):
        src, note = wiki.graph(self.root, self.pages())
        self.assertTrue(src.startswith("flowchart LR"))
        self.assertIn('("Individuation")', src)          # concept shape
        self.assertIn('(["Jane Doe"])', src)             # author shape
        self.assertIn("<-->", src)                        # mutual links
        self.assertIn("classDef concept", src)
        self.assertEqual(note, "")

    def test_around_and_limits(self):
        src, _ = wiki.graph(self.root, self.pages(), around="preindividual", depth=1)
        self.assertIn("stroke-width:3px", src)
        edges = lambda s: [l for l in s.splitlines() if "-->" in l or "-.-" in l]
        self.assertEqual(len(edges(src)), 3)             # a star: centre to each neighbour
        src, _ = wiki.graph(self.root, self.pages(), around="preindividual", all_edges=True)
        self.assertGreater(len(edges(src)), 3)
        src, note = wiki.graph(self.root, self.pages(), max_nodes=2)
        self.assertIn("best-connected", note)
        with self.assertRaises(ValueError):
            wiki.graph(self.root, self.pages(), around="nothing-here")

    def test_cli_fences_output(self):
        code, out, _ = self.run_cli("graph", "--around", "jane-doe")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("```mermaid\n"))


class TestMove(WikiFixture):
    def test_rename_rewrites_links_and_related(self):
        changes = wiki.move(self.root, "wiki/concepts/individuation.md", "wiki/concepts/individuation-simondon.md")
        self.assertTrue(changes)
        self.assertIn("(../concepts/individuation-simondon.md)", self.read("wiki/source-notes/doe-2020-individuation.md"))
        self.assertIn("(individuation-simondon.md)", self.read("wiki/concepts/preindividual.md"))
        self.assertIn("related: [individuation-simondon, jane-doe", self.read("wiki/concepts/preindividual.md"))
        self.assertIn("(wiki/concepts/individuation-simondon.md)", self.read("index.md"))
        findings, _ = wiki.lint(self.root, self.cfg)
        self.assertEqual(self.codes(findings, "error"), [])

    def test_move_to_other_folder_fixes_outgoing_links(self):
        wiki.move(self.root, "wiki/concepts/individuation.md", "wiki/themes/individuation.md")
        moved = self.read("wiki/themes/individuation.md")
        self.assertIn("(../source-notes/doe-2020-individuation.md#summary)", moved)
        self.assertIn("(../concepts/preindividual.md)", moved)
        self.assertIn("`[x](../concepts/nowhere.md)`", moved)   # inline code untouched
        findings, _ = wiki.lint(self.root, self.cfg)
        self.assertEqual([f.msg for f in findings if f.code == "link-broken"], [])

    def test_dry_run_writes_nothing(self):
        before = self.read("wiki/concepts/preindividual.md")
        wiki.move(self.root, "wiki/concepts/individuation.md", "wiki/concepts/x.md", dry_run=True)
        self.assertEqual(before, self.read("wiki/concepts/preindividual.md"))
        self.assertTrue(os.path.exists(os.path.join(self.root, "wiki/concepts/individuation.md")))

    def test_refuses_bad_targets(self):
        with self.assertRaises(ValueError):
            wiki.move(self.root, "wiki/concepts/individuation.md", "wiki/concepts/preindividual.md")
        with self.assertRaises(ValueError):
            wiki.move(self.root, "wiki/concepts/missing.md", "wiki/concepts/y.md")


class TestCheck(WikiFixture):
    def git(self, *a):
        import subprocess
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *a], cwd=self.root,
                       check=True, capture_output=True)

    def test_without_git_checks_everything(self):
        text, n = wiki.check(self.root, self.cfg)
        self.assertEqual(n, 0, text)
        self.write("wiki/source-notes/doe-2020-individuation.md", NOTE.replace("reduced to", "limited to"))
        text, n = wiki.check(self.root, self.cfg)
        self.assertEqual(n, 1)
        self.assertIn("quote-differs", text)

    def test_quotes_without_a_linked_source_fail_the_check(self):
        self.write("wiki/source-notes/doe-2020-individuation.md",
                   NOTE.replace("**Raw file:** [doe-2020.md](../../raw/articles/doe-2020.md)", "**Raw file:** raw/articles/doe-2020.md"))
        findings, _ = wiki.check_quotes(self.root, [wiki.Page(self.root, "wiki/source-notes/doe-2020-individuation.md")])
        self.assertIn("quote-no-source", self.codes(findings, "warn"))
        text, n = wiki.check(self.root, self.cfg)
        self.assertEqual(n, 1)
        self.assertIn("quote-no-source", text)

    def test_if_changed_skips_a_clean_tree(self):
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("commit", "-qm", "base")
        self.assertEqual(wiki.check(self.root, self.cfg, if_changed=True), ("", 0))
        self.write("wiki/concepts/preindividual.md", PRE + "\n[gone](gone.md)\n")
        text, n = wiki.check(self.root, self.cfg, if_changed=True)
        self.assertEqual(n, 1)
        self.assertIn("link-broken", text)
        self.git("add", "-A")
        self.assertEqual(wiki.check(self.root, self.cfg, staged=True)[1], 1)


class TestPromptApply(WikiFixture):
    def test_ingest_prompt_bundles_everything(self):
        self.write("AGENTS.md", "# Schema\nNever invent citations.\n")
        self.write("templates/concept.md", "---\ntype: concept\n---\n# [Concept Name]\n")
        text, note = wiki.build_prompt(self.root, self.cfg, "ingest", "raw/articles/doe-2020.md")
        for part in ("Never invent citations", "=== TEMPLATE: templates/concept.md ===", "## index.md",
                     "=== PAGE: wiki/concepts/individuation.md ===", "preindividual.", "=== END FILE ===",
                     "**Raw file:** [doe-2020.md](../../raw/articles/doe-2020.md)"):
            self.assertIn(part, text)
        self.assertEqual(note, "")

    def test_prompt_trims_to_budget_by_relevance(self):
        text, note = wiki.build_prompt(self.root, self.cfg, "query", "What is the preindividual?", budget=900)
        self.assertIn("=== PAGE: wiki/concepts/preindividual.md ===", text)
        self.assertNotIn("=== PAGE: wiki/source-notes/doe-2020-individuation.md ===", text)
        self.assertIn("- wiki/source-notes/doe-2020-individuation.md — Doe 2020", text)   # still listed
        self.assertIn("of 4 pages", note)

    def test_lint_prompt_carries_tool_findings(self):
        self.write("wiki/concepts/preindividual.md", PRE + "\n[gone](gone.md)\n")
        text, _ = wiki.build_prompt(self.root, self.cfg, "lint")
        self.assertIn("[link-broken]", text)

    def test_apply_writes_files_and_appends_log(self):
        self.write("log.md", "# Log\n")
        answer = """Here you go.
~~~~text
=== FILE: wiki/concepts/field.md ===
---
title: "Field"
type: concept
tags: [field]
created: 2026-01-01
updated: 2026-01-01
---
# Field
See [Preindividual](preindividual.md).
=== END FILE ===
=== APPEND: log.md ===
## [2026-01-01] ingest | Field
=== END FILE ===
~~~~
"""
        changes = wiki.apply_answer(self.root, answer)
        self.assertEqual(changes[0], "create wiki/concepts/field.md")
        self.assertIn("See [Preindividual](preindividual.md).", self.read("wiki/concepts/field.md"))
        self.assertTrue(self.read("log.md").endswith("## [2026-01-01] ingest | Field\n"))

    def test_apply_refuses_paths_outside_the_wiki(self):
        for path in ("raw/articles/doe-2020.md", "../escape.md", "wiki/../AGENTS.md", "scripts/wiki.py"):
            with self.assertRaises(ValueError, msg=path):
                wiki.apply_answer(self.root, f"=== FILE: {path} ===\nx\n=== END FILE ===\n")
        with self.assertRaises(ValueError):
            wiki.apply_answer(self.root, "no sections at all")

    def test_round_trip_catches_a_misquote(self):
        bad = NOTE.replace("reduced to", "limited to")
        wiki.apply_answer(self.root, f"=== FILE: wiki/source-notes/doe-2020-individuation.md ===\n{bad}=== END FILE ===\n")
        _, n = wiki.check(self.root, self.cfg)
        self.assertEqual(n, 1)


if __name__ == "__main__":
    unittest.main()
