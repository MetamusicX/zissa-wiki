#!/usr/bin/env python3
"""wiki — the deterministic 'hands' layer for an LLM Research Wiki.

Philosophy (borrowed from engram): the tool is the hands, the agent is the head.
Everything mechanically checkable — link integrity, orphans, index drift, missing
frontmatter, and (optionally) epistemic-register markers — lives here as
deterministic code, so the agent stops hand-scanning every page for it.

The prose schema stays in CLAUDE.md; the data-shaped rules live in conventions.toml.
This linter is schema-agnostic: behaviour is driven entirely by conventions.toml,
so the same script serves both this template and a fully specialised wiki.

Usage:
    python3 scripts/wiki.py lint [--root PATH] [--min-severity error|warn|info] [--type TYPE]
    python3 scripts/wiki.py quotes [NOTE ...] [--root PATH] [--min-severity error|warn|info]
    python3 scripts/wiki.py graph [--around PAGE] [--depth N] [--type TYPE] [--all-edges] [--raw]
    python3 scripts/wiki.py move OLD NEW [--dry-run]

Exit code is nonzero when any ERROR-tier finding is present, so this can gate a
commit or CI ("lint must pass error-free as the last step of any wiki-touching task").
An empty wiki (no pages under wiki/ yet) always lints clean.

`quotes` checks that every direct quote in a source note appears word for word in
the raw file(s) the note links to, and that its page citation fits. It compares
letters only, so punctuation, spacing and PDF extraction noise never count. PDFs need
`pdftotext` (poppler); .md/.txt/.html/.docx/.epub are read with the stdlib.

`graph` prints the link graph as a Mermaid diagram; `move` renames a page and rewrites
every link and `related:` entry that points to it.

Roadmap (not yet implemented — this is the seam to grow the CLI along):
    wiki search <query>     BM25 over frontmatter + body
    wiki whois <name>       resolve an author name/alias to its page
"""
from __future__ import annotations

import argparse
import bisect
import difflib
import html
import os
import re
import shutil
import subprocess
import sys
import unicodedata
import zipfile
from collections import Counter
from datetime import date
from urllib.parse import unquote

# ─────────────────────────────────────────────────────────────────────────────
# Config loading (tomllib / tomli if present, else a minimal parser for our file)
# ─────────────────────────────────────────────────────────────────────────────

def _load_toml(path):
    try:
        import tomllib  # Python 3.11+
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except ModuleNotFoundError:
        pass
    try:
        import tomli  # optional backport
        with open(path, "rb") as fh:
            return tomli.load(fh)
    except ModuleNotFoundError:
        pass
    return _mini_toml(path)


def _mini_toml(path):
    """Tiny TOML reader for conventions.toml only: [tables], scalars, 1-line arrays."""
    data, cur = {}, None
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                cur = data.setdefault(line[1:-1].strip(), {})
                continue
            if "=" not in line or cur is None:
                continue
            key, val = line.split("=", 1)
            cur[key.strip()] = _mini_val(_strip_toml_comment(val).strip())
    return data


def _strip_toml_comment(s):
    """Drop a trailing ` # comment`, but not a `#` inside a quoted string."""
    out, q = [], None
    for ch in s:
        if q:
            out.append(ch)
            if ch == q:
                q = None
        elif ch in "\"'":
            q = ch
            out.append(ch)
        elif ch == "#":
            break
        else:
            out.append(ch)
    return "".join(out)


def _mini_val(v):
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        if not inner:
            return []
        return [_mini_val(x.strip()) for x in inner.split(",")]
    if len(v) >= 2 and v[0] in "\"'" and v[-1] == v[0]:
        return v[1:-1]
    if v in ("true", "false"):
        return v == "true"
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    return v


# ─────────────────────────────────────────────────────────────────────────────
# Findings
# ─────────────────────────────────────────────────────────────────────────────

SEV = {"error": 3, "warn": 2, "info": 1}


class Finding:
    __slots__ = ("sev", "code", "relpath", "line", "msg")

    def __init__(self, sev, code, relpath, msg, line=0):
        self.sev, self.code, self.relpath, self.line, self.msg = sev, code, relpath, line, msg

    def loc(self):
        return f"{self.relpath}:{self.line}" if self.line else self.relpath


# ─────────────────────────────────────────────────────────────────────────────
# Frontmatter + page model
# ─────────────────────────────────────────────────────────────────────────────

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")          # [text](target)
HEADER_RE = re.compile(r"^#{1,6}\s")
INLINE_CODE_RE = re.compile(r"`[^`]*`")                 # `inline code` — example links here don't count


def _links_in(line):
    """Yield link targets on a line, ignoring any inside inline-code spans."""
    scanned = INLINE_CODE_RE.sub(lambda m: " " * len(m.group()), line)
    return (m.group(1) for m in LINK_RE.finditer(scanned))


def parse_frontmatter(lines):
    """Return (fields dict, ok). Minimal YAML subset: scalars + inline/block lists."""
    if not lines or lines[0].rstrip() != "---":
        return {}, False
    fields, key = {}, None
    for i in range(1, len(lines)):
        line = lines[i].rstrip("\n")
        if line.rstrip() == "---":
            return fields, True
        m = re.match(r"^(\S[^:]*?):\s*(.*)$", line)
        if m:
            key, rawval = m.group(1).strip(), m.group(2).strip()
            fields[key] = _yaml_val(rawval)
        elif key and re.match(r"^\s*-\s+", line):          # block list continuation
            item = _strip_quotes(re.sub(r"^\s*-\s+", "", line).strip())
            prev = fields.get(key)
            fields[key] = (prev if isinstance(prev, list) else []) + [item]
    return fields, False   # no closing ---


def _yaml_val(v):
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return [_strip_quotes(x.strip()) for x in inner.split(",") if x.strip()] if inner else []
    return _strip_quotes(v) if v else ""


def _strip_quotes(s):
    return s[1:-1] if len(s) >= 2 and s[0] in "\"'" and s[-1] == s[0] else s


