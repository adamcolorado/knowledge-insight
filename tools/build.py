#!/usr/bin/env python3
r"""
Build the Knowledge InSight static site from the course markdown.

    py -3 tools/build.py          # build
    py -3 tools/build.py --clean  # remove generated output first

Output is plain pre-rendered HTML: every reading is in the page source, so the
site is readable with JavaScript disabled and indexes properly. JavaScript adds
navigation state, progress, quizzes, and the Claude dialogue links.

Nothing here is specific to a single program. Adding a second program means
adding an entry to content/site.json and dropping its markdown in markdown/.
"""

import argparse
import datetime
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mdrender import html_escape, render, strip_md                # noqa: E402
from parse import (ASSIGNMENT, DIALOGUE, GRADED_QUIZ, ITEM_META,  # noqa: E402
                   JOURNAL, KNOWLEDGE_CHECK, READING, parse_course)

ROOT = Path(__file__).resolve().parent.parent
MARKDOWN = ROOT / "markdown"
CONTENT = ROOT / "content"
BUILD_MARKER = """<!-- ============================================================
     GENERATED FILE - DO NOT EDIT
     Every `py -3 tools/build.py` overwrites this file.
     Edit the source instead:
       copy, headings, bio, status  ->  content/site.json
       course content               ->  markdown/
       layout and markup            ->  tools/build.py
       styling                      ->  assets/css/main.css
     ============================================================ -->"""

GENERATED_DIRS = ["programs"]
GENERATED_FILES = ["index.html", "about.html"]


# ==========================================================================
# Icons
# ==========================================================================

ICONS = {
    "reading": '<path d="M2 4.5h6.5A3.5 3.5 0 0 1 12 8v12a3 3 0 0 0-3-2.5H2Z"/>'
               '<path d="M22 4.5h-6.5A3.5 3.5 0 0 0 12 8v12a3 3 0 0 1 3-2.5H22Z"/>',
    "dialogue": '<path d="m12 3 1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9Z"/>'
                '<path d="m18.5 15 .7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7Z"/>',
    "journal": '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
    "check": '<path d="M22 11.1V12a10 10 0 1 1-5.9-9.1"/><path d="M22 4 12 14l-3-3"/>',
    "quiz": '<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>'
            '<rect x="8" y="2" width="8" height="4" rx="1"/><path d="m9 14 2 2 4-4"/>',
    "assignment": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/>'
                  '<path d="M14 2v6h6"/><path d="M8 13h5"/><path d="M8 17h8"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/>',
    "arrow-right": '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
    "arrow-left": '<path d="M19 12H5"/><path d="m12 19-7-7 7-7"/>',
    "menu": '<path d="M3 6h18"/><path d="M3 12h18"/><path d="M3 18h18"/>',
    "close": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "chevron": '<path d="m6 9 6 6 6-6"/>',
    "external": '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>'
                '<path d="M15 3h6v6"/><path d="M10 14 21 3"/>',
    "copy": '<rect x="9" y="9" width="12" height="12" rx="2"/>'
            '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    "map": '<path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2Z"/><path d="M9 4v14"/><path d="M15 6v14"/>',
    "list": '<path d="M8 6h13"/><path d="M8 12h13"/><path d="M8 18h13"/>'
            '<path d="M3 6h.01"/><path d="M3 12h.01"/><path d="M3 18h.01"/>',
    "print": '<path d="M6 9V2h12v7"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/>'
             '<path d="M6 14h12v8H6Z"/>',
    "sparkle-small": '<path d="m12 4 1.6 4.4L18 10l-4.4 1.6L12 16l-1.6-4.4L6 10l4.4-1.6Z"/>',
    # Vetting seals: a validated badge, and one still under review.
    "seal-check": '<path d="M12 2.5 14.6 5l3.5-.3.9 3.4 2.8 2.1-1.7 3.1 1.7 3.1-2.8 2.1-.9 3.4-3.5-.3L12 21.5 9.4 19l-3.5.3-.9-3.4-2.8-2.1L3.9 10 2.2 7l2.8-2.1.9-3.4L9.4 5Z"/>'
                  '<path d="m8.6 12.1 2.3 2.3 4.5-4.5"/>',
    "seal-progress": '<path d="M12 2.5 14.6 5l3.5-.3.9 3.4 2.8 2.1-1.7 3.1 1.7 3.1-2.8 2.1-.9 3.4-3.5-.3L12 21.5 9.4 19l-3.5.3-.9-3.4-2.8-2.1L3.9 10 2.2 7l2.8-2.1.9-3.4L9.4 5Z"/>'
                     '<path d="M12 7.6v4.6l2.9 1.7"/>',
    # The brand mark. It lives in the sprite rather than being loaded as an
    # <img> so that currentColor resolves and it can sit on any background.
    "mark": '<circle cx="12" cy="12" r="10.6" stroke-width="1.5"/>'
            '<path d="M12 9.2c-2.2-2-5.9-2.4-8.2-2v6.7c2.3-.4 6 0 8.2 2Z" stroke-width="1.4"/>'
            '<path d="M12 9.2c2.2-2 5.9-2.4 8.2-2v6.7c-2.3-.4-6 0-8.2 2Z" stroke-width="1.4"/>'
            '<path d="M12 9.2v6.7" stroke-width="1.4"/>',
}


def sprite():
    symbols = []
    for name, body in ICONS.items():
        symbols.append(
            '<symbol id="ic-%s" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">%s</symbol>'
            % (name, body)
        )
    return '<svg class="sprite" aria-hidden="true" focusable="false">%s</svg>' % "".join(symbols)


def icon(name, cls="ico"):
    return '<svg class="%s" aria-hidden="true" focusable="false"><use href="#ic-%s"></use></svg>' % (cls, name)


# ==========================================================================
# Small helpers
# ==========================================================================

def attr(value):
    return html_escape(str(value), quote=True)


def fmt_minutes(total):
    if not total:
        return ""
    hours, minutes = divmod(int(total), 60)
    if hours and minutes:
        return "%dh %dm" % (hours, minutes)
    if hours:
        return "%dh" % hours
    return "%dm" % minutes


def plural(count, word, suffix="s"):
    return "%d %s%s" % (count, word, "" if count == 1 else suffix)


def clip(text, limit):
    """Trim to a word boundary and add an ellipsis, rather than cutting mid-word."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    if " " in cut:
        cut = cut[:cut.rindex(" ")]
    return cut.rstrip(" ,;:.") + "…"


def item_minutes(items, include_optional=True):
    return sum(i["durationMin"] or 0 for i in items
               if include_optional or not i["optional"])


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ==========================================================================
# Page shell
# ==========================================================================

def page(title, body, description="", body_class="", site=None,
         canonical="", extra_head="", scripts=(), program_id=""):
    site = site or {}
    org = site.get("org", "Knowledge InSight")
    full_title = title if title == org else "%s | %s" % (title, org)
    desc = description or site.get("tagline", "")
    script_tags = "".join(
        '<script src="/assets/js/%s" defer></script>' % s for s in scripts)
    return f"""<!doctype html>
{BUILD_MARKER}
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{attr(full_title)}</title>
<meta name="description" content="{attr(desc)}">
<meta property="og:title" content="{attr(full_title)}">
<meta property="og:description" content="{attr(desc)}">
<meta property="og:type" content="website">
<meta property="og:image" content="/assets/img/og-card.jpg">
<meta name="twitter:card" content="summary_large_image">
{f'<link rel="canonical" href="{attr(canonical)}">' if canonical else ''}
<link rel="icon" href="/assets/img/favicon-32.png" sizes="32x32">
<link rel="icon" href="/assets/img/ki-mark.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/assets/img/apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Sans+3:ital,wght@0,400;0,500;0,600;0,700;1,400&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap">
<link rel="stylesheet" href="/assets/css/main.css">
{extra_head}
</head>
<body class="{attr(body_class)}" data-program="{attr(program_id)}">
<a class="skip-link" href="#main">Skip to main content</a>
{sprite()}
{masthead(site)}
{body}
{site_foot(site)}
<script src="/assets/js/site.js" defer></script>
{script_tags}
</body>
</html>
"""


def masthead(site):
    return f"""<header class="masthead">
  <div class="masthead-inner">
    <a class="brand" href="/">
      {icon('mark', 'brand-mark')}
      <span class="brand-words"><span>Knowledge</span><span>InSight</span></span>
    </a>
    <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="site-nav">
      {icon('menu')}<span class="u-visually-hidden">Menu</span>
    </button>
    <nav class="site-nav" id="site-nav" aria-label="Main">
      <a href="/#programs">Programs</a>
      <a href="/about.html">About</a>
    </nav>
  </div>
