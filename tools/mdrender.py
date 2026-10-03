r"""
Markdown -> HTML renderer for the Knowledge InSight course files.

This is deliberately not a general Markdown implementation. The source files are
machine-generated and use a small, regular subset: ATX headings, paragraphs,
bullet and ordered lists (one level of nesting), block quotes, pipe tables,
fenced code blocks, horizontal rules, and inline emphasis / code / links.
Writing to that subset keeps the build dependency-free and makes the output
predictable, which matters when 366 items have to render identically.

Two quirks of the source are handled here:
  * Backslash escapes before punctuation (``2017\.``, ``Module 1 \- Lesson 1``)
    are artifacts of the original export and must be unescaped, not rendered.
  * Many list lines end in two trailing spaces. Those are stripped rather than
    turned into <br>, since they are export noise, not intentional line breaks.
"""

import re

__all__ = ["render", "inline", "unescape_md", "strip_md", "html_escape"]

_ESCAPABLE = r"\\`*_{}\[\]()#+\-.!|>~<&\"'"
_SENTINEL = "\x00"

# Bold may wrap italics: the source writes key terms as
# ``**Garb of ideas (*Ideenkleid*):**``. A lone asterisk inside the span is
# therefore allowed, and the italic pass runs afterwards over the result.
_BOLD = re.compile(r"\*\*((?:[^*]|\*(?!\*))+?)\*\*")
_ITALIC = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")


def html_escape(text, quote=False):
    out = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    if quote:
        out = out.replace('"', "&quot;")
    return out


def unescape_md(text):
    """Remove the export's backslash escapes: ``2017\\.`` -> ``2017.``"""
    return re.sub(r"\\([" + _ESCAPABLE + r"])", r"\1", text)


def strip_md(text):
    """Flatten inline markup to plain text (for titles, slugs, meta tags)."""
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,2}([^_]+)_{1,2}", r"\1", text)
    return unescape_md(text).strip()


# --------------------------------------------------------------------------
# Inline
# --------------------------------------------------------------------------

def _external(url):
    return url.startswith("http://") or url.startswith("https://")


def inline(text):
    """Render inline markup. Escapes and code spans are stashed before the
    rest of the string is HTML-escaped, so neither can be re-interpreted."""
    stash = []

    def put(html):
        stash.append(html)
        return "%s%d%s" % (_SENTINEL, len(stash) - 1, _SENTINEL)

    # 1. Backslash escapes become literal characters, immune to later passes.
    text = re.sub(r"\\([" + _ESCAPABLE + r"])",
                  lambda m: put(html_escape(m.group(1), quote=True)), text)

    # 2. Code spans keep their contents verbatim.
    text = re.sub(r"`([^`]+)`",
                  lambda m: put("<code>%s</code>" % html_escape(m.group(1))), text)

    # 3. Everything still in the stream is literal text.
    text = html_escape(text)

    # 4. Links. The label is emphasised in place; the whole anchor is stashed
    #    so the emphasis passes below cannot straddle the tag.
    def link(m):
        label, url = m.group(1), m.group(2)
        label = _BOLD.sub(r"<strong>\1</strong>", label)
        label = _ITALIC.sub(r"<em>\1</em>", label)
        attrs = ' target="_blank" rel="noopener"' if _external(url) else ""
        return put('<a href="%s"%s>%s</a>' % (url.replace('"', "&quot;"), attrs, label))

    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, text)

    # 5. Emphasis, strongest first, so that bold wrapping italics survives.
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    text = _ITALIC.sub(r"<em>\1</em>", text)

    # 6. Restore.
    return re.sub(_SENTINEL + r"(\d+)" + _SENTINEL,
                  lambda m: stash[int(m.group(1))], text)


# --------------------------------------------------------------------------
# Block
# --------------------------------------------------------------------------

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET = re.compile(r"^(\s*)[-*+]\s+(.*)$")
_ORDERED = re.compile(r"^(\s*)(\d+)\.\s+(.*)$")
_HRULE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
_FENCE = re.compile(r"^\s*```+\s*(\w*)\s*$")
_TABLE_SEP = re.compile(r"^\s*\|?[\s:|-]+\|[\s:|-]*$")


def _heading_text(raw):
    """Item headings arrive fully bolded: ``# **Title**``."""
    raw = raw.strip()
    if raw.startswith("**") and raw.endswith("**") and len(raw) > 4:
        raw = raw[2:-2]
    return raw.strip()


