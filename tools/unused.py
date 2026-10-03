#!/usr/bin/env python3
"""
Report assets and source images that nothing references.

Looks for each file's name in the generated HTML, the stylesheet, the scripts,
the build sources, and the docs. Anything unmentioned is a deletion candidate.

    py -3 tools/unused.py

Source images under images/ are treated separately: one is "used" if a file in
assets/img/ was derived from it, which the report has to be told about, since
that link exists only in the commands that generated the derivative.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# assets/img file -> the images/ original it was generated from.
DERIVED_FROM = {
    "hero-books-blue-480.jpg": "knowledge-insight-background.jpg",
    "hero-books-blue-800.jpg": "knowledge-insight-background.jpg",
    "hero-books-blue-1280.jpg": "knowledge-insight-background.jpg",
    "hero-books-blue-1920.jpg": "knowledge-insight-background.jpg",
    "og-card.jpg": "KI background.png",
    "apple-touch-icon.png": "logo.png",
    "favicon-32.png": "logo.png",
    "logo-mark-256.png": "logo.png",
    "adam-h.jpg": "adam-h.jpg",
}

SEARCH_GLOBS = [
    "*.html", "programs/**/*.html", "assets/css/*.css", "assets/js/*.js",
    "tools/*.py", "tools/*.html", "tools/*.ps1", "content/*.json",
    "*.md", "*.bat",
]


def haystack(skip_dir=None):
    text = []
    for pattern in SEARCH_GLOBS:
        for path in ROOT.glob(pattern):
            if skip_dir and skip_dir in path.parts:
                continue
            try:
                text.append(path.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                pass
    return "\n".join(text)


def main():
    blob = haystack()
    unused = []

    print("assets/img")
    for path in sorted((ROOT / "assets" / "img").glob("*")):
        if path.name in blob.replace(path.name, path.name):  # literal search
            referenced = path.name in blob
        else:
            referenced = False
        mark = "used" if referenced else "UNUSED"
        print("  %-28s %s" % (path.name, mark))
        if not referenced:
            unused.append(path)

    used_originals = {
        DERIVED_FROM[p.name] for p in (ROOT / "assets" / "img").glob("*")
        if p.name in DERIVED_FROM and p.name in blob
    }

    print("\nimages (originals)")
    for path in sorted((ROOT / "images").glob("*")):
        if path.name in used_originals:
            reason = "used  (source of an asset in assets/img)"
        elif path.name in blob:
            reason = "used  (referenced directly)"
        else:
            reason = "UNUSED"
            unused.append(path)
        print("  %-40s %s" % (path.name, reason))

    print("\nother files at the repo root")
    for path in sorted(ROOT.glob("*")):
        if path.is_dir() or path.name.startswith("."):
            continue
        if path.suffix in (".html", ".md", ".bat"):
            # index.html and about.html are generated; README and the launchers
            # are obviously in use. Flag only strays.
            if path.name in ("index.html", "about.html", "README.md",
                             "serve.bat", "serve-phone.bat"):
                continue
            print("  %-40s STRAY (not generated, not linked)" % path.name)
            unused.append(path)

    print("\n%d deletion candidate(s)" % len(unused))
    for path in unused:
        print("  rm %s" % path.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main())