</header>"""


def site_foot(site):
    org = site.get("org", "Knowledge InSight")
    legal = site.get("legalName", org)
    return f"""<footer class="site-foot">
  <div class="site-foot-inner">
    <p class="foot-brand">{html_escape(org)}</p>
    <p class="foot-tag">{html_escape(site.get('tagline', ''))}</p>
    <nav class="foot-nav" aria-label="Footer">
      <a href="/">Home</a><a href="/about.html">About</a><a href="/#programs">Programs</a>
    </nav>
    <p class="foot-fine">Open access. Self-paced. Your progress is stored in this browser only.</p>
    <p class="foot-fine foot-legal">&copy; <span data-year>{datetime.date.today().year}</span> {html_escape(legal)}
      <span aria-hidden="true">&middot;</span> {contact_link(site)}</p>
  </div>
</footer>"""


def contact_link(site):
    """The footer contact link, kept out of reach of address harvesters.

    The address never appears in the HTML: user and domain are stored
    reversed in data attributes and site.js assembles the mailto: on load.
    Without JavaScript the reader gets a spelled-out address instead.
    """
    user = site.get("contactUser", "contact")
    domain = site.get("domain", "knowledgeinsight.org")
    spelled = "%s at %s" % (user, domain.replace(".", " dot "))
    return ('<a class="foot-mail" data-mail-u="%s" data-mail-d="%s">Contact us</a>'
            '<noscript> (%s)</noscript>'
            % (attr(user[::-1]), attr(domain[::-1]), html_escape(spelled)))


# ==========================================================================
# Program model helpers
# ==========================================================================

def program_href(program):
    return "/programs/%s/" % program["id"]


def course_href(program, course):
    return "%s%s/" % (program_href(program), course["slug"])


def module_href(program, course, module):
    return "%s%s/" % (course_href(program, course), module["slug"])


def lesson_href(program, course, module, lesson):
    return "%s%s/" % (module_href(program, course, module), lesson["slug"])


def project_href(program, course):
    return "%scourse-project/" % course_href(program, course)


def lesson_id(course, module, lesson):
    return "c%d.m%d.l%d" % (course["num"], module["num"], lesson["num"])


def project_id(course):
    return "c%d.project" % course["num"]


def item_id(scope, index):
    return "%s.i%d" % (scope, index + 1)


def walk_stops(program):
    """Flatten the program into the linear order a learner moves through.

    Every stop is a page: course overview, module overview, lesson, project.
    The Prev/Next control walks this list, so it crosses module and course
    boundaries without the learner having to climb back up the hierarchy.
    """
    stops = []
    for course in program["courses"]:
        stops.append({
            "kind": "course", "title": course["title"], "titleHtml": course["titleHtml"],
            "href": course_href(program, course),
            "label": "Course %d" % course["num"], "course": course,
        })
        for module in course["modules"]:
            stops.append({
                "kind": "module", "title": module["title"], "titleHtml": module["titleHtml"],
                "href": module_href(program, course, module),
                "label": "Course %d · Module %d" % (course["num"], module["num"]),
                "course": course, "module": module,
            })
            for lesson in module["lessons"]:
                stops.append({
                    "kind": "lesson", "title": lesson["title"], "titleHtml": lesson["titleHtml"],
                    "href": lesson_href(program, course, module, lesson),
                    "label": "Module %d · Lesson %d" % (module["num"], lesson["num"]),
                    "course": course, "module": module, "lesson": lesson,
                })
        if course.get("project"):
            stops.append({
                "kind": "project", "title": course["project"]["title"],
                "titleHtml": course["project"]["titleHtml"],
                "href": project_href(program, course),
                "label": "Course %d · Project" % course["num"],
                "course": course, "lesson": course["project"],
            })
    return stops


# ==========================================================================
# Shared components
# ==========================================================================

def crumbs(parts):
    links = []
    for idx, (label, href) in enumerate(parts):
        last = idx == len(parts) - 1
        if href and not last:
            links.append('<li><a href="%s">%s</a></li>' % (attr(href), html_escape(label)))
        else:
            links.append('<li><span aria-current="page">%s</span></li>' % html_escape(label))
    return '<nav class="crumbs" aria-label="Breadcrumb"><ol>%s</ol></nav>' % "".join(links)


def progress_ring(target, count, label="progress"):
    """A small dot whose fill is driven by progress.js."""
    return ('<span class="pdot" data-progress-for="%s" data-item-count="%d" '
            'role="img" aria-label="%s"></span>' % (attr(target), count, attr(label)))


def picker(label, current, options, menu_id, grouped=False, kind=""):
    """A breadcrumb segment that opens its siblings.

    The outline sidebar used to carry this. Folding it into the breadcrumb
    keeps every jump one click away without a permanent column of links
    competing with the reading.
    """
    rows = []
    if grouped:
        for group, entries in options:
            rows.append('<li class="lbm-group">%s</li>' % html_escape(group))
            rows += ['<li><a href="%s"%s><span class="lbm-num">%s</span>'
                     '<span class="lbm-text">%s</span></a></li>'
                     % (attr(href), ' class="is-current"' if current_row else '',
                        html_escape(num), text)
                     for num, text, href, current_row in entries]
    else:
        rows = ['<li><a href="%s"%s><span class="lbm-num">%s</span>'
                '<span class="lbm-text">%s</span></a></li>'
                % (attr(href), ' class="is-current"' if current_row else '',
                   html_escape(num), text)
                for num, text, href, current_row in options]

    return (
        '<li class="lb-crumb lb-pick lb-pick--%s">'
        '<button type="button" class="lb-pick-btn" aria-expanded="false" aria-controls="%s">'
        '<span class="lb-pick-label">%s</span>%s</button>'
        '<div class="lb-menu" id="%s" hidden><ul>%s</ul></div></li>'
        % (kind or menu_id, menu_id, html_escape(label),
           icon('chevron', 'ico lb-caret'), menu_id, ''.join(rows)))


def learn_bar(site, program, course, module=None, lesson=None, scope=None,
              items=None, is_project=False):
    """The one navigation surface on a learning page.

    One left-aligned line: where you are, how to jump anywhere, and how to step
    between items. Course progress sits beneath it. Nothing is pushed to the
    right edge, so the eye reads one thing rather than two competing groups.
    """
    # The map is the way back up; a separate Program crumb was one hop too many.
    crumb_items = [
        '<li class="lb-crumb lb-mapcrumb"><a class="lb-map" href="%smap/">%s<span>Map</span></a></li>'
        % (attr(program_href(program)), icon("map"))]

    # Course picker
    crumb_items.append(picker(
        "Course %d" % course["num"], course,
        [("%d" % other["num"], other["titleHtml"], course_href(program, other),
          other["slug"] == course["slug"]) for other in program["courses"]],
        "lb-courses", kind="course"))

    # Module picker. On a course overview no module is selected yet, so the
    # control names what it opens rather than claiming a position.
    if course["modules"]:
        # A project belongs to no module, so this control just opens the list.
        label = "Module %d" % module["num"] if module else "Modules"
        crumb_items.append(picker(
            label, module,
            [("M%d" % other["num"], other["titleHtml"], module_href(program, course, other),
              bool(module) and other["num"] == module["num"])
             for other in course["modules"]]
            + ([("P", course["project"]["titleHtml"], project_href(program, course), is_project)]
               if course.get("project") else []),
            "lb-modules", kind="module"))

    # Lesson picker: every lesson in the course, grouped by module, so a jump
    # across modules is still one click. It renders on course and module
    # overviews too -- there is no current lesson to name there, but the
    # destinations are just as useful, and a bar that changes shape as you
    # move through a course reads as broken.
    if course["modules"]:
        groups = []
        for other_module in course["modules"]:
            groups.append((
                "Module %d: %s" % (other_module["num"], other_module["title"]),
                [("%d.%d" % (other_module["num"], other["num"]), other["titleHtml"],
                  lesson_href(program, course, other_module, other),
                  # Nothing is current on a course or module overview.
                  not is_project and module is not None and lesson is not None
                  and other_module["num"] == module["num"] and other["num"] == lesson["num"])
                 for other in other_module["lessons"]]))
        if course.get("project"):
            groups.append(("Course project",
                           [("P", course["project"]["titleHtml"],
                             project_href(program, course), is_project)]))
        if is_project:
            label = "Course Project"
        elif lesson is not None:
            label = "Lesson %d" % lesson["num"]
        else:
            label = "Lessons"
        crumb_items.append(picker(label, lesson, groups, "lb-lessons",
                                  grouped=True, kind="lesson"))

    # Item stepping sits inline at the end of the breadcrumb, so there is one
    # line of controls to read rather than two groups pulling apart.
    if items:
        rows = "".join(
            '<li><a href="#%s" data-item-jump="%d"><span class="lbm-ico kind-%s">%s</span>'
            '<span class="lbm-text">%s</span>'
            '<span class="lbm-meta">%s</span></a></li>'
            % (attr(item["anchor"]), n, item["type"],
               icon(ITEM_META[item["type"]]["icon"]), item["titleHtml"],
               html_escape("%d min" % item["durationMin"] if item["durationMin"] else ""))
            for n, item in enumerate(items))
        crumb_items.append(f"""<li class="lb-crumb lb-items">
  <button type="button" class="lb-step" data-item-step="-1" aria-label="Previous item" disabled>{icon('arrow-left')}</button>
  <div class="lb-pick lb-itempick">
    <button type="button" class="lb-pick-btn" aria-expanded="false" aria-controls="lb-items"
            aria-label="Jump to an item in this lesson">
      <span class="lb-pick-label"><span class="lbp-wide">Item </span><b data-item-current>1</b><span class="lbp-wide"> of </span><span class="lbp-narrow">/</span>{len(items)}</span>{icon('chevron', 'ico lb-caret')}
    </button>
    <div class="lb-menu lb-menu--items" id="lb-items" hidden><ul>{rows}</ul></div>
  </div>
  <button type="button" class="lb-step" data-item-step="1" aria-label="Next item">{icon('arrow-right')}</button>
