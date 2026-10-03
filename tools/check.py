#!/usr/bin/env python3
"""
Post-build checks: HTML well-formedness, internal links, and assets.

    py -3 tools/check.py
"""

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr"}
PHRASING_ONLY = {"span", "b", "i", "em", "strong", "small", "code", "button", "label", "summary"}
FLOW_ONLY = {"div", "ul", "ol", "li", "p", "section", "article", "aside", "nav",
             "header", "footer", "table", "form", "details", "pre", "blockquote",
             "h1", "h2", "h3", "h4", "h5", "h6"}
# SVG shapes are written self-closing (<path .../>), which arrives as a
# startend tag and is balanced there; <use> is written as an explicit pair.


class Checker(HTMLParser):
    def __init__(self, path):
        super().__init__(convert_charrefs=True)
        self.path = path
        self.stack = []
        self.errors = []
        self.ids = set()
        self.dup_ids = []
        self.links = []
        self.srcs = []
        self.h1s = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            if a["id"] in self.ids:
                self.dup_ids.append(a["id"])
            self.ids.add(a["id"])
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if tag in ("img", "script", "link") and (a.get("src") or a.get("href")):
            self.srcs.append(a.get("src") or a.get("href"))
        if tag == "h1":
            self.h1s += 1
        if tag == "img" and "alt" not in a:
            self.errors.append("img without alt at line %d" % self.getpos()[0])
        # Flow content inside a phrasing element is invalid and browsers will
        # silently restructure it, so catch it here instead.
        if tag in FLOW_ONLY:
            for open_tag, line in reversed(self.stack):
                if open_tag in PHRASING_ONLY:
                    self.errors.append("<%s> inside <%s> (opened line %d)"
                                       % (tag, open_tag, line))
                    break
                if open_tag not in ("a", "label"):
                    break
        if tag not in VOID:
            self.stack.append((tag, self.getpos()[0]))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.stack and self.stack[-1][0] == tag:
            self.stack.pop()

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack:
            self.errors.append("stray </%s> at line %d" % (tag, self.getpos()[0]))
            return
        if self.stack[-1][0] == tag:
            self.stack.pop()
            return
        for depth in range(len(self.stack) - 1, -1, -1):
            if self.stack[depth][0] == tag:
                unclosed = [t for t, _ in self.stack[depth + 1:]]
                self.errors.append("</%s> at line %d closes over unclosed %s"
                                   % (tag, self.getpos()[0], unclosed))
                del self.stack[depth:]
                return
        self.errors.append("unmatched </%s> at line %d" % (tag, self.getpos()[0]))


def resolve(page, href):
    """Map an internal href to the file that must exist."""
    parsed = urlparse(href)
    if parsed.scheme or parsed.netloc:
        return None
    path = parsed.path
    if not path:
        return None
    target = (ROOT / path.lstrip("/")) if path.startswith("/") else (page.parent / path)
    target = Path(target).resolve()
    if target.is_dir() or path.endswith("/"):
        target = target / "index.html"
    return target


def main():
    pages = sorted(ROOT.glob("*.html")) + sorted(ROOT.glob("programs/**/*.html"))
    problems = []
    checked_links = 0
    anchors = {}

    parsed_pages = []
    for page in pages:
        text = page.read_text(encoding="utf-8")
        checker = Checker(page)
        checker.feed(text)
        checker.close()
        anchors[page.resolve()] = checker.ids
        parsed_pages.append((page, checker))

        rel = page.relative_to(ROOT).as_posix()
        for err in checker.errors:
            problems.append("%s: %s" % (rel, err))
        if checker.stack:
            problems.append("%s: unclosed %s" % (rel, [t for t, _ in checker.stack][:6]))
        if checker.dup_ids:
            problems.append("%s: duplicate id(s) %s" % (rel, checker.dup_ids[:5]))
        if checker.h1s != 1:
            problems.append("%s: %d <h1> elements" % (rel, checker.h1s))

    for page, checker in parsed_pages:
        rel = page.relative_to(ROOT).as_posix()
        for href in checker.links + checker.srcs:
            if href.startswith("#"):
                if href[1:] and href[1:] not in checker.ids:
                    problems.append("%s: missing anchor %s" % (rel, href))
                continue
            target = resolve(page, href)
            if target is None:
                continue
            checked_links += 1
            if not target.exists():
                problems.append("%s: broken link %s" % (rel, href))
                continue
            fragment = urlparse(href).fragment
            if fragment and target.suffix == ".html":
                ids = anchors.get(target)
                if ids is None:
                    ids = Checker(target)
                    ids.feed(target.read_text(encoding="utf-8"))
                    ids = ids.ids
                    anchors[target] = ids
                if fragment not in ids:
                    problems.append("%s: %s has no #%s" % (rel, href, fragment))

    # Quiz payloads referenced by lesson pages must exist and parse.
    quiz_refs = set()
    for page in pages:
        quiz_refs |= set(re.findall(r'data-quiz-src="([^"]+)"', page.read_text(encoding="utf-8")))
    for ref in sorted(quiz_refs):
        target = ROOT / ref.lstrip("/")
        if not target.exists():
            problems.append("missing quiz payload %s" % ref)
            continue
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except Exception as exc:
            problems.append("bad JSON in %s: %s" % (ref, exc))
            continue
        if not data.get("forms") or not data["forms"][0]:
            problems.append("%s has no questions" % ref)

    # Every location id a feedback link can send must resolve in locations.csv,
    # or the report arrives in the sheet with no title against it.
    import csv as _csv
    for csv_path in ROOT.glob("content/*/locations.csv"):
        known = {row[0] for row in _csv.reader(csv_path.open(encoding="utf-8"))}
        emitted = set()
        for page in pages:
            emitted |= set(re.findall(r'data-loc="([^"]+)"',
                                      page.read_text(encoding="utf-8")))
        orphans = sorted(emitted - known)
        if orphans:
            problems.append("%s: %d location id(s) with no row, e.g. %s"
                            % (csv_path.name, len(orphans), ", ".join(orphans[:3])))

    print("checked %d pages, %d links, %d quiz payloads" % (len(pages), checked_links, len(quiz_refs)))
    if problems:
        print("%d problem(s):" % len(problems))
        for problem in problems[:40]:
            print("  - %s" % problem)
        if len(problems) > 40:
            print("  ... and %d more" % (len(problems) - 40))
        return 1
    print("no problems found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