class Page:
    def __init__(self, root, relpath):
        self.relpath = relpath
        self.abspath = os.path.join(root, relpath)
        with open(self.abspath, encoding="utf-8") as fh:
            self.lines = fh.readlines()
        self.fm, self.fm_ok = parse_frontmatter(self.lines)
        self.type = self.fm.get("type", "")
        self.stem = os.path.splitext(os.path.basename(relpath))[0]
        # first path segment under wiki/  (e.g. "concepts", "projects")
        parts = relpath.split(os.sep)
        self.segment = parts[1] if len(parts) > 2 and parts[0] == "wiki" else ""
        self.is_project_index = relpath.startswith(os.path.join("wiki", "projects")) and self.stem == "index"


# ─────────────────────────────────────────────────────────────────────────────
# Discovery
# ─────────────────────────────────────────────────────────────────────────────

def find_root(start):
    d = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(d, "conventions.toml")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def iter_wiki_pages(root):
    wiki_dir = os.path.join(root, "wiki")
    for dirpath, _dirs, files in os.walk(wiki_dir):
        for name in files:
            if name.endswith(".md"):
                yield os.path.relpath(os.path.join(dirpath, name), root)


def resolve_link(root, from_relpath, target):
    """Return repo-relative path a link resolves to, or None if external/anchor."""
    t = target.strip()
    if t.startswith(("http://", "https://", "mailto:", "#")):
        return None
    t = t.split("#", 1)[0].split("?", 1)[0].strip()
    if not t:
        return None
    base = os.path.dirname(os.path.join(root, from_relpath))
    abs_target = os.path.normpath(os.path.join(base, unquote(t)))
    return os.path.relpath(abs_target, root)


def link_severity(resolved):
    """A broken link's severity depends on where it points.

    Into wiki/ (.md) → ERROR: real knowledge-graph breakage.
    Into raw/         → INFO: a provenance pointer to immutable source material,
                        which is often gitignored/absent and not part of the graph.
    Anything else     → WARN: an asset/output link worth a look.
    """
    if resolved.startswith("wiki" + os.sep):
        return "error" if resolved.endswith(".md") else "warn"
    if resolved.startswith("raw" + os.sep):
        return "info"
    return "warn"


# ─────────────────────────────────────────────────────────────────────────────
# Lint
# ─────────────────────────────────────────────────────────────────────────────