</li>""")

    total = course["itemCount"]
    return f"""<div class="learnbar" id="learnbar" data-scope="{attr(scope or '')}">
  <div class="lb-program">
    <a class="lb-program-inner" href="{attr(program_href(program))}">
      {icon('mark', 'lb-program-mark')}<span>{html_escape(program['title'])}</span>
    </a>
  </div>
  <div class="learnbar-inner">
    <nav class="lb-crumbs" aria-label="Breadcrumb"><ol>{''.join(crumb_items)}</ol></nav>
    <div class="lb-progress">
      <span class="bar"><span data-progress-bar-for="c{course['num']}" data-item-count="{total}"></span></span>
      <span class="lb-pct">
        <span data-progress-text-for="c{course['num']}" data-item-count="{total}">0%</span>
        of Course {course['num']} complete
      </span>
    </div>
  </div>
</div>"""


def pager(stops, index):
    prev_stop = stops[index - 1] if index > 0 else None
    next_stop = stops[index + 1] if index + 1 < len(stops) else None
    parts = []
    if prev_stop:
        parts.append(
            '<a class="pager-link pager-prev" href="%s" rel="prev">%s'
            '<span class="pager-text"><span class="pager-dir">Previous</span>'
            '<span class="pager-title">%s</span></span></a>'
            % (attr(prev_stop["href"]), icon("arrow-left"), prev_stop["titleHtml"]))
    else:
        parts.append("<span></span>")
    if next_stop:
        parts.append(
            '<a class="pager-link pager-next" href="%s" rel="next">'
            '<span class="pager-text"><span class="pager-dir">Next — %s</span>'
            '<span class="pager-title">%s</span></span>%s</a>'
            % (attr(next_stop["href"]), html_escape(next_stop["label"]),
               next_stop["titleHtml"], icon("arrow-right")))
    else:
        parts.append("<span></span>")
    return '<nav class="pager" aria-label="Lesson navigation">%s</nav>' % "".join(parts)


def seal(site, program, size="md", link=True):
    """The vetting seal.

    Programs are published before expert review has finished, so every page
    says which state it is in. The seal is a link to the explanation rather
    than a decoration a learner has to guess at.
    """
    key = program.get("status", "in-progress")
    meta = site.get("statuses", {}).get(key)
    if not meta:
        return ""
    ico = "seal-check" if key == "vetted" else "seal-progress"
    inner = (
        '<span class="seal-ring">%s</span>'
        '<span class="seal-words"><span class="seal-kicker">Knowledge InSight</span>'
        '<span class="seal-label">%s</span></span>'
        % (icon(ico, "ico seal-ico"), html_escape(meta["label"])))
    classes = "seal seal--%s seal--%s" % (key, size)
    if link:
        return ('<a class="%s" href="%sstatus/" title="%s">%s</a>'
                % (classes, program_href(program), attr(meta["blurb"]), inner))
    return '<span class="%s" title="%s">%s</span>' % (classes, attr(meta["blurb"]), inner)


def vetting_panel(site, program, compact=False, scope="", where=""):
    """Guidance on what and how to vet, plus the feedback link when configured."""
    key = program.get("status", "in-progress")
    meta = site.get("statuses", {}).get(key, {})
    if key != "in-progress":
        return ""

    if compact:
        report = feedback_cta(meta, small=True, label="Report an issue on this page",
                              loc=scope or "", where=where or "")
        return f"""<aside class="vet-strip">
  {seal(site, program, size='sm')}
  <p>{html_escape(meta.get('blurb', ''))}
     <a href="{attr(program_href(program))}status/">What this means and how to help</a>.</p>
  {report}
</aside>"""

    points = "".join("<li>%s</li>" % p for p in meta.get("helpPoints", []))
    return f"""<section class="section vetting" id="vetting">
  <div class="vet-head">
    {seal(site, program, size='lg', link=False)}
    <div>
      <h2 class="section-head">{html_escape(meta.get('helpHeading', 'Help us vet this program'))}</h2>
      <p class="section-lede">{html_escape(meta.get('helpLede', ''))}</p>
    </div>
  </div>
  <ul class="vet-points">{points}</ul>
  {feedback_cta(meta)}
</section>"""


def feedback_attrs(meta, loc="", where=""):
    """Data attributes that let feedback.js prefill the form.

    The field ids come from a Google Form prefill link (Send > Get pre-filled
    link) and are all optional: with none set the link still opens the form,
    it just arrives empty.

    `loc` is the stable location id, e.g. c1.m1.l2.i7. It is deliberately not
    a title: titles get edited, and the id is what makes a report sortable in
    the responses sheet months later.
    """
    bits = ['data-feedback-link']
    for key, name in (("feedbackPageField", "data-field-page"),
                      ("feedbackTitleField", "data-field-where"),
                      ("feedbackLocationField", "data-field-loc")):
        value = (meta.get(key) or "").strip()
        if value:
            bits.append('%s="%s"' % (name, attr(value)))
    if loc:
        bits.append('data-loc="%s"' % attr(loc))
    if where:
        bits.append('data-where="%s"' % attr(where))
    return " ".join(bits)


def feedback_cta(meta, small=False, label=None, loc="", where=""):
    """Renders the feedback button once a form URL is configured, and an honest
    placeholder until then."""
    url = (meta.get("feedbackUrl") or "").strip()
    label = label or meta.get("feedbackLabel", "Report an issue")
    if not url:
        if small:
            return ""
        return ('<p class="vet-pending">%s</p>'
                % html_escape(meta.get("feedbackPending", "")))
    cls = "btn btn-small" if small else "btn btn-primary"
    anchor = ('<a class="%s" href="%s" target="_blank" rel="noopener" %s>%s<span>%s</span></a>'
              % (cls, attr(url), feedback_attrs(meta, loc, where), icon("external"),
                 html_escape(label)))
    return anchor if small else '<p class="cta-row">%s</p>' % anchor


def item_feedback(meta, iid, where):
    """A quiet per-item report link.

    A report that names the item is worth far more than one that names the
    page, and the learner should not have to describe where they were. Nothing
    renders until a form URL is configured, so the pages stay clean until then.
    """
    if not (meta.get("feedbackUrl") or "").strip():
        return ""
    return ('<p class="item-report"><a class="item-report-link" href="%s" '
            'target="_blank" rel="noopener" %s>%s<span>Report an issue with this item</span></a></p>'
            % (attr(meta["feedbackUrl"]), feedback_attrs(meta, iid, where), icon("external")))


def objectives_block(objectives, heading="What you will be able to do"):
    if not objectives:
        return ""
    lis = "".join("<li>%s</li>" % o for o in objectives)
    return ('<section class="objectives"><h2 class="objectives-head">%s</h2><ul>%s</ul></section>'
            % (html_escape(heading), lis))


# ==========================================================================
# Item rendering
# ==========================================================================

def kind_label(item):
    meta = ITEM_META[item["type"]]
    label = meta["label"]
    if item["type"] == READING and item.get("subtype") == "guided":
        label = "Guided Reading"
    return label, meta["icon"]


def lesson_contents(items, scope):
    """A collapsed contents list in the lesson header.

    The sticky bar handles jumping while reading; this is for orienting before
    you start, so it stays out of the way until asked for.
    """
    rows = []
    for index, item in enumerate(items):
        label, ico = kind_label(item)
        duration = "%d min" % item["durationMin"] if item["durationMin"] else ""
        rows.append(
            '<li class="lc-row lc-%s"><a href="#%s">'
            '<span class="lc-ico">%s</span>'
            '<span class="lc-text"><span class="lc-kind">%s%s</span>'
            '<span class="lc-name">%s</span></span>'
            '<span class="lc-min">%s</span>'
            '%s</a></li>'
            % (item["type"], attr(item["anchor"]), icon(ico), html_escape(label),
               ' &middot; optional' if item["optional"] else "",
               item["titleHtml"], html_escape(duration),
               progress_ring(item_id(scope, index), 1, "Item status")))
    return f"""<details class="lesson-contents">
  <summary>{icon('list')}<span>Contents of this lesson</span><span class="lc-count">{plural(len(items), 'item')}</span>{icon('chevron', 'ico lc-caret')}</summary>
  <ol class="lc-list">{''.join(rows)}</ol>
