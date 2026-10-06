#!/usr/bin/env python3
"""
A small structural check for the site's JavaScript.

There is no Node on this machine, so this is not a parser. It is a lexer that
understands strings, template literals, regex literals, and both comment forms,
then verifies that quotes terminate on their line and that every bracket pair
balances. That catches the class of damage a careless edit does -- an unclosed
string, a stray brace -- without pretending to be a syntax checker.

    py -3 tools/jslint.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAIRS = {")": "(", "]": "[", "}": "{"}
OPENERS = set(PAIRS.values())

# A '/' starts a regex literal only where a value may begin.
REGEX_OK_AFTER = set("(,=:[!&|?{};+-*%~^<>") | {"return", "typeof", "case", "in", "of", "new", "delete", "void"}


def check(path):
    src = path.read_text(encoding="utf-8")
    problems = []
    stack = []
    i, n = 0, len(src)
    line = 1
    prev_token = ""

    while i < n:
        ch = src[i]

        if ch == "\n":
            line += 1
            i += 1
            continue

        # Comments -----------------------------------------------------
        if ch == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and src[i + 1] == "*":
            end = src.find("*/", i + 2)
            if end == -1:
                problems.append("line %d: unterminated /* comment" % line)
                break
            line += src.count("\n", i, end)
            i = end + 2
            continue

        # Strings ------------------------------------------------------
        if ch in "\"'":
            start_line = line
            i += 1
            closed = False
            while i < n:
                if src[i] == "\\":
                    i += 2
                    continue
                if src[i] == "\n":
                    break
                if src[i] == ch:
                    closed = True
                    i += 1
                    break
                i += 1
            if not closed:
                problems.append("line %d: unterminated %s string" % (start_line, ch))
            prev_token = "str"
            continue

        # Template literals --------------------------------------------
        if ch == "`":
            start_line = line
            i += 1
            closed = False
            while i < n:
                if src[i] == "\\":
                    i += 2
                    continue
                if src[i] == "\n":
                    line += 1
                if src[i] == "`":
                    closed = True
                    i += 1
                    break
                i += 1
            if not closed:
                problems.append("line %d: unterminated template literal" % start_line)
            prev_token = "str"
            continue

        # Regex literals -----------------------------------------------
        if ch == "/" and (prev_token in REGEX_OK_AFTER or prev_token == ""):
            start_line = line
            j = i + 1
            closed = False
            in_class = False
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == "\n":
                    break
                if src[j] == "[":
                    in_class = True
                elif src[j] == "]":
                    in_class = False
                elif src[j] == "/" and not in_class:
                    closed = True
                    j += 1
                    break
                j += 1
            if closed:
                while j < n and src[j] in "gimsuy":
                    j += 1
                i = j
                prev_token = "re"
                continue
            problems.append("line %d: unterminated regex literal" % start_line)

        # Brackets -----------------------------------------------------
        if ch in OPENERS:
            stack.append((ch, line))
        elif ch in PAIRS:
            if not stack:
                problems.append("line %d: stray '%s'" % (line, ch))
            elif stack[-1][0] != PAIRS[ch]:
                problems.append("line %d: '%s' closes '%s' opened on line %d"
                                % (line, ch, stack[-1][0], stack[-1][1]))
                stack.pop()
            else:
                stack.pop()

        if not ch.isspace():
            prev_token = ch if not (ch.isalnum() or ch == "_") else prev_token + ch
            if not (ch.isalnum() or ch == "_"):
                prev_token = ch
        i += 1

    for opener, opened_line in stack:
        problems.append("unclosed '%s' opened on line %d" % (opener, opened_line))
    return problems


def main():
    files = sorted((ROOT / "docs" / "assets" / "js").glob("*.js"))
    total = 0
    for path in files:
        problems = check(path)
        total += len(problems)
        status = "ok" if not problems else "%d problem(s)" % len(problems)
        print("%-14s %s" % (path.name, status))
        for problem in problems[:10]:
            print("    - %s" % problem)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