def _split_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def render(md, base_level=2, heading_ids=False):
    """Render a block of Markdown.

    base_level shifts headings down the document outline: with base_level=2 a
    source ``##`` becomes an ``<h3>``, which keeps a single ``<h1>`` per page.
    """
    if isinstance(md, str):
        lines = md.split("\n")
    else:
        lines = list(md)

    out = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # Fenced code -------------------------------------------------------
        fence = _FENCE.match(line)
        if fence:
            lang = fence.group(1)
            i += 1
            buf = []
            while i < n and not _FENCE.match(lines[i]):
                buf.append(lines[i])
                i += 1
            i += 1  # closing fence
            cls = ' class="language-%s"' % lang if lang else ""
            out.append("<pre><code%s>%s</code></pre>" % (cls, html_escape("\n".join(buf))))
            continue

        # Horizontal rule ---------------------------------------------------
        if _HRULE.match(line) and not _TABLE_SEP.match(line):
            out.append("<hr>")
            i += 1
            continue

        # Heading -----------------------------------------------------------
        head = _HEADING.match(stripped)
        if head:
            level = min(len(head.group(1)) + base_level - 1, 6)
            text = _heading_text(head.group(2))
            attrs = ""
            if heading_ids:
                slug = re.sub(r"[^a-z0-9]+", "-", strip_md(text).lower()).strip("-")
                if slug:
                    attrs = ' id="%s"' % slug[:60]
            out.append("<h%d%s>%s</h%d>" % (level, attrs, inline(text), level))
            i += 1
            continue

        # Table ---------------------------------------------------------------
        if stripped.startswith("|") and i + 1 < n and _TABLE_SEP.match(lines[i + 1]):
            header = _split_row(lines[i])
            i += 2
            body = []
            while i < n and lines[i].strip().startswith("|"):
                body.append(_split_row(lines[i]))
                i += 1
            cells = "".join("<th scope=\"col\">%s</th>" % inline(c) for c in header)
            rows = []
            for row in body:
                tds = "".join("<td>%s</td>" % inline(c) for c in row)
                rows.append("<tr>%s</tr>" % tds)
            out.append(
                '<div class="table-wrap"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>'
                % (cells, "".join(rows))
            )
            continue

        # Block quote ---------------------------------------------------------
        if stripped.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append("<blockquote>%s</blockquote>" % render(buf, base_level, heading_ids))
            continue

        # Lists ---------------------------------------------------------------
        if _BULLET.match(line) or _ORDERED.match(line):
            html, i = _render_list(lines, i, base_level)
            out.append(html)
            continue

        # Paragraph -----------------------------------------------------------
        buf = []
        while i < n:
            cur = lines[i]
            s = cur.strip()
            if (not s or _HEADING.match(s) or _HRULE.match(cur) or _FENCE.match(cur)
                    or s.startswith(">") or s.startswith("|")
                    or _BULLET.match(cur) or _ORDERED.match(cur)):
                break
            buf.append(s)
            i += 1
        if buf:
            out.append("<p>%s</p>" % inline(" ".join(buf)))

    return "".join(out)


def _indent_of(line):
    return len(line) - len(line.lstrip(" "))


def _render_list(lines, i, base_level):
    """Render one list, recursing for indented sub-lists."""
    n = len(lines)
    base_indent = _indent_of(lines[i])
    ordered = bool(_ORDERED.match(lines[i]))
    items = []

    while i < n:
        line = lines[i]
        if not line.strip():
            # A blank line ends the list unless an item continues after it.
            nxt = i + 1
            while nxt < n and not lines[nxt].strip():
                nxt += 1
            if nxt >= n:
                break
            m = _BULLET.match(lines[nxt]) or _ORDERED.match(lines[nxt])
            if not m or _indent_of(lines[nxt]) < base_indent:
                break
            i = nxt
            continue

        m = _BULLET.match(line) or _ORDERED.match(line)
        if not m:
            break

        indent = _indent_of(line)
        if indent < base_indent:
            break
        if indent > base_indent:
            sub, i = _render_list(lines, i, base_level)
            if items:
                items[-1] += sub
            else:
                items.append(sub)
            continue

        is_ordered = bool(_ORDERED.match(line))
        if is_ordered != ordered:
            break

        text = m.group(3) if is_ordered else m.group(2)
        items.append(inline(text.strip()))
        i += 1

    tag = "ol" if ordered else "ul"
    body = "".join("<li>%s</li>" % it for it in items)
    return "<%s>%s</%s>" % (tag, body, tag), i