</details>"""


def render_item(program, item, scope, index, where="", status_meta=None):
    label, ico = kind_label(item)
    iid = item_id(scope, index)
    bits = []

    duration = ""
    if item["durationMin"]:
        duration = '<span class="item-time">%s %d min</span>' % (icon("clock"), item["durationMin"])
    optional = '<span class="tag tag-optional">Optional</span>' if item["optional"] else ""

    bits.append(f"""<header class="item-head">
  <p class="item-kind">
    <span class="kind-chip kind-{item['type']}">{icon(ico)}{html_escape(label)}</span>
    {duration}{optional}
  </p>
  <h2 class="item-title">{item["titleHtml"]}</h2>
  <button class="item-done" type="button" data-done-for="{attr(iid)}" aria-pressed="false">
    {icon('check')}<span class="done-label">Mark done</span>
  </button>
</header>""")

    if item["type"] == DIALOGUE:
        bits.append('<div class="prose">%s</div>' % item["introHtml"])
        bits.append(dialogue_block(item, iid))
    elif item["type"] in (KNOWLEDGE_CHECK, GRADED_QUIZ):
        bits.append('<div class="prose">%s</div>' % item["quiz"]["overviewHtml"])
        bits.append(quiz_block(program, item, iid))
    else:
        bits.append('<div class="prose">%s</div>' % item["bodyHtml"])
        if item["type"] in (JOURNAL, ASSIGNMENT):
            bits.append(writing_actions(item, iid))

    if status_meta:
        bits.append(item_feedback(status_meta, iid,
                                  "%s - Item %d: %s" % (where, index + 1, item["title"])))

    return ('<article class="item item--%s%s" id="%s" data-item-id="%s">%s</article>'
            % (item["type"], " is-optional" if item["optional"] else "",
               attr(item["anchor"]), attr(iid), "".join(bits)))


# Only assistants that actually accept a prompt through a link. Gemini has no
# such parameter, so offering a button for it would do nothing; the copy button
# covers it, and every other assistant, instead.
ASSISTANTS = [
    ("claude", "Claude"),
    ("chatgpt", "ChatGPT"),
]


def dialogue_block(item, iid):
    """The prompt lives once, in the <pre>. Every button reads it from there and
    builds its own URL, so a change to any link format is a one-line change in
    dialogue.js rather than an edit to 38 markdown files."""
    buttons = "".join(
        '<a class="btn btn-assistant btn-%s" data-provider="%s" href="#" target="_blank" rel="noopener">'
        '%s<span>Open in %s</span></a>' % (key, key, icon("dialogue"), html_escape(label))
        for key, label in ASSISTANTS)

    return f"""<div class="dialogue" data-dialogue>
  <p class="dialogue-lead">Run this conversation in whichever assistant you already use:</p>
  <div class="dialogue-actions">
    {buttons}
  </div>
  <div class="dialogue-secondary">
    <a class="btn btn-small btn-quiet" data-provider="claude-app" href="#">Claude desktop app</a>
    <button class="btn btn-small" type="button" data-copy-prompt>{icon('copy')}<span>Copy prompt</span></button>
  </div>
  <p class="dialogue-note" data-dialogue-status role="status">
    To use another LLM, simply copy and paste the prompt into its chat window.
  </p>
  <details class="prompt-reveal">
    <summary>Show the full prompt <span class="muted">(it lists misreadings to watch for, so skip it if you would rather come to the conversation fresh)</span></summary>
    <pre data-prompt-text>{html_escape(item['prompt'])}</pre>
  </details>
</div>"""


def writing_actions(item, iid):
    return f"""<div class="writing-actions">
  <button class="btn" type="button" data-copy-item="{attr(iid)}">{icon('copy')}<span>Copy this prompt</span></button>
  <p class="muted writing-note">Nothing is uploaded. Write in your own notebook or document and keep it.</p>
</div>"""


def quiz_block(program, item, iid):
    quiz = item["quiz"]
    kind = item["type"]
    forms = quiz["forms"]
    count = len(forms[0]) if forms else 0
    src = "/content/%s/quizzes/%s.json" % (program["id"], iid)
    if kind == GRADED_QUIZ:
        note = ('<p class="quiz-meta">%s questions · target score %d%% · %d forms, '
                'rotated on each attempt</p>' % (count, quiz["passPercent"], len(forms)))
        cta = "Start the graded quiz"
    else:
        note = '<p class="quiz-meta">%s questions · ungraded · retry as often as you like</p>' % count
        cta = "Start the knowledge check"
    return f"""<div class="quiz" data-quiz data-quiz-src="{attr(src)}" data-quiz-id="{attr(iid)}" data-quiz-kind="{attr(kind)}">
  {note}
  <div class="quiz-launch">
    <button class="btn btn-primary" type="button" data-quiz-start>{icon('quiz')}<span>{cta}</span></button>
    <span class="quiz-best" data-quiz-best hidden></span>
  </div>
  <div class="quiz-mount" data-quiz-mount hidden></div>
  <noscript><p class="muted">This check needs JavaScript. The material it covers is in the readings above.</p></noscript>
</div>"""


# ==========================================================================
# Pages
# ==========================================================================

def build_lesson_page(site, program, course, module, lesson, stops, index, scope, is_project=False):
    items = lesson["items"]
    total = item_minutes(items)
    required = item_minutes(items, include_optional=False)

    if is_project:
        eyebrow = "Course %d · Course Project" % course["num"]
        heading_kicker = "Course Project"
    else:
        eyebrow = "Module %d · Lesson %d" % (module["num"], lesson["num"])
        crumb = [(program["title"], program_href(program)),
                 ("Course %d" % course["num"], course_href(program, course)),
                 ("Module %d" % module["num"], module_href(program, course, module)),
                 ("Lesson %d" % lesson["num"], None)]
        heading_kicker = eyebrow

    meta_bits = [plural(len(items), "item")]
    if total:
        meta_bits.append("%s total" % fmt_minutes(total))
    if total != required:
        meta_bits.append("%s without the optional journal" % fmt_minutes(required))

    status_meta = site.get("statuses", {}).get(program.get("status", ""), {})
    where = ("Course %d - Course Project" % course["num"] if is_project
             else "Course %d - Module %d - Lesson %d" % (course["num"], module["num"], lesson["num"]))
    body_items = "".join(
        render_item(program, it, scope, i, where, status_meta)
        for i, it in enumerate(items))

    main = f"""<main id="main" class="learn-main">
  <header class="lesson-head">
    <p class="eyebrow">{html_escape(heading_kicker)}</p>
    <h1>{lesson["titleHtml"]}</h1>
    {f'<p class="lede">{lesson["descriptionHtml"]}</p>' if lesson.get("description") else ""}
    {objectives_block(lesson.get('objectives', []))}
    <div class="lesson-progress">
      <div class="bar"><span data-progress-bar-for="{attr(scope)}" data-item-count="{len(items)}"></span></div>
      <p class="bar-label"><span data-progress-text-for="{attr(scope)}" data-item-count="{len(items)}">0%</span> of this lesson &middot; {html_escape(' · '.join(meta_bits))}</p>
    </div>
    {lesson_contents(items, scope)}
  </header>
  {vetting_panel(site, program, compact=True, scope=scope, where=where)}
  <div class="items">{body_items}</div>
  {pager(stops, index)}