def lint(root, cfg, type_filter=None):
    findings = []
    add = lambda *a, **k: findings.append(Finding(*a, **k))

    fm_required = cfg.get("frontmatter", {}).get("required", [])
    fm_by_type = cfg.get("frontmatter_by_type", {})
    type_enum = set(cfg.get("types", {}).get("enum", []))
    folder_map = cfg.get("folders", {})
    src_types = set(cfg.get("source_type", {}).get("enum", []))
    rel_cfg = cfg.get("related", {})
    rel_types, rel_min, rel_max = set(rel_cfg.get("types", [])), rel_cfg.get("min", 3), rel_cfg.get("max", 5)
    mk = cfg.get("markers", {})
    rel_header = mk.get("relevance_header")            # optional: only checked if declared
    rel_marker = mk.get("relevance_marker", "")
    overview_marker = mk.get("overview_marker")        # optional: only checked if declared
    soft, hard = cfg.get("size", {}).get("soft_cap", 450), cfg.get("size", {}).get("hard_cap", 900)
    stale = cfg.get("staleness", {})
    idx_cfg = cfg.get("index", {})
    tracked = set(idx_cfg.get("tracked_types", []))
    thin = cfg.get("thin_support", {})
    thin_types, thin_min = set(thin.get("types", [])), thin.get("min_source_links", 2)
    skip = cfg.get("skip", {})
    noninbound = set(skip.get("noninbound_files", []))
    no_linkcheck = set(skip.get("no_linkcheck_files", []))

    pages = [Page(root, rp) for rp in iter_wiki_pages(root)]
    if type_filter:
        pages = [p for p in pages if p.type == type_filter]
    by_relpath = {p.relpath: p for p in pages}
    wiki_paths = set(by_relpath)
    stem_to_paths = {}
    for p in pages:
        stem_to_paths.setdefault(p.stem, []).append(p.relpath)

    inbound = {p.relpath: set() for p in pages}          # target -> set of source relpaths

    # ── per-page checks ──────────────────────────────────────────────────────
    for p in pages:
        # frontmatter present & required fields
        if not p.fm_ok:
            add("error", "frontmatter-missing", p.relpath, "no valid YAML frontmatter block")
            continue
        for f in fm_required:
            if not p.fm.get(f):
                add("error", "frontmatter-field", p.relpath, f"missing required field `{f}`")
        # type enum + folder agreement
        if p.type and p.type not in type_enum:
            add("error", "type-unknown", p.relpath, f"type `{p.type}` not in the enum")
        expected = folder_map.get(p.segment)
        if expected and p.type and p.type != expected and not p.is_project_index:
            add("error", "type-folder", p.relpath, f"type `{p.type}` but folder implies `{expected}`")
        # per-type extra fields
        for f in fm_by_type.get(p.type, []):
            if not p.fm.get(f):
                add("warn", "frontmatter-type-field", p.relpath, f"{p.type} missing `{f}`")
        # source-type enum
        st = p.fm.get("source-type")
        if p.type == "source-note" and st and st not in src_types:
            add("warn", "source-type", p.relpath, f"source-type `{st}` not in the enum")
        # related field (concept/author)
        if p.type in rel_types:
            rel = p.fm.get("related")
            rel = rel if isinstance(rel, list) else ([rel] if rel else [])
            if not rel:
                add("info", "related-missing", p.relpath, "no `related:` field")
            elif not (rel_min <= len(rel) <= rel_max):
                add("info", "related-count", p.relpath, f"related has {len(rel)} entries (want {rel_min}-{rel_max})")
            for stem in rel:
                if stem and stem not in stem_to_paths:
                    add("warn", "related-broken", p.relpath, f"related `{stem}` resolves to no page")
                else:
                    for tgt in stem_to_paths.get(stem, []):
                        if tgt != p.relpath:
                            inbound[tgt].add(p.relpath)

        # links: broken-link check + inbound graph + thin-support tally
        src_notes = set()                          # distinct source notes cited
        in_fence = False
        for i, line in enumerate(p.lines, 1):
            stripped = line.lstrip()
            if stripped.startswith("```") or stripped.startswith("~~~"):
                in_fence = not in_fence
                continue
            if in_fence:                              # example links in code blocks don't count
                continue
            for target in _links_in(line):
                resolved = resolve_link(root, p.relpath, target)
                if resolved is None:
                    continue
                exists = os.path.exists(os.path.join(root, resolved))
                if not exists:
                    add(link_severity(resolved), "link-broken", p.relpath, f"link → `{resolved}` (missing)", line=i)
                elif resolved in wiki_paths and resolved != p.relpath:
                    inbound[resolved].add(p.relpath)
                if resolved.startswith(os.path.join("wiki", "source-notes")) and exists:
                    src_notes.add(resolved)

            # epistemic-marker checks (header lines only) — only if the schema declares markers
            if HEADER_RE.match(line):
                if rel_header and rel_header in line and rel_marker not in line:
                    add("warn", "marker-relevance", p.relpath,
                        f"'{rel_header}' header missing {rel_marker}", line=i)
                if overview_marker and p.type == "synthesis" \
                        and re.match(r"^#{1,6}\s+Overview\b", line) and overview_marker not in line:
                    add("warn", "marker-overview", p.relpath,
                        f"synthesis Overview header missing {overview_marker}", line=i)

        # thin source support
        if p.type in thin_types and len(src_notes) < thin_min:
            add("info", "thin-support", p.relpath,
                f"{p.type} cites {len(src_notes)} source-note(s) (want ≥{thin_min})")

        # size caps
        n = len(p.lines)
        if n > hard:
            add("warn", "oversize", p.relpath, f"{n} lines (> hard cap {hard}) — consider splitting")
        elif n > soft:
            add("info", "oversize", p.relpath, f"{n} lines (> soft cap {soft})")

    # ── orphans + staleness (need the completed inbound graph) ────────────────
    today = date.today()
    for p in pages:
        if p.is_project_index:
            continue
        deg = len(inbound[p.relpath])
        if deg == 0:
            add("warn", "orphan", p.relpath, "no inbound links from any wiki page")
        # staleness: well-linked AND old, together
        if stale and deg >= stale.get("min_inbound_links", 5):
            upd = str(p.fm.get("updated", ""))
            m = re.match(r"(\d{4})-(\d{2})-(\d{2})", upd)
            if m:
                age = (today - date(int(m[1]), int(m[2]), int(m[3]))).days
                if age > stale.get("max_days_since_update", 180):
                    add("info", "stale", p.relpath, f"{age}d since update, {deg} inbound links")

    # ── index + meta-file checks (only meaningful once the wiki has content) ──
    if pages:
        # index drift (pages the index is meant to enumerate but doesn't)
        idx_file = idx_cfg.get("file", "index.md")
        idx_path = os.path.join(root, idx_file)
        if os.path.exists(idx_path):
            with open(idx_path, encoding="utf-8") as fh:
                idx_text = fh.read()
            indexed = set()
            for m in LINK_RE.finditer(idx_text):
                r = resolve_link(root, idx_file, m.group(1))
                if r:
                    indexed.add(r)
            for p in pages:
                if p.type in tracked and p.relpath not in indexed and not p.is_project_index:
                    add("info", "index-drift", p.relpath, "not linked from the index")

        # broken links inside root meta files (index.md, README.md, CLAUDE.md) — not log.md
        for meta in noninbound:
            if meta in no_linkcheck:
                continue
            mp = os.path.join(root, meta)
            if not os.path.exists(mp):
                continue
            in_fence = False
            with open(mp, encoding="utf-8") as fh:
                for i, line in enumerate(fh, 1):
                    stripped = line.lstrip()
                    if stripped.startswith("```") or stripped.startswith("~~~"):
                        in_fence = not in_fence
                        continue
                    if in_fence:                      # skip template examples in code blocks
                        continue
                    for target in _links_in(line):
                        r = resolve_link(root, meta, target)
                        if r and not os.path.exists(os.path.join(root, r)):
                            add(link_severity(r), "link-broken", meta, f"link → `{r}` (missing)", line=i)

    return findings, len(pages)


# ─────────────────────────────────────────────────────────────────────────────
# Quotes — verify direct quotes in source notes against their raw files
# ─────────────────────────────────────────────────────────────────────────────

DOUBLE_OPEN, DOUBLE_CLOSE = '"“„«', '"”“»'
SINGLE_OPEN, SINGLE_CLOSE = "'‘", "'’"
# after the closing quote mark: optional punctuation, then a citation or the end
QUOTE_END_RE = re.compile(r"^\s*[,.;:!?]?\s*(\(|\[|—|–|-|$)")
GAP_RE = re.compile(r"\s*(?:\.\s?\.\s?\.|…|\[[^\]]*\])\s*")   # ellipses and [editorial insertions]
PAGE_RE = re.compile(r"\bpp?\.\s*(\d+)(?:\s*[–-]\s*(\d+))?")
RAW_CODE_RE = re.compile(r"`(raw/[^`]+)`")
MIN_FRAGMENT = 12          # letters; shorter fragments are too common to prove anything
ANCHOR = 30                # letters per probe when lining a quote up against its source
PAGE_BREAK_NOISE = 300     # letters of running head / footnote tolerated at a page break
MIN_FURNITURE = 10         # letters; a recurring line shorter than this could be any phrase
TYPO = 3                   # letters; a gap this small reads as changed wording, not an omission
CITATION_RE = re.compile(r"(?:[\s,;:.'\"’”]*\([^()]*\d[^()]*\)\d*)+[\s,;:.'\"’”]*")   # ’ (Krohn 2010: 31–2)


def _loose(text):
    """Letters only, casefolded, accents dropped. Compares the words of a quote while
    ignoring what PDF extraction and editing routinely disturb: punctuation, spacing,
    line-end hyphens, ligatures, accents, case, emphasis markup, and footnote numbers."""
    return "".join(ch for ch in unicodedata.normalize("NFKD", text).casefold() if ch.isalpha())