</main>"""

    body = f"""{learn_bar(site, program, course, module, lesson, scope, items=items, is_project=is_project)}
<div class="learn">{main}</div>"""

    return page(lesson["title"], body,
                description=lesson.get("description", "")[:300],
                body_class="page-lesson", site=site, program_id=program["id"],
                scripts=("progress.js", "dialogue.js", "quiz.js", "lessonnav.js", "feedback.js"))


def build_module_page(site, program, course, module, stops, index):
    lessons = module["lessons"]
    rows = []
    for lesson in lessons:
        lid = lesson_id(course, module, lesson)
        minutes = item_minutes(lesson["items"])
        kinds = {}
        for it in lesson["items"]:
            kinds[it["type"]] = kinds.get(it["type"], 0) + 1
        chips = "".join(
            '<span class="minichip" title="%s"><span class="minichip-ico">%s</span>%d</span>'
            % (attr(ITEM_META[k]["label"]), icon(ITEM_META[k]["icon"]), v)
            for k, v in kinds.items())
        rows.append(f"""<li class="lesson-card">
  <a href="{attr(lesson_href(program, course, module, lesson))}">
    <span class="lc-num">Lesson {lesson['num']}</span>
    <span class="lc-title">{lesson["titleHtml"]}</span>
    <span class="lc-desc">{html_escape(clip(lesson.get("description"), 180))}</span>
    <span class="lc-foot">{chips}<span class="lc-time">{icon('clock')}{fmt_minutes(minutes)}</span>
    {progress_ring(lid, len(lesson['items']), 'Lesson progress')}</span>
  </a></li>""")

    total_items = sum(len(l["items"]) for l in lessons)
    main = f"""<main id="main" class="learn-main">
  <header class="lesson-head">
    <p class="eyebrow">Course {course['num']} · Module {module['num']}</p>
    <h1>{module["titleHtml"]}</h1>
    {f'<p class="lede">{module["descriptionHtml"]}</p>' if module.get("description") else ""}
    {objectives_block(module.get('objectives', []), 'Module objectives')}
    <p class="lesson-meta">{plural(len(lessons), 'lesson')} · {plural(total_items, 'item')} · {fmt_minutes(item_minutes([i for l in lessons for i in l['items']]))}</p>
  </header>
  <section class="section">
    <h2 class="section-head">Lessons</h2>
    <ol class="lesson-cards">{''.join(rows)}</ol>
  </section>
  {f'<section class="section further"><h2 class="section-head">Further reading</h2><div class="prose">{module["furtherReadingHtml"]}</div></section>' if module.get('furtherReadingHtml') else ''}
  {pager(stops, index)}
</main>"""

    body = f"""{learn_bar(site, program, course, module)}
<div class="learn">{main}</div>"""
    return page(module["title"], body, description=module.get("description", "")[:300],
                body_class="page-module", site=site, program_id=program["id"],
                scripts=("progress.js", "lessonnav.js", "feedback.js"))


def build_course_page(site, program, course, stops, index):
    module_rows = []
    for module in course["modules"]:
        lessons = "".join(
            '<li><a href="%s"><span class="ml-num">%d.%d</span>'
            '<span class="ml-title">%s</span>'
            '<span class="ml-time">%s</span>%s</a></li>'
            % (attr(lesson_href(program, course, module, lesson)),
               module["num"], lesson["num"], lesson["titleHtml"],
               fmt_minutes(item_minutes(lesson["items"])),
               progress_ring(lesson_id(course, module, lesson), len(lesson["items"]), "Lesson progress"))
            for lesson in module["lessons"])
        module_rows.append(f"""<li class="module-block">
  <details open>
    <summary>
      <span class="mb-num">Module {module['num']}</span>
      <span class="mb-title">{module["titleHtml"]}</span>
      <span class="mb-meta">{plural(len(module['lessons']), 'lesson')}</span>
      {icon('chevron', 'ico mb-caret')}
    </summary>
    <p class="mb-desc">{module["descriptionHtml"]}</p>
    <p class="mb-link"><a href="{attr(module_href(program, course, module))}">Module overview and further reading {icon('arrow-right')}</a></p>
    <ol class="module-lessons">{lessons}</ol>
  </details>
</li>""")

    project_card = ""
    if course.get("project"):
        proj = course["project"]
        project_card = f"""<section class="section">
  <h2 class="section-head">Course project</h2>
  <a class="project-card" href="{attr(project_href(program, course))}">
    <span class="pc-ico">{icon('assignment')}</span>
    <span class="pc-body">
      <span class="pc-title">{proj["titleHtml"]}</span>
      <span class="pc-desc">{html_escape(clip(proj.get("description"), 260))}</span>
      <span class="pc-meta">{plural(len(proj['items']), 'item')} · {fmt_minutes(item_minutes(proj['items']))}</span>
    </span>
    <span class="pc-go">{icon('arrow-right')}</span>
  </a>
</section>"""

    outcomes = "".join("<li>%s</li>" % o for o in course["outcomes"])
    first = course["modules"][0]["lessons"][0]
    start_href = lesson_href(program, course, course["modules"][0], first)

    main = f"""<main id="main" class="learn-main">
  <header class="course-head">
    <p class="eyebrow">Course {course['num']} of {len(program['courses'])}</p>
    <h1>{course["titleHtml"]}</h1>
    <div class="prose course-desc">{course['descriptionHtml']}</div>
    <p class="lesson-meta">{plural(len(course['modules']), 'module')} · {plural(course['lessonCount'], 'lesson')} · {plural(course['itemCount'], 'item')} · {fmt_minutes(course['minutes'])}</p>
    <p class="cta-row">
      <a class="btn btn-primary btn-lg" href="{attr(start_href)}" data-resume-for="c{course['num']}">{icon('arrow-right')}<span>Start Course {course['num']}</span></a>
    </p>
  </header>
  {f'<section class="section audience"><h2 class="section-head">Who this is for</h2><p>{html_escape(course["audience"])}</p></section>' if course.get('audience') else ''}
  <section class="section">
    <h2 class="section-head">What you will learn</h2>
    <ul class="outcomes">{outcomes}</ul>
  </section>
  {vetting_panel(site, program, compact=True)}
  <section class="section">
    <h2 class="section-head">Contents</h2>
    <ol class="module-blocks">{''.join(module_rows)}</ol>
  </section>
  {project_card}
  {pager(stops, index)}
</main>"""

    body = f"""{learn_bar(site, program, course)}
<div class="learn">{main}</div>"""
    return page(course["title"], body, description=strip_md(course["descriptionHtml"])[:280],
                body_class="page-course", site=site, program_id=program["id"],
                scripts=("progress.js", "lessonnav.js", "feedback.js"))


def build_program_page(site, program):
    cards = []
    for course in program["courses"]:
        cards.append(f"""<li class="course-card">
  <a href="{attr(course_href(program, course))}">
    <span class="cc-num">Course {course['num']}</span>
    <span class="cc-title">{course["titleHtml"]}</span>
    <span class="cc-desc">{html_escape(clip(strip_md(course["descriptionHtml"]), 200))}</span>
    <span class="cc-meta">
      <span>{plural(len(course['modules']), 'module')}</span>
      <span>{plural(course['lessonCount'], 'lesson')}</span>
      <span>{fmt_minutes(course['minutes'])}</span>
    </span>
    <span class="cc-bar"><span class="bar"><span data-progress-bar-for="c{course['num']}" data-item-count="{course['itemCount']}"></span></span>
      <span class="cc-pct" data-progress-text-for="c{course['num']}" data-item-count="{course['itemCount']}">0%</span></span>
  </a></li>""")

    outcomes = "".join("<li>%s</li>" % html_escape(o) for o in program["outcomes"])
    first_course = program["courses"][0]
    first_lesson = first_course["modules"][0]["lessons"][0]
    start = lesson_href(program, first_course, first_course["modules"][0], first_lesson)

    rhythm = [
        (READING, "A motivating reading", "Why the question matters, in three minutes."),
        (READING, "Four concept readings", "The ideas themselves, one at a time."),
        (READING, "A guided close reading", "One primary passage, walked through line by line."),
        (DIALOGUE, "A Guided Conversation", "A structured conversation you run in your own AI account."),
        (JOURNAL, "An optional journal entry", "A writing prompt you answer in your own notebook."),
        (KNOWLEDGE_CHECK, "A knowledge check", "Five questions, ungraded, retry as often as you like."),
    ]
    rhythm_html = "".join(
        '<li><span class="rh-ico kind-%s">%s</span><span class="rh-body">'
        '<strong>%s</strong><span>%s</span></span></li>'
        % (kind, icon(ITEM_META[kind]["icon"]), html_escape(title), html_escape(desc))
        for kind, title, desc in rhythm)

    desc_html = "".join("<p>%s</p>" % html_escape(para)
                        for para in program["description"].split("\n\n"))

    main = f"""<main id="main" class="prog">
  <header class="prog-hero">
    <div class="prog-hero-inner">
      {crumbs([('Programs', '/#programs'), (program['title'], None)])}
      <div class="prog-hero-top">
        <div class="prog-hero-words">
          <p class="eyebrow">{html_escape(program['level'])} &middot; {html_escape(program['format'])} &middot; Open access</p>
          <h1>{html_escape(program['title'])}</h1>
          <p class="prog-sub">{html_escape(program['subtitle'])}</p>
        </div>
        {seal(site, program, size='lg')}
      </div>
      <p class="prog-stats">
        <span>{plural(len(program['courses']), 'course')}</span>
        <span>{plural(program['moduleCount'], 'module')}</span>
        <span>{plural(program['lessonCount'], 'lesson')}</span>
        <span>{fmt_minutes(program['minutes'])} of material</span>
      </p>
      <p class="cta-row">
        <a class="btn btn-primary btn-lg" href="{attr(start)}" data-resume-for="program">{icon('arrow-right')}<span>Start the program</span></a>
        <a class="btn btn-onhero" href="{attr(program_href(program))}map/">{icon('map')}<span>See the whole map</span></a>
      </p>
    </div>
  </header>

  <div class="prog-body">
    <section class="section">
      <h2 class="section-head">About this program</h2>
      <div class="prose prog-about">{desc_html}</div>
    </section>

    <section class="section">
      <h2 class="section-head">What you will be able to do</h2>
      <ul class="outcomes">{outcomes}</ul>
    </section>

    <section class="section">
      <h2 class="section-head">{html_escape(site.get('progressHeading', 'How to progress through a program'))}</h2>
      <p class="section-lede">{html_escape(site.get('progressLede', ''))}</p>
      <ol class="rhythm">{rhythm_html}</ol>
      <p class="muted">The last lesson of each module adds a graded quiz with a target score of 80 percent.</p>
    </section>

    <section class="section" id="courses">
      <h2 class="section-head">Courses</h2>
      <ol class="course-cards">{''.join(cards)}</ol>
    </section>

    <section class="section">
      <h2 class="section-head">Who this is for</h2>
      <p class="measure">{html_escape(program['audience'])}</p>
    </section>

    {vetting_panel(site, program)}
  </div>
</main>"""
    return page(program["title"], main, description=program["summary"],
                body_class="page-program", site=site, program_id=program["id"],
                scripts=("progress.js", "feedback.js"))


def build_status_page(site, program):
    """A page the seal links to: what the status means, and how to help."""
    key = program.get("status", "in-progress")
    meta = site.get("statuses", {}).get(key, {})
    ai = site.get("ai", {})

    vetting = "".join("<p>%s</p>" % para for para in ai.get("vetting", []))
    points = "".join("<li>%s</li>" % point for point in meta.get("helpPoints", []))

    main = f"""<main id="main">
  <header class="page-head wrap">
    {crumbs([(program['title'], program_href(program)), ('Vetting status', None)])}
    <div class="status-head">
      {seal(site, program, size='xl', link=False)}
      <div>
        <p class="eyebrow">{html_escape(program['title'])}</p>
        <h1>Vetting status</h1>
        <p class="lede">{html_escape(meta.get('blurb', ''))}</p>
      </div>
    </div>
  </header>
  <div class="wrap narrow">
    <section class="section">
      <h2 class="section-head">What the seals mean</h2>
      <div class="prose">{vetting}</div>
    </section>
    <section class="section">
      <h2 class="section-head">{html_escape(meta.get('helpHeading', 'Help us vet this program'))}</h2>
      <p class="section-lede">{html_escape(meta.get('helpLede', ''))}</p>
      <ul class="vet-points">{points}</ul>
      {feedback_cta(meta)}
    </section>
    <section class="section">
      <p class="cta-row">
        <a class="btn" href="{attr(program_href(program))}">{icon('arrow-left')}<span>Back to the program</span></a>
        <a class="btn btn-quiet" href="/about.html#ai">{icon('dialogue')}<span>How we use AI</span></a>
      </p>
    </section>
  </div>
</main>"""
    return page("Vetting status", main,
                description=meta.get("blurb", ""), body_class="page-status",
                site=site, program_id=program["id"], scripts=("feedback.js",))


def build_map_page(site, program):
    """The whole program as one flowing outline.

    A multi-column grid packed four modules abreast and left lesson titles
    fighting for width. An indented outline reads the way a syllabus does, and
    a single narrow column keeps the line length comfortable rather than
    stretching rows across a wide screen.
    """
    blocks = []
    for course in program["courses"]:
        modules = []
        for module in course["modules"]:
            lessons = "".join(
                '<li class="mo-lesson"><a href="%s">'
                '<span class="mo-num">%d.%d</span>'
                '<span class="mo-title">%s</span>'
                '<span class="mo-dots" aria-hidden="true"></span>'
                '<span class="mo-time">%s</span>%s</a></li>'
                % (attr(lesson_href(program, course, module, lesson)),
                   module["num"], lesson["num"], lesson["titleHtml"],
                   fmt_minutes(item_minutes(lesson["items"])),
                   progress_ring(lesson_id(course, module, lesson),
                                 len(lesson["items"]), "Lesson progress"))
                for lesson in module["lessons"])
            modules.append(f"""<li class="mo-module">
  <h3 class="mo-module-head">
    <a href="{attr(module_href(program, course, module))}">
      <span class="mo-mnum">Module {module['num']}</span>
      <span class="mo-mtitle">{module['titleHtml']}</span>
    </a>
    <span class="mo-mmeta">{plural(len(module['lessons']), 'lesson')}</span>
  </h3>
  <ol class="mo-lessons">{lessons}</ol>
</li>""")

        project = ""
        if course.get("project"):
            project = (
                '<li class="mo-module mo-project"><h3 class="mo-module-head">'
                '<a href="%s"><span class="mo-mnum">%sProject</span>'
                '<span class="mo-mtitle">%s</span></a>'
                '<span class="mo-mmeta">%s</span></h3>'
                '<ol class="mo-lessons"><li class="mo-lesson"><a href="%s">'
                '<span class="mo-num">&nbsp;</span><span class="mo-title">%s</span>'
                '<span class="mo-dots" aria-hidden="true"></span>'
                '<span class="mo-time">%s</span>%s</a></li></ol></li>'
                % (attr(project_href(program, course)), icon("assignment"),
                   course["project"]["titleHtml"],
                   plural(len(course["project"]["items"]), "item"),
                   attr(project_href(program, course)),
                   course["project"]["titleHtml"],
                   fmt_minutes(item_minutes(course["project"]["items"])),
                   progress_ring(project_id(course), len(course["project"]["items"]),
                                 "Project progress")))

        blocks.append(f"""<section class="mo-course">
  <header class="mo-course-head">
    <h2><a href="{attr(course_href(program, course))}">
      <span class="mo-ckicker">Course {course['num']}</span>
      <span>{course['titleHtml']}</span></a></h2>
    <p class="mo-cmeta">{plural(len(course['modules']), 'module')} &middot; {plural(course['lessonCount'], 'lesson')} &middot; {fmt_minutes(course['minutes'])}</p>
    <div class="mo-cbar">
      <span class="bar"><span data-progress-bar-for="c{course['num']}" data-item-count="{course['itemCount']}"></span></span>
      <span class="mo-cpct" data-progress-text-for="c{course['num']}" data-item-count="{course['itemCount']}">0%</span>
    </div>
  </header>
  <ol class="mo-modules">{''.join(modules)}{project}</ol>