def _at_letter(text, n):
    """Index in `text` of the character that holds letter n of _loose(text)."""
    seen = 0
    for i, ch in enumerate(text):
        k = sum(c.isalpha() for c in unicodedata.normalize("NFKD", ch).casefold())
        if seen + k > n:
            return i
        seen += k
    return len(text)


class _Unreadable(Exception):
    pass


class RawDoc:
    """A raw file's text, split into pages when the format has them (PDF). Matching runs
    on the letters-only form; `text` joins the pages so a quote can cross a page break."""

    def __init__(self, pages, paged):
        self.paged, self.raw = paged, pages
        self.pages = [_loose(t) for t in pages]
        self.text = "".join(self.pages)
        self.starts, n = [], 0
        for pg in self.pages:
            self.starts.append(n)
            n += len(pg)

    def page_at(self, i):
        """1-based page holding letter i of `text`."""
        return bisect.bisect_right(self.starts, i)

    def pages_between(self, a, b):
        return set(range(self.page_at(a), self.page_at(max(a, b - 1)) + 1))

    def printed_offset(self):
        """Printed page minus PDF page, read from the page numbers the PDF prints: a line
        holding just a number among a page's first or last three lines. None when there
        is no consistent numbering (unnumbered files, two-page spreads)."""
        if not self.paged:
            return None
        votes = Counter()
        for n, raw in enumerate(self.raw, 1):
            lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
            for ln in set(lines[:3] + lines[-3:]):
                if re.fullmatch(r"\d{1,4}", ln):
                    votes[int(ln) - n] += 1
        if votes:
            offset, k = votes.most_common(1)[0]
            if k >= max(3, len(self.raw) // 4):
                return offset
        return None

    def raw_between(self, a, b):
        """The original text a gap spans: from after letter a-1 up to letter b of `text`.
        None when the gap crosses a page break."""
        pg = self.page_at(a)
        if pg != self.page_at(b):
            return None
        raw, base = self.raw[pg - 1], self.starts[pg - 1]
        start = _at_letter(raw, a - 1 - base) + 1 if a > base else 0
        return raw[start:_at_letter(raw, b - base)]

    def context(self, i, before=30, after=45):
        """The original text around letter i of `text`."""
        pg = self.page_at(i)
        raw = self.raw[pg - 1]
        c = _at_letter(raw, i - self.starts[pg - 1])
        return _snippet(raw, c, before, after), pg


def _snippet(text, c, before, after):
    if not after and 0 < c < len(text) and text[c - 1].isalpha() and text[c].isalpha():
        c = text.rfind(" ", 0, c) + 1                    # ending here: don't cut a word in half
    s = re.sub(r"\s+", " ", text[max(0, c - before):c]).lstrip()
    t = re.sub(r"\s+", " ", text[c:c + after]).rstrip()
    return ("…" if c > before else "") + s + t + ("…" if c + after < len(text) else "")


def _strip_markup(text):
    text = re.sub(r"(?i)</(p|div|h\d|li|tr)>|<br\s*/?>|</w:p>|<w:tab/>", "\n", text)
    return html.unescape(re.sub(r"<[^>]+>", "", text))


def read_raw(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        exe = shutil.which("pdftotext")
        if not exe:
            raise _Unreadable("pdftotext not installed (macOS: brew install poppler; Linux: poppler-utils)")
        out = subprocess.run([exe, "-enc", "UTF-8", path, "-"], capture_output=True)
        if out.returncode != 0:
            raise _Unreadable("pdftotext could not read it")
        pages, paged = out.stdout.decode("utf-8", "replace").split("\f"), True
        if pages and not pages[-1].strip():
            pages.pop()
    elif ext in (".md", ".markdown", ".txt"):
        with open(path, encoding="utf-8", errors="replace") as fh:
            pages, paged = [fh.read()], False
    elif ext in (".html", ".htm", ".xhtml"):
        with open(path, encoding="utf-8", errors="replace") as fh:
            pages, paged = [_strip_markup(fh.read())], False
    elif ext in (".docx", ".epub"):
        try:
            with zipfile.ZipFile(path) as z:
                names = ["word/document.xml"] if ext == ".docx" else sorted(
                    n for n in z.namelist() if n.lower().endswith((".xhtml", ".html", ".htm")))
                pages = ["\n".join(_strip_markup(z.read(n).decode("utf-8", "replace")) for n in names)]
                paged = False
        except (zipfile.BadZipFile, KeyError):
            raise _Unreadable(f"not a readable {ext} file")
    else:
        raise _Unreadable(f"unsupported format `{ext}`")
    doc = RawDoc(pages, paged)
    if not doc.text:
        raise _Unreadable("no text layer (scanned without OCR?)")
    return doc


def raw_refs(root, page):
    """Raw files a source note points to: markdown links and `raw/...` code spans."""
    refs = []
    for line in page.lines:
        for target in LINK_RE.findall(line):
            r = resolve_link(root, page.relpath, target)
            if r and r.startswith("raw" + os.sep) and r not in refs:
                refs.append(r)
        for target in RAW_CODE_RE.findall(line):
            r = os.path.normpath(target.strip())
            if r not in refs:
                refs.append(r)
    return refs


def quotes_in(page):
    """Yield (line, quote text, citation tail) for each blockquote that opens with a quote mark."""
    para, start, in_fence = [], 0, False
    for i, line in enumerate(page.lines + ["\n"], 1):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
        if not in_fence and stripped.startswith(">") and stripped.lstrip("> ").strip():
            if not para:
                start = i
            para.append(stripped.lstrip(">").strip())
            continue
        if para:
            q = _split_quote(" ".join(para))
            if q:
                yield (start,) + q
            para = []


def _split_quote(s):
    if not s or s[0] not in DOUBLE_OPEN + SINGLE_OPEN:
        return None
    closers = DOUBLE_CLOSE if s[0] in DOUBLE_OPEN else SINGLE_CLOSE
    ends = [i for i in range(1, len(s)) if s[i] in closers]
    for i in ends:
        if QUOTE_END_RE.match(s[i + 1:]):
            return s[1:i], s[i + 1:]
    return (s[1:ends[-1]], s[ends[-1] + 1:]) if ends else (s[1:], "")


def locate(fragment, doc):
    """Line one fragment up against a raw file. Returns (tier, pages, divergence):

    'exact'       its letters run on unbroken in the source (a page break may intervene);
    'citation'    it matches once an in-text citation the quote drops unmarked is skipped;
    None          it departs from the source: wording changed, or words left out without
                  an ellipsis — an unmarked omission can reverse the sense ("is [not] a").
    divergence = (quote letter, source letter, kind) where the two first part, if they do;
    kind is 'citation', 'omits' or 'differs'.
    """
    q = _loose(fragment)
    pages, i = set(), doc.text.find(q)
    while i >= 0:                                        # every occurrence, for the page check
        pages |= doc.pages_between(i, i + len(q))
        i = doc.text.find(q, i + 1)
    if pages:
        return "exact", pages, None

    votes = Counter()                                    # where do the probes place the quote?
    for size in (ANCHOR, MIN_FRAGMENT):                  # shorter probes only if long ones all miss
        for k in range(0, max(1, len(q) - size + 1), size // 2):
            j = doc.text.find(q[k:k + size])
            if j >= 0:
                votes[j - k] += 1
        if votes:
            break
    if not votes:
        return None, set(), None
    s0 = max(0, votes.most_common(1)[0][0] - ANCHOR)
    window = doc.text[s0:s0 + 2 * len(q) + 2 * ANCHOR]
    blocks = [b for b in difflib.SequenceMatcher(None, q, window, autojunk=False).get_matching_blocks() if b.size]
    pages = doc.pages_between(s0 + blocks[0].b, s0 + blocks[-1].b + blocks[-1].size)

    if len(q) - sum(b.size for b in blocks) <= len(q) // 200:   # tolerate a stray OCR letter
        tier, where = "exact", None
        for x, y in zip(blocks, blocks[1:]):             # source text the quote skips over
            a, b = s0 + x.b + x.size, s0 + y.b
            if b <= a or _page_noise(doc, a, b):
                continue
            if CITATION_RE.fullmatch(doc.raw_between(a, b) or ""):
                tier, where = "citation", where or (x.a + x.size, a, "citation")
                continue
            return None, pages, (x.a + x.size, a, "omits" if b - a > TYPO else "differs")
        return tier, pages, where
    qi, sj = 0, s0
    for b in blocks:                                     # first quote letters the source lacks
        if b.a > qi:
            break
        qi, sj = b.a + b.size, s0 + b.b + b.size
    return None, pages, (qi, sj, "differs")


def _page_noise(doc, a, b):
    """Is source text a..b (letters) page furniture rather than words the quote left out?
    Either it straddles a page break (running head, footnotes), or it is a line that
    recurs through the document (a footer extraction dropped mid-page)."""
    k = bisect.bisect_left(doc.starts, a)
    if k < len(doc.starts) and doc.starts[k] <= b and b - a <= PAGE_BREAK_NOISE:
        return True
    return b - a >= MIN_FURNITURE and doc.text.count(doc.text[a:b]) >= max(3, len(doc.pages) // 10)


TIER_RANK = {"exact": 0, "citation": 1, None: 2}


def check_quote(text, docs):
    """Best result over the note's raw files: (tier, doc, pages, divergence kind, message)."""
    frags = [f for f in GAP_RE.split(text) if len(_loose(f)) >= MIN_FRAGMENT]
    if not frags:
        return "short", None, set(), None, None
    best = (None, None, set(), None, None)
    for doc in docs:
        tier, pages, kind, why = "exact", set(), None, None
        for f in frags:
            t, pg, where = locate(f, doc)
            pages |= pg
            if TIER_RANK[t] > TIER_RANK[tier]:
                tier, kind, why = t, None, None
            if t == tier and where and why is None:
                kind, skipped = where[2], where[2] != "differs"
                src, pg_no = doc.context(where[1], before=20 if skipped else 30, after=70 if skipped else 45)
                quoted = _snippet(f, _at_letter(f, where[0]), 45 if skipped else 30, 0 if skipped else 45)
                on_pg = f" (PDF page {pg_no})" if doc.paged else ""
                why = {"citation": f"drops an in-text citation without marking it: after “{quoted}” the source has “{src}”{on_pg}",
                       "omits": f"leaves out words without an ellipsis: after “{quoted}” the source goes on “{src}”{on_pg}",
                       "differs": f"departs from the source at “{quoted}”; the source reads “{src}”{on_pg}"}[kind]
        if TIER_RANK[tier] < TIER_RANK[best[0]] or (tier == best[0] and best[4] is None and why):
            best = (tier, doc, pages, kind, why)
    return best


def _preview(text, n=70):
    t = re.sub(r"\s+", " ", text).strip()
    return "“" + (t if len(t) <= n else t[:n].rstrip() + "…") + "”"


def check_quotes(root, notes):
    findings, cache = [], {}
    tally = Counter()
    add = lambda *a, **k: findings.append(Finding(*a, **k))

    for p in notes:
        quotes = list(quotes_in(p))
        if not quotes:
            continue
        tally["quotes"] += len(quotes)
        refs = raw_refs(root, p)
        docs, problems = [], []
        for r in refs:
            path = os.path.join(root, r)
            if not os.path.exists(path):
                problems.append(f"`{r}` not present")
                continue
            if path not in cache:
                try:
                    cache[path] = read_raw(path)
                except _Unreadable as e:
                    cache[path] = str(e)
            if isinstance(cache[path], str):
                problems.append(f"`{r}`: {cache[path]}")
            else:
                docs.append(cache[path])
        if not docs:
            why = "; ".join(problems) if problems else "the note links no raw file"
            add("info", "quote-unchecked", p.relpath, f"{len(quotes)} quote(s) not checked — {why}")
            tally["unchecked"] += len(quotes)
            continue

        results = []
        for line, text, tail in quotes:
            if re.search(r"(?i)\btrans(\.|lat)|my translation", tail):
                add("info", "quote-unchecked", p.relpath, f"translated, not checked: {_preview(text)}", line=line)
                tally["unchecked"] += 1
                continue
            tier, doc, pages, kind, why = check_quote(text, docs)
            if tier == "short":
                add("info", "quote-unchecked", p.relpath, f"too short to verify: {_preview(text)}", line=line)
                tally["unchecked"] += 1
                continue
            tally[tier or "missing"] += 1
            if tier is None:
                add("error", f"quote-{kind}" if why else "quote-missing", p.relpath,
                    why or f"not found in the raw file(s): {_preview(text)}", line=line)
                continue
            if tier == "citation":
                add("warn", "quote-citation", p.relpath, why, line=line)
            m = PAGE_RE.search(tail)
            if m and doc.paged and not re.search(r"(?i)approx|cf\.", tail):
                lo = int(m.group(1))
                hi = int(m.group(2)) if m.group(2) else lo
                if m.group(2) and len(m.group(2)) < len(m.group(1)):     # "pp. 166–7"
                    hi = int(m.group(1)[:-len(m.group(2))] + m.group(2))
                results.append((line, text, doc, sorted(pages), lo, hi))

        # page check. Printed page = PDF page + offset. The offset comes from the page
        # numbers the PDF itself prints; failing that, from the offset most of the
        # note's quotes agree on (which cannot tell a consistent miscitation apart).
        for doc in docs:
            rows = [r for r in results if r[2] is doc]
            if not rows:
                continue
            offset, printed_known = doc.printed_offset(), True
            if offset is None:
                votes = Counter(r[4] - r[3][0] for r in rows if len(r[3]) == 1)
                offset, n = votes.most_common(1)[0] if votes else (None, 0)
                if n < 2 or n * 2 <= len(rows):
                    continue                                 # no consistent numbering to test against
                printed_known = False
            fits = lambda pages, lo, hi, off: any(lo <= pg + off <= hi for pg in pages)
            by_pdf = False
            if printed_known and offset:
                pdf_cited = [r for r in rows if not fits(r[3], r[4], r[5], offset) and fits(r[3], r[4], r[5], 0)]
                by_pdf = len(pdf_cited) * 2 > len(rows)
                if by_pdf:                                   # one warning, then judge by the note's convention
                    add("warn", "quote-page", p.relpath,
                        f"{len(pdf_cited)} of {len(rows)} quotes cite PDF page numbers, not the printed ones "
                        f"(printed page = PDF page {offset:+d})", line=pdf_cited[0][0])
                    tally["page"] += len(pdf_cited)
            for line, text, _doc, pages, lo, hi in rows:
                if not fits(pages, lo, hi, offset) and not (by_pdf and fits(pages, lo, hi, 0)):
                    cited = f"p. {lo}" if lo == hi else f"pp. {lo}–{hi}"
                    found = ", ".join(f"p. {pg + offset}" for pg in pages[:3])
                    basis = f"PDF page {pages[0]}" if printed_known else f"offset {offset:+d} inferred from the other quotes"
                    add("warn", "quote-page", p.relpath,
                        f"cited {cited}, but the passage is on {found} ({basis}): {_preview(text, 50)}", line=line)
                    tally["page"] += 1
    return findings, tally


# ─────────────────────────────────────────────────────────────────────────────
# Link graph — shared by `graph` and `move`
# ─────────────────────────────────────────────────────────────────────────────

def _body_lines(lines):
    """Yield (lineno, line) outside fenced code blocks."""
    in_fence = False
    for i, line in enumerate(lines, 1):
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if not in_fence:
            yield i, line


def _related(page):
    rel = page.fm.get("related")
    return rel if isinstance(rel, list) else ([rel] if rel else [])


def link_graph(root, pages):
    """Return (links, related): sets of (src, dst) relpath pairs between wiki pages."""
    paths = {p.relpath for p in pages}
    by_stem = {}
    for p in pages:
        by_stem.setdefault(p.stem, []).append(p.relpath)
    links, related = set(), set()
    for p in pages:
        for _i, line in _body_lines(p.lines):
            for target in _links_in(line):
                r = resolve_link(root, p.relpath, target)
                if r in paths and r != p.relpath:
                    links.add((p.relpath, r))
        for stem in _related(p):
            for r in by_stem.get(stem, []):
                if r != p.relpath:
                    related.add((p.relpath, r))
    return links, related


# ─────────────────────────────────────────────────────────────────────────────
# Graph — draw the wiki (or one page's neighbourhood) as a Mermaid diagram
# ─────────────────────────────────────────────────────────────────────────────

# type -> (open, close) node shape, and a fill that reads in light and dark themes
SHAPE = {"concept": ('("', '")'), "author": ('(["', '"])'), "source-note": ('[["', '"]]'),
         "debate": ('{{"', '"}}'), "synthesis": ('[/"', '"/]')}
FILL = {"concept": "#dbeafe,stroke:#3b82f6", "author": "#fce7f3,stroke:#db2777",
        "source-note": "#f1f5f9,stroke:#64748b", "debate": "#fef3c7,stroke:#d97706",
        "synthesis": "#dcfce7,stroke:#16a34a", "project": "#ede9fe,stroke:#7c3aed",
        "method": "#e0f2fe,stroke:#0284c7", "theme": "#ffedd5,stroke:#ea580c"}


def _find_page(pages, key):
    """Match a page by repo-relative path, filename, or stem."""
    key = key.strip().replace("/", os.sep)
    hits = [p for p in pages if key in (p.relpath, os.path.basename(p.relpath), p.stem)]
    return hits


def graph(root, pages, around=None, depth=1, types=None, max_nodes=60, direction="LR", all_edges=False):
    """Return (mermaid source, note) for the wiki graph, or raise ValueError.

    With `around`, only the edges by which each page was reached are drawn (a tree
    out from the centre), which stays readable; `all_edges` adds the cross-links too.
    """
    links, related = link_graph(root, pages)
    by_path = {p.relpath: p for p in pages}
    adj = {p.relpath: set() for p in pages}
    for a, b in links | related:
        adj[a].add(b)
        adj[b].add(a)

    if around:
        hits = _find_page(pages, around)
        if len(hits) != 1:
            raise ValueError(f"`{around}` matches {len(hits)} pages" + (
                ": " + ", ".join(h.relpath for h in hits) if hits else ""))
        keep, frontier, tree = {hits[0].relpath}, [hits[0].relpath], set()
        for _ in range(depth):
            nxt = []
            for f in frontier:
                for n in sorted(adj[f] - keep):
                    keep.add(n)
                    nxt.append(n)
                    tree.add(frozenset((f, n)))
            frontier = nxt
    else:
        keep = set(by_path)
    if types:
        centre = _find_page(pages, around)[0].relpath if around else None
        keep = {k for k in keep if by_path[k].type in types or k == centre}

    note = ""
    if len(keep) > max_nodes:
        ranked = sorted(keep, key=lambda k: (-len(adj[k] & keep), k))
        note = f"showing the {max_nodes} best-connected of {len(keep)} pages (raise --max-nodes to see more)"
        keep = set(ranked[:max_nodes])

    ids = {rp: f"n{i}" for i, rp in enumerate(sorted(keep))}
    out = [f"flowchart {direction}"]
    for rp in sorted(keep):
        p = by_path[rp]
        label = str(p.fm.get("title") or p.stem).replace('"', "#quot;")
        o, c = SHAPE.get(p.type, ('["', '"]'))
        out.append(f"    {ids[rp]}{o}{label}{c}")
    shown = (lambda a, b: a in keep and b in keep) if not around or all_edges else \
        (lambda a, b: frozenset((a, b)) in tree)
    drawn = set()
    for a, b in sorted(links):
        if shown(a, b) and (b, a) not in drawn:
            arrow = "<-->" if (b, a) in links else "-->"
            out.append(f"    {ids[a]} {arrow} {ids[b]}")
            drawn.add((a, b))
    for a, b in sorted(related):
        if shown(a, b) and (a, b) not in drawn and (b, a) not in drawn:
            out.append(f"    {ids[a]} -.- {ids[b]}")
            drawn.add((a, b))
    used = sorted({by_path[rp].type for rp in keep if by_path[rp].type in FILL})
    for t in used:
        out.append(f"    classDef {t.replace('-', '_')} fill:{FILL[t]},color:#1f2328")
        members = ",".join(ids[rp] for rp in sorted(keep) if by_path[rp].type == t)
        out.append(f"    class {members} {t.replace('-', '_')}")
    if around:
        out.append(f"    style {ids[_find_page(pages, around)[0].relpath]} stroke-width:3px")
    return "\n".join(out), note


# ─────────────────────────────────────────────────────────────────────────────
# Move — rename a page and rewrite every inbound link and `related:` entry
# ─────────────────────────────────────────────────────────────────────────────

def _relative(from_relpath, to_relpath):
    return os.path.relpath(to_relpath, os.path.dirname(from_relpath) or ".").replace(os.sep, "/")


def _rewrite_line_links(line, fn):
    """Apply fn(target) -> new target to every link on the line, outside inline code."""
    out, pos = [], 0
    for m in INLINE_CODE_RE.finditer(line):
        out.append(LINK_RE.sub(lambda lm: _swap(lm, fn), line[pos:m.start()]))
        out.append(m.group())
        pos = m.end()
    out.append(LINK_RE.sub(lambda lm: _swap(lm, fn), line[pos:]))
    return "".join(out)


def _swap(m, fn):
    new = fn(m.group(1))
    if new is None:
        return m.group()
    s, e = m.span(1)
    return m.group()[:s - m.start()] + new + m.group()[e - m.start():]


def _anchor(target):
    t = target.strip()
    return t[t.index("#"):] if "#" in t else ""


def move(root, old, new, dry_run=False):
    """Rename wiki page `old` to `new` (repo-relative); return a list of change descriptions."""
    if not old.startswith("wiki" + os.sep) or not new.startswith("wiki" + os.sep) or not new.endswith(".md"):
        raise ValueError("both paths must be .md pages under wiki/")
    if not os.path.isfile(os.path.join(root, old)):
        raise ValueError(f"no such page: {old}")
    if os.path.exists(os.path.join(root, new)):
        raise ValueError(f"already exists: {new}")
    old_stem = os.path.splitext(os.path.basename(old))[0]
    new_stem = os.path.splitext(os.path.basename(new))[0]
    stem_taken = old_stem != new_stem and any(
        os.path.splitext(os.path.basename(r))[0] == new_stem for r in iter_wiki_pages(root))

    changes, writes = [], {}
    files = list(iter_wiki_pages(root))
    idx = "index.md"
    if os.path.exists(os.path.join(root, idx)):
        files.append(idx)

    for rel in files:
        path = os.path.join(root, rel)
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
        here = new if rel == old else rel           # where this file will live afterwards
        n_links = n_rel = 0

        def fix(target, rel=rel, here=here):
            nonlocal n_links
            r = resolve_link(root, rel, target)
            if r is None:
                return None
            if r == old:
                n_links += 1
                return _relative(here, new) + _anchor(target)
            if rel == old and resolve_link(root, here, target) != r:   # own links that would break
                n_links += 1
                return _relative(here, r) + _anchor(target)
            return None

        body = dict(_body_lines(lines))
        fm_end = 0
        if lines and lines[0].rstrip() == "---":
            fm_end = next((i for i in range(1, len(lines)) if lines[i].rstrip() == "---"), 0)
        in_related = False
        for i in range(len(lines)):
            line = lines[i]
            if 0 < i < fm_end and old_stem != new_stem and not stem_taken:
                key = re.match(r"^(\S[^:]*?):", line)
                if key:
                    in_related = key.group(1).strip() == "related"
                if in_related:
                    new_line = re.sub(rf"(?<![\w-]){re.escape(old_stem)}(?![\w-])", new_stem, line)
                    if new_line != line:
                        n_rel += 1
                        lines[i] = line = new_line
            if (i + 1) in body:
                lines[i] = _rewrite_line_links(line, fix)
        if n_links or n_rel:
            writes[rel] = lines
            what = ", ".join(x for x in (f"{n_links} link(s)" if n_links else "",
                                         f"{n_rel} related entry" if n_rel else "") if x)
            changes.append(f"{rel}: {what}")

    if stem_taken:
        changes.append(f"note: stem `{new_stem}` is already used by another page, "
                       f"so `related:` entries naming `{old_stem}` were left unchanged")
    if not dry_run:
        for rel, lines in writes.items():
            with open(os.path.join(root, rel), "w", encoding="utf-8") as fh:
                fh.writelines(lines)
        os.makedirs(os.path.dirname(os.path.join(root, new)), exist_ok=True)
        os.rename(os.path.join(root, old), os.path.join(root, new))
    return changes


# ─────────────────────────────────────────────────────────────────────────────
# Reporting
# ─────────────────────────────────────────────────────────────────────────────

ICON = {"error": "✗", "warn": "!", "info": "·"}


def report(findings, npages, min_sev, unit="pages"):
    floor = SEV[min_sev]
    shown = [f for f in findings if SEV[f.sev] >= floor]
    shown.sort(key=lambda f: (-SEV[f.sev], f.code, f.relpath, f.line))

    counts = {"error": 0, "warn": 0, "info": 0}
    for f in findings:
        counts[f.sev] += 1

    order = {"error": [], "warn": [], "info": []}
    for f in shown:
        order[f.sev].append(f)
    for sev in ("error", "warn", "info"):
        group = order[sev]
        if not group:
            continue
        print(f"\n{ICON[sev]} {sev.upper()} ({len(group)})")
        for f in group:
            print(f"  {f.loc()}  [{f.code}] {f.msg}")

    print(f"\n{'─'*60}")
    print(f"{npages} {unit} · {counts['error']} error · {counts['warn']} warn · {counts['info']} info")
    return counts["error"]


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main(argv=None):
    ap = argparse.ArgumentParser(prog="wiki", description="Deterministic checks for the Research Wiki.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    lp = sub.add_parser("lint", help="check link integrity, orphans, index drift, frontmatter, markers")
    lp.add_argument("--root", help="wiki root (default: walk up for conventions.toml)")
    lp.add_argument("--min-severity", choices=["error", "warn", "info"], default="info")
    lp.add_argument("--type", help="restrict to one page type (e.g. concept, source-note)")
    qp = sub.add_parser("quotes", help="check source-note quotes against their raw files")
    qp.add_argument("notes", nargs="*", help="source notes to check (default: all)")
    qp.add_argument("--root", help="wiki root (default: walk up for conventions.toml)")
    qp.add_argument("--min-severity", choices=["error", "warn", "info"], default="info")
    gp = sub.add_parser("graph", help="draw the wiki's link graph as a Mermaid diagram")
    gp.add_argument("--around", metavar="PAGE", help="centre on one page (stem, filename or path)")
    gp.add_argument("--depth", type=int, default=1, help="link hops from --around (default 1)")
    gp.add_argument("--type", action="append", dest="types", metavar="TYPE",
                    help="only pages of this type (repeatable)")
    gp.add_argument("--max-nodes", type=int, default=60, help="keep the best-connected N pages (default 60)")
    gp.add_argument("--all-edges", action="store_true",
                    help="with --around, also draw links between the neighbours")
    gp.add_argument("--direction", choices=["LR", "TD"], default="LR")
    gp.add_argument("--raw", action="store_true", help="omit the ```mermaid fence")
    gp.add_argument("--root", help="wiki root (default: walk up for conventions.toml)")
    mp = sub.add_parser("move", help="rename a page and rewrite every link and related: entry to it")
    mp.add_argument("old")
    mp.add_argument("new")
    mp.add_argument("--dry-run", action="store_true", help="show what would change, write nothing")
    mp.add_argument("--root", help="wiki root (default: walk up for conventions.toml)")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.root) if args.root else find_root(os.getcwd())
    cfg_path = os.path.join(root, "conventions.toml")
    if not os.path.exists(cfg_path):
        print(f"error: no conventions.toml at {root}", file=sys.stderr)
        return 2

    if args.cmd == "lint":
        cfg = _load_toml(cfg_path)
        findings, npages = lint(root, cfg, type_filter=args.type)
        n_err = report(findings, npages, args.min_severity)
        return 1 if n_err else 0
    if args.cmd == "quotes":
        if args.notes:
            relpaths = [os.path.relpath(os.path.abspath(n), root) for n in args.notes]
            missing = [r for r in relpaths if not os.path.exists(os.path.join(root, r))]
            if missing:
                print(f"error: no such note: {', '.join(missing)}", file=sys.stderr)
                return 2
        else:
            relpaths = list(iter_wiki_pages(root))
        notes = [pg for pg in (Page(root, r) for r in sorted(relpaths))
                 if pg.type == "source-note" or pg.segment == "source-notes"]
        findings, t = check_quotes(root, notes)
        n_err = report(findings, len(notes), args.min_severity, unit="source notes")
        print(f"{t['quotes']} quotes · {t['exact']} verbatim · {t['citation']} drop a citation · "
              f"{t['missing']} differ or not found · {t['unchecked']} unchecked · {t['page']} page mismatch")
        return 1 if n_err else 0
    if args.cmd == "graph":
        pages = [Page(root, r) for r in sorted(iter_wiki_pages(root))]
        if not pages:
            print("error: the wiki has no pages yet", file=sys.stderr)
            return 2
        try:
            src, note = graph(root, pages, around=args.around, depth=args.depth, types=args.types,
                              max_nodes=args.max_nodes, direction=args.direction,
                              all_edges=args.all_edges)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        print(src if args.raw else f"```mermaid\n{src}\n```")
        if note:
            print(f"note: {note}", file=sys.stderr)
        return 0
    if args.cmd == "move":
        old, new = (os.path.relpath(os.path.abspath(x), root) for x in (args.old, args.new))
        try:
            changes = move(root, old, new, dry_run=args.dry_run)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        print(f"{'would move' if args.dry_run else 'moved'} {old} → {new}")
        for c in changes:
            print(f"  {c}")
        if not changes:
            print("  no inbound links to rewrite")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