</section>""")

    main = f"""<main id="main" class="mapping">
  <header class="page-head">
    {crumbs([(program['title'], program_href(program)), ('Program map', None)])}
    <h1>Program map</h1>
    <p class="lede">Every course, module, and lesson in {html_escape(program['title'])}, in order.
      Jump anywhere: nothing is locked, and the sequence is a suggestion rather than a gate.</p>
    <p class="cta-row"><a class="btn" href="{attr(program_href(program))}">{icon('arrow-left')}<span>Program overview</span></a></p>
  </header>
  {''.join(blocks)}
</main>"""
    return page("Program map", main,
                description="Every course, module, and lesson in %s on one page." % program["title"],
                body_class="page-map", site=site, program_id=program["id"],
                scripts=("progress.js",))


def placeholder_cards(site):
    """Generic "more coming" cards that sit in the Programs grid.

    Deliberately unnamed: they show how the grid will look once there is more
    than one program, without promising a particular one.
    """
    count = int(site.get("placeholderCards") or 0)
    if count < 1:
        return ""
    return "".join(f"""<li class="splash-card splash-card--soon" aria-hidden="true">
  <span class="sc-soon-mark">{icon('sparkle-small')}</span>
  <span class="sc-soon-title">{html_escape(site.get('placeholderText', 'Another program is on the way.'))}</span>
  <span class="sc-soon-sub">{html_escape(site.get('placeholderSub', ''))}</span>
</li>""" for _ in range(count))


def build_splash(site, programs):
    cards = []
    for program in programs:
        cards.append(f"""<li class="splash-card">
  <a href="{attr(program_href(program))}">
    <span class="sc-top">
      <span class="sc-eyebrow">{html_escape(program['level'])} &middot; {html_escape(program['format'])}</span>
      {seal(site, program, size='sm', link=False)}
    </span>
    <span class="sc-title">{html_escape(program['title'])}</span>
    <span class="sc-sub">{html_escape(program['subtitle'])}</span>
    <span class="sc-meta">
      <span>{plural(len(program['courses']), 'course')}</span>
      <span>{plural(program['lessonCount'], 'lesson')}</span>
      <span>{fmt_minutes(program['minutes'])}</span>
    </span>
    <span class="sc-go">Open the program {icon('arrow-right')}</span>
  </a></li>""")

    principles = "".join(
        '<li><h3>%s</h3><p>%s</p></li>' % (html_escape(p["title"]), html_escape(p["body"]))
        for p in site["principles"])

    main = f"""<main id="main">
  <section class="hero">
    <picture class="hero-img">
      <source media="(max-width: 480px)" srcset="/assets/img/hero-books-blue-480.jpg">
      <source media="(max-width: 900px)" srcset="/assets/img/hero-books-blue-800.jpg">
      <source media="(max-width: 1400px)" srcset="/assets/img/hero-books-blue-1280.jpg">
      <img src="/assets/img/hero-books-blue-1920.jpg" alt="" width="1920" height="1280" fetchpriority="high">
    </picture>
    <div class="hero-inner">
      <p class="hero-eyebrow">{html_escape(site['org'])}</p>
      <h1>{html_escape(site['splashHeadline'])}</h1>
      <p class="hero-lede">{html_escape(site['splashLede'])}</p>
      <p class="cta-row">
        <a class="btn btn-primary btn-lg" href="#programs">{icon('arrow-right')}<span>Browse programs</span></a>
        <a class="btn btn-onhero" href="/about.html">{icon('list')}<span>How it works</span></a>
      </p>
    </div>
  </section>

  <section class="section band" id="programs">
    <div class="wrap">
      <h2 class="section-head">Programs</h2>
      <p class="section-lede">Free, self-paced, and open to anyone. No sign-up, no submission, no grade.</p>
      <ol class="splash-cards">{''.join(cards)}{placeholder_cards(site)}</ol>
    </div>
  </section>

  <section class="section">
    <div class="wrap">
      <h2 class="section-head">{html_escape(site.get('progressHeading', 'How to progress through a program'))}</h2>
      <p class="section-lede">{html_escape(site.get('progressLede', ''))}</p>
      <ul class="principles">{principles}</ul>
    </div>
  </section>
</main>"""
    return page(site["org"], main, description=site["tagline"],
                body_class="page-splash", site=site, scripts=("progress.js", "feedback.js"))


def build_about(site, programs):
    paragraphs = "".join("<p>%s</p>" % html_escape(para) for para in site["about"])
    aside = site.get("aboutAside", "")
    ai = site.get("ai", {})
    bio = site.get("bio", {})

    ai_intro = "".join("<p>%s</p>" % para for para in ai.get("intro", []))
    ai_vetting = "".join("<p>%s</p>" % para for para in ai.get("vetting", []))
    ai_convo = "".join("<p>%s</p>" % para for para in ai.get("conversations", []))

    seals = "".join(
        '<li>%s<p>%s</p></li>'
        % (seal(site, {"id": p["id"], "status": key}, size="md", link=False),
           html_escape(site["statuses"][key]["blurb"]))
        for key, p in [(k, programs[0]) for k in ("vetted", "in-progress")]
        if key in site.get("statuses", {}))

    main = f"""<main id="main">
  <section class="hero hero--about">
    <picture class="hero-img">
      <source media="(max-width: 480px)" srcset="/assets/img/hero-books-blue-480.jpg">
      <source media="(max-width: 900px)" srcset="/assets/img/hero-books-blue-800.jpg">
      <source media="(max-width: 1400px)" srcset="/assets/img/hero-books-blue-1280.jpg">
      <img src="/assets/img/hero-books-blue-1920.jpg" alt="" width="1920" height="1280">
    </picture>
    <div class="hero-inner">
      <p class="hero-eyebrow">About</p>
      <h1>{html_escape(site['org'])}</h1>
      <p class="hero-lede">{html_escape(site['tagline'])}</p>
    </div>
  </section>

  <div class="wrap narrow">
    <section class="section">
      <div class="prose">{paragraphs}</div>
    </section>

    <section class="section" id="ai">
      <h2 class="section-head">{html_escape(ai.get('heading', 'AI in education'))}</h2>
      <div class="prose">{ai_intro}</div>
      <h3 class="sub-head">Vetting, and what the seals mean</h3>
      <div class="prose">{ai_vetting}</div>
      <ul class="seal-key">{seals}</ul>
      <h3 class="sub-head">Guided Conversations</h3>
      <div class="prose">{ai_convo}</div>
    </section>

    <section class="section">
      <h2 class="section-head">What we store</h2>
      <div class="prose">
        <p>Nothing leaves your browser. Marking an item done, and any quiz score you record,
           is saved in this browser's local storage so the site can show you where you left off.
           It is not synced, not shared, and not visible to us. Clearing your browser data clears it.</p>
        <p>The Guided Conversations open in your own AI account and count against your own plan.
           We never see those conversations.</p>
      </div>
    </section>

    <section class="section">
      <h2 class="section-head">Who makes this</h2>
      <div class="bio">
        <img class="bio-photo" src="{attr(bio.get('image', ''))}" alt="{attr(bio.get('alt', ''))}"
             width="160" height="160" loading="lazy">
        <div class="bio-body">
          <p class="bio-name">{html_escape(bio.get('name', ''))}</p>
          <p>{html_escape(bio.get('text', ''))}</p>
          {f'<p class="aside-note">{html_escape(aside)}</p>' if aside else ''}
        </div>
      </div>
    </section>
  </div>
</main>"""
    return page("About", main, description=site["tagline"],
                body_class="page-about", site=site)


# ==========================================================================
# Build
# ==========================================================================

def enrich(program):
    """Add the counts and totals the templates and the nav tree both need."""
    program["moduleCount"] = 0
    program["lessonCount"] = 0
    program["itemCount"] = 0
    program["minutes"] = 0
    for course in program["courses"]:
        course["lessonCount"] = sum(len(m["lessons"]) for m in course["modules"])
        items = [i for m in course["modules"] for l in m["lessons"] for i in l["items"]]
        if course.get("project"):
            items += course["project"]["items"]
        course["itemCount"] = len(items)
        course["minutes"] = item_minutes(items)
        program["moduleCount"] += len(course["modules"])
        program["lessonCount"] += course["lessonCount"]
        program["itemCount"] += course["itemCount"]
        program["minutes"] += course["minutes"]
    return program


def nav_tree(program):
    """The compact tree the client uses for progress rollups and resume."""
    courses = []
    for course in program["courses"]:
        modules = []
        for module in course["modules"]:
            modules.append({
                "num": module["num"], "title": module["title"],
                "href": module_href(program, course, module),
                "lessons": [{
                    "num": lesson["num"], "title": lesson["title"],
                    "id": lesson_id(course, module, lesson),
                    "href": lesson_href(program, course, module, lesson),
                    "items": len(lesson["items"]),
                    "minutes": item_minutes(lesson["items"]),
                } for lesson in module["lessons"]],
            })
        entry = {
            "num": course["num"], "title": course["title"],
            "href": course_href(program, course),
            "items": course["itemCount"], "minutes": course["minutes"],
            "modules": modules,
        }
        if course.get("project"):
            entry["project"] = {
                "title": course["project"]["title"],
                "id": project_id(course),
                "href": project_href(program, course),
                "items": len(course["project"]["items"]),
            }
        courses.append(entry)
    return {
        "id": program["id"], "title": program["title"], "href": program_href(program),
        "items": program["itemCount"], "lessons": program["lessonCount"],
        "minutes": program["minutes"], "courses": courses,
    }


def build_program(site, spec, out_root):
    program = dict(spec)
    program["courses"] = []
    warnings = []

    for source in spec["sourceFiles"]:
        path = MARKDOWN / source["website"]
        if not path.exists():
            raise SystemExit("missing source file: %s" % path)
        prompts = MARKDOWN / source["prompts"] if source.get("prompts") else None
        course = parse_course(path, source["slug"], prompts, warnings.append)
        program["courses"].append(course)
    program["courses"].sort(key=lambda c: c["num"])
    enrich(program)

    stops = walk_stops(program)
    index_of = {stop["href"]: i for i, stop in enumerate(stops)}
    base = out_root / "programs" / program["id"]

    write(base / "index.html", build_program_page(site, program))
    write(base / "map" / "index.html", build_map_page(site, program))
    write(base / "status" / "index.html", build_status_page(site, program))

    quiz_dir = CONTENT / program["id"] / "quizzes"
    quiz_count = 0

    for course in program["courses"]:
        href = course_href(program, course)
        write(out_root / href.strip("/") / "index.html",
              build_course_page(site, program, course, stops, index_of[href]))

        for module in course["modules"]:
            href = module_href(program, course, module)
            write(out_root / href.strip("/") / "index.html",
                  build_module_page(site, program, course, module, stops, index_of[href]))

            for lesson in module["lessons"]:
                href = lesson_href(program, course, module, lesson)
                scope = lesson_id(course, module, lesson)
                write(out_root / href.strip("/") / "index.html",
                      build_lesson_page(site, program, course, module, lesson,
                                        stops, index_of[href], scope))
                quiz_count += emit_quizzes(lesson, scope, quiz_dir)

        if course.get("project"):
            href = project_href(program, course)
            scope = project_id(course)
            write(out_root / href.strip("/") / "index.html",
                  build_lesson_page(site, program, course, None, course["project"],
                                    stops, index_of[href], scope, is_project=True))
            quiz_count += emit_quizzes(course["project"], scope, quiz_dir)

    write(CONTENT / program["id"] / "program.json",
          json.dumps(nav_tree(program), indent=1, ensure_ascii=False))
    write(CONTENT / program["id"] / "locations.csv", locations_csv(program))

    return program, warnings, quiz_count, len(stops)


def locations_csv(program):
    """Every location id the site can report, with a readable title.

    Must cover every level, not just items: the page-level "report an issue on
    this page" link sends a lesson id such as c1.m1.l1, and a lookup table of
    item ids alone leaves those reports unresolvable in the responses sheet.

    Paste this into a second tab of the form's responses sheet and a report
    that says c3.m2.l1.i6 becomes readable with a VLOOKUP, without having to
    put titles into the form itself where they would go stale.
    """
    rows = ["id,course,module,lesson,item,type,title,url"]

    def esc(value):
        value = str(value if value is not None else "")
        if any(ch in value for ch in (",", '"', chr(10))):
            return '"%s"' % value.replace('"', '""')
        return value

    def add(ident, course_num, module_num, lesson_num, item_num, kind, title, url):
        rows.append(",".join(esc(v) for v in
                             [ident, course_num, module_num, lesson_num,
                              item_num, kind, title, url]))

    for course in program["courses"]:
        cn = course["num"]
        add("c%d" % cn, cn, "", "", "", "course", course["title"],
            course_href(program, course))

        for module in course["modules"]:
            mn = module["num"]
            add("c%d.m%d" % (cn, mn), cn, mn, "", "", "module", module["title"],
                module_href(program, course, module))

            for lesson in module["lessons"]:
                scope = lesson_id(course, module, lesson)
                href = lesson_href(program, course, module, lesson)
                add(scope, cn, mn, lesson["num"], "", "lesson", lesson["title"], href)
                for index, item in enumerate(lesson["items"]):
                    add(item_id(scope, index), cn, mn, lesson["num"], index + 1,
                        item["type"], item["title"], "%s#%s" % (href, item["anchor"]))

        if course.get("project"):
            scope = project_id(course)
            href = project_href(program, course)
            add(scope, cn, "", "project", "", "project",
                course["project"]["title"], href)
            for index, item in enumerate(course["project"]["items"]):
                add(item_id(scope, index), cn, "", "project", index + 1,
                    item["type"], item["title"], "%s#%s" % (href, item["anchor"]))

    return "\n".join(rows) + "\n"


def emit_quizzes(lesson, scope, quiz_dir):
    count = 0
    for index, item in enumerate(lesson["items"]):
        if item["type"] not in (KNOWLEDGE_CHECK, GRADED_QUIZ):
            continue
        iid = item_id(scope, index)
        payload = dict(item["quiz"])
        payload["id"] = iid
        payload["title"] = item["title"]
        write(quiz_dir / ("%s.json" % iid),
              json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        count += 1
    return count


def clean(out_root):
    for name in GENERATED_DIRS:
        target = out_root / name
        if target.exists():
            shutil.rmtree(target)
    for name in GENERATED_FILES:
        target = out_root / name
        if target.exists():
            target.unlink()
    for program_dir in CONTENT.iterdir() if CONTENT.exists() else []:
        if program_dir.is_dir():
            shutil.rmtree(program_dir)


def main():
    ap = argparse.ArgumentParser(description="Build the Knowledge InSight site.")
    ap.add_argument("--clean", action="store_true", help="remove generated output first")
    args = ap.parse_args()

    site = json.loads((CONTENT / "site.json").read_text(encoding="utf-8"))
    out_root = ROOT

    if args.clean:
        clean(out_root)

    built, all_warnings, quizzes, pages = [], [], 0, 0
    for spec in site["programs"]:
        program, warnings, quiz_count, stop_count = build_program(site, spec, out_root)
        built.append(program)
        all_warnings += warnings
        quizzes += quiz_count
        pages += stop_count + 3  # + program page + map + status

    write(out_root / "index.html", build_splash(site, built))
    write(out_root / "about.html", build_about(site, built))
    pages += 2

    print("Knowledge InSight build")
    for program in built:
        print("  program : %s" % program["title"])
        print("            %d courses, %d modules, %d lessons, %d items, %s"
              % (len(program["courses"]), program["moduleCount"], program["lessonCount"],
                 program["itemCount"], fmt_minutes(program["minutes"])))
    print("  pages   : %d" % pages)
    print("  quizzes : %d" % quizzes)
    if all_warnings:
        print("  warnings: %d" % len(all_warnings))
        for warning in all_warnings[:20]:
            print("     - %s" % warning)
    else:
        print("  warnings: none")


if __name__ == "__main__":
    main()
