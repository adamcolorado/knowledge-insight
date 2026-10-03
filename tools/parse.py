r"""
Parse the Knowledge InSight course markdown into a structured program model.

The course files are regular enough to parse from headings alone, which is what
the content brief recommends. Every structural element is a level-1 heading and
is told apart by pattern:

    # **Course 1: ...**                      course
    # **Module 1: ...**                      module
    # **Module 1 \- Lesson 1 | ...**         lesson
    # **Course Project | ...**               course project
    # **<emoji> Title (N min)**               item

The in-file Contents table is ignored: it is malformed (a three-column header
over four-cell rows) and the headings are a better source anyway.
"""

import re
import unicodedata
from pathlib import Path

from mdrender import render, inline, unescape_md, strip_md

# --------------------------------------------------------------------------
# Item types
# --------------------------------------------------------------------------

READING = "reading"
DIALOGUE = "dialogue"
JOURNAL = "journal"
KNOWLEDGE_CHECK = "knowledge-check"
GRADED_QUIZ = "graded-quiz"
ASSIGNMENT = "assignment"

ITEM_META = {
    READING:         {"label": "Reading",             "icon": "reading",    "emoji": "\U0001F4D6"},
    DIALOGUE:        {"label": "Guided Conversation", "icon": "dialogue",   "emoji": "✨"},
    JOURNAL:         {"label": "Journal",             "icon": "journal",    "emoji": "✍️"},
    KNOWLEDGE_CHECK: {"label": "Knowledge Check",     "icon": "check",      "emoji": "❓"},
    GRADED_QUIZ:     {"label": "Graded Quiz",         "icon": "quiz",       "emoji": "❓"},
    ASSIGNMENT:      {"label": "Writing Assignment",  "icon": "assignment", "emoji": "✍️"},
}

EMOJI_READING = "\U0001F4D6"
EMOJI_DIALOGUE = "✨"
EMOJI_WRITE = "✍"
EMOJI_QUIZ = "❓"

PASS_PERCENT = 80

# Repeated scaffolding in item titles. The type chip already says what the item
# is, so the prefix is dropped from the displayed title.
TITLE_NOISE = re.compile(r"^Hands-on Activity:\s*")

# --------------------------------------------------------------------------
# Heading classification
# --------------------------------------------------------------------------

RE_COURSE = re.compile(r"^Course\s+(\d+)\s*[:.]\s*(.+)$")
RE_MODULE = re.compile(r"^Module\s+(\d+)\s*:\s*(.+)$")
RE_LESSON = re.compile(r"^Module\s+(\d+)\s*-\s*Lesson\s+(\d+)\s*\|\s*(.+)$")
RE_PROJECT = re.compile(r"^Course Project\s*\|\s*(.+)$")
RE_DURATION = re.compile(r"\s*\((?:(Optional)\s*,\s*)?(\d+)\s*min\)\s*$", re.I)


def heading_text(line):
    """Strip the '# ', the wrapping bold, and the export's backslash escapes."""
    text = re.sub(r"^#+\s*", "", line.strip())
    text = text.strip()
    if text.startswith("**") and text.endswith("**") and len(text) > 4:
        text = text[2:-2]
    return unescape_md(text).strip()


def slugify(text, max_len=52):
    text = strip_md(text)
    text = re.sub(r"[‘’']", "", text)
    # Fold accents so 'Epoche' and 'Epoché' produce the same slug.
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^A-Za-z0-9]+", "-", text.lower()).strip("-")
    if len(text) <= max_len:
        return text
    cut = text[:max_len]
    if "-" in cut:
        cut = cut[:cut.rindex("-")]
    return cut.strip("-")


def lesson_slug(title):
    """Lesson titles read 'Module theme: Specific topic'. The specific half
    makes the better URL, and is how a learner refers to the lesson."""
    if ": " in title:
        head, tail = title.split(": ", 1)
        if len(head) < 44 and tail.strip():
            candidate = slugify(tail)
            if candidate:
                return candidate
    return slugify(title)


def classify_item(title):
    """Return (type, clean_title, duration_min, optional, subtype)."""
    optional = False
    duration = None
    m = RE_DURATION.search(title)
    if m:
        optional = bool(m.group(1))
        duration = int(m.group(2))
        title = title[: m.start()].strip()

    first = title[:1]
    rest = title[1:].strip()
    # Variation selectors and the like sit between the emoji and the text.
    rest = rest.lstrip("️‍").strip()

    kind, subtype = READING, None
    if first == EMOJI_READING:
        kind = READING
        if rest.startswith("Guided Close Reading") or rest.startswith("Guided Walkthrough"):
            subtype = "guided"
    elif first == EMOJI_DIALOGUE:
        kind = DIALOGUE
    elif first == EMOJI_WRITE:
        kind = JOURNAL if "Journal Entry" in rest else ASSIGNMENT
    elif first == EMOJI_QUIZ:
        kind = GRADED_QUIZ if rest.startswith("Graded Quiz") else KNOWLEDGE_CHECK
    else:
        rest = title

    clean = TITLE_NOISE.sub("", rest).strip()
    for prefix in ("Knowledge Check: ", "Graded Quiz: "):
        if clean.startswith(prefix):
            clean = clean[len(prefix):]
    return kind, clean, duration, optional, subtype


def titled(text):
    """Titles carry markup -- book titles are italicised, as in
    'Guided Close Reading: How Moods Disclose a World in *Being and Time* §29'.

    Return both renderings: HTML for display, plain text for attributes,
    meta tags, and slugs, which must never contain markup.
    """
    return {"title": strip_md(text), "titleHtml": inline(text)}


def described(text):
    """Same split for descriptions, which also carry italics."""
    return {"description": strip_md(text), "descriptionHtml": inline(text)} if text \
        else {"description": "", "descriptionHtml": ""}


# --------------------------------------------------------------------------
# Section helpers
# --------------------------------------------------------------------------

def split_h2(lines):
    """Split a block into (intro_lines, [(title, lines)...]) on '## ' headings."""
    intro, sections, current = [], [], None
    for line in lines:
        if re.match(r"^##\s+(?!#)", line.strip()):
            current = (heading_text(line), [])
            sections.append(current)
        elif current is None:
            intro.append(line)
        else:
            current[1].append(line)
    return intro, sections


def labelled_text(lines, label):
    """Pull the text of a '**Label:** value' paragraph."""
    pattern = re.compile(r"^\s*\*\*%s:?\*\*:?\s*(.*)$" % re.escape(label))
    for idx, line in enumerate(lines):
        m = pattern.match(line)
        if not m:
            continue
        buf = [m.group(1).strip()]
        for cont in lines[idx + 1:]:
            if not cont.strip():
                break
            buf.append(cont.strip())
        return " ".join(b for b in buf if b).strip()
    return ""


def labelled_list(lines, label):
    """Pull the bullet list that follows a '**Label:**' line."""
    pattern = re.compile(r"^\s*\*\*%s:?\*\*:?\s*$" % re.escape(label))
    for idx, line in enumerate(lines):
        if not pattern.match(line):
            continue
        items = []
        for cont in lines[idx + 1:]:
            s = cont.strip()
            if not s:
                if items:
                    break
                continue
            if s.startswith("- ") or s.startswith("* "):
                items.append(s[2:].strip())
            else:
                break
        return items
    return []


def drop_labelled(lines, labels):
    """Remove '**Label:** ...' paragraphs and their lists from a block."""
    out, skip = [], False
    patterns = [re.compile(r"^\s*\*\*%s:?\*\*" % re.escape(l)) for l in labels]
    for line in lines:
        s = line.strip()
        if any(p.match(line) for p in patterns):
            skip = True
            continue
        if skip:
            if not s:
                skip = False
                continue
            if s.startswith("- ") or s.startswith("* "):
                continue
            skip = False
        out.append(line)
    return out


# --------------------------------------------------------------------------
# Quiz parsing
# --------------------------------------------------------------------------

RE_Q_HEAD = re.compile(r"^##\s+Question\s+(\d+)\s*-\s*(?:variation\s+(\d+)\s*,\s*)?(.+)$")
RE_OPT_CORRECT = re.compile(r"^\*\*([A-H]):\s*(.+?)\*\*\s*\(correct\)\s*$")
RE_OPT_PLAIN = re.compile(r"^([A-H]):\s+(.+)$")
RE_FEEDBACK = re.compile(r"^Feedback:\s*(.*)$")
RE_DEFAULT_FB = re.compile(r"^Default Feedback:\s*(.*)$")
RE_BLANK_MARK = re.compile(r"^\[\[\[response\s+(\d+)\]\]\]\s*$")
RE_BLANK_INLINE = re.compile(r"\[\[\[response\s+(\d+)\]\]\]")

TYPE_MAP = [
    ("multiple dropdowns", "dropdowns"),
    ("multiple choice", "single"),
    ("checkbox", "multi"),
    ("text match", "text"),
]


def parse_question(spec, lines):
    """Parse one question block into a serialisable dict."""
    qtype = "single"
    for needle, name in TYPE_MAP:
        if needle in spec:
            qtype = name
            break

    question = {
        "type": qtype,
        "shuffle": "shuffle" in spec,
        "partialCredit": "partial credit" in spec,
        "stemHtml": "",
        "options": [],
        "defaultFeedbackHtml": "",
    }

    stem, current_blank = [], None
    if qtype == "dropdowns":
        question["blanks"] = []

    # Consecutive options sometimes share a single Feedback line -- two accepted
    # spellings of one text-match answer, for instance. Feedback is therefore
    # applied to the whole run of options since the last Feedback line.
    pending = []         # options awaiting their Feedback line
    target = question["options"]

    i, n = 0, len(lines)
    while i < n:
        raw = lines[i]
        flat = unescape_md(raw).strip()
        i += 1

        if not flat:
            continue

        mark = RE_BLANK_MARK.match(flat)
        if mark and qtype == "dropdowns":
            current_blank = {"n": int(mark.group(1)), "options": []}
            question["blanks"].append(current_blank)
            target = current_blank["options"]
            pending = []
            continue

        m = RE_DEFAULT_FB.match(flat)
        if m:
            question["defaultFeedbackHtml"] = inline(m.group(1))
            pending = []
            continue

        m = RE_FEEDBACK.match(flat)
        if m:
            feedback = inline(m.group(1))
            for option in pending:
                option["feedbackHtml"] = feedback
            pending = []
            continue

        m = RE_OPT_CORRECT.match(flat)
        if m:
            option = {"id": m.group(1), "html": inline(m.group(2)),
                      "text": strip_md(m.group(2)), "correct": True, "feedbackHtml": ""}
            target.append(option)
            pending.append(option)
            continue

        m = RE_OPT_PLAIN.match(flat)
        if m and not flat.startswith("Note:"):
            option = {"id": m.group(1), "html": inline(m.group(2)),
                      "text": strip_md(m.group(2)), "correct": False, "feedbackHtml": ""}
            target.append(option)
            pending.append(option)
            continue

        if not question["options"] and current_blank is None:
            stem.append(raw)
        pending = []

    stem_md = "\n".join(stem)
    if qtype == "dropdowns":
        stem_md = RE_BLANK_INLINE.sub(lambda m: "@@BLANK%s@@" % m.group(1), unescape_md(stem_md))
    stem_html = render(stem_md, base_level=4)
    if qtype == "dropdowns":
        stem_html = re.sub(r"@@BLANK(\d+)@@",
                           lambda m: '<span class="q-blank" data-blank="%s"></span>' % m.group(1),
                           stem_html)
    question["stemHtml"] = stem_html

    if qtype == "dropdowns":
        question.pop("options", None)
    return question


def parse_quiz(lines, kind):
    """Split a quiz item body into its overview and questions."""
    heads = [i for i, l in enumerate(lines) if RE_Q_HEAD.match(unescape_md(l).strip())]
    overview_lines = lines[: heads[0]] if heads else lines
    overview_lines = [l for l in overview_lines if not re.match(r"^##\s+Overview\s*$", l.strip())]

    questions = []
    for idx, start in enumerate(heads):
        end = heads[idx + 1] if idx + 1 < len(heads) else len(lines)
        block = lines[start + 1: end]
        while block and (not block[-1].strip() or block[-1].strip() == "---"):
            block.pop()
        m = RE_Q_HEAD.match(unescape_md(lines[start]).strip())
        q = parse_question(m.group(3).lower(), block)
        q["n"] = int(m.group(1))
        q["variation"] = int(m.group(2)) if m.group(2) else None
        questions.append(q)

    quiz = {
        "kind": kind,
        "overviewHtml": render(overview_lines, base_level=3),
        "passPercent": PASS_PERCENT if kind == GRADED_QUIZ else None,
    }

    variations = sorted({q["variation"] for q in questions if q["variation"]})
    if variations:
        forms = []
        for v in variations:
            form = [q for q in questions if q["variation"] == v]
            form.sort(key=lambda q: q["n"])
            forms.append(form)
        quiz["forms"] = forms
    else:
        questions.sort(key=lambda q: q["n"])
        quiz["forms"] = [questions]
    return quiz


# --------------------------------------------------------------------------
# Dialogue parsing
# --------------------------------------------------------------------------

RE_CLAUDE_LINK = re.compile(r"^\s*\[Open in Claude\]\(.*\)\s*$")
RE_PROMPT_LABEL = re.compile(r"^\s*\*\*Prompt\*\*\s*$")


def parse_dialogue(lines):
    """Split a dialogue item into its learner-facing intro and the prompt.

    The 'Open in Claude' link in the source is discarded: the site rebuilds the
    URL from the prompt text at click time, so the link format lives in one
    place rather than in 38 markdown files.
    """
    intro, prompt, in_fence = [], [], False
    for line in lines:
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            prompt.append(line)
            continue
        if RE_CLAUDE_LINK.match(line) or RE_PROMPT_LABEL.match(line):
            continue
        intro.append(line)
    return render(intro, base_level=3), "\n".join(prompt).strip()


def parse_prompt_file(path):
    """Index a 'Dialogue Prompts' file by (module, lesson) for cross-checking."""
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    prompts, key, in_fence, buf = {}, None, False, []
    for line in text.split("\n"):
        flat = unescape_md(line.strip())
        m = re.match(r"^##\s+Module\s+(\d+)\s*-\s*Lesson\s+(\d+)\s*\|", flat)
        if m and not in_fence:
            key = (int(m.group(1)), int(m.group(2)))
            continue
        if line.strip().startswith("```"):
            if in_fence and key:
                prompts[key] = "\n".join(buf).strip()
                buf = []
            in_fence = not in_fence
            continue
        if in_fence:
            buf.append(line)
    return prompts


# --------------------------------------------------------------------------
# Course parsing
# --------------------------------------------------------------------------

def parse_course(path, slug, prompts_path=None, warn=None):
    warn = warn or (lambda msg: None)
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    lines = text.split("\n")

    heads = [i for i, l in enumerate(lines) if l.startswith("# ")]
    blocks = []
    for idx, start in enumerate(heads):
        end = heads[idx + 1] if idx + 1 < len(heads) else len(lines)
        body = lines[start + 1: end]
        while body and (not body[-1].strip() or body[-1].strip() == "---"):
            body.pop()
        blocks.append((heading_text(lines[start]), body))

    course = None
    modules, current_module, current_lesson, project = [], None, None, None
    item_counter = 0

    for title, body in blocks:
        m = RE_COURSE.match(title)
        if m and course is None:
            _, sections = split_h2(body)
            by_name = {name: lns for name, lns in sections}
            desc_lines = by_name.get("Course Description", [])
            course = {
                "num": int(m.group(1)),
                "slug": slug,
                **titled(m.group(2).strip()),
                "descriptionHtml": render(drop_labelled(desc_lines, ["Who this is for"]), base_level=3),
                "audience": labelled_text(desc_lines, "Who this is for"),
                "outcomes": [inline(o) for o in _bullets(by_name.get("What You Will Learn", []))],
                "modules": modules,
            }
            continue

        m = RE_MODULE.match(title)
        if m:
            intro, sections = split_h2(body)
            further = next((lns for name, lns in sections if name == "Further Reading"), [])
            current_module = {
                "num": int(m.group(1)),
                "slug": slugify(m.group(2)),
                **titled(m.group(2).strip()),
                **described(labelled_text(intro, "Module Description")),
                "objectives": [inline(o) for o in labelled_list(intro, "Learning Objectives")],
                "furtherReadingHtml": render(further, base_level=3),
                "lessons": [],
            }
            modules.append(current_module)
            current_lesson = None
            continue

        m = RE_LESSON.match(title)
        if m:
            current_lesson = {
                "num": int(m.group(2)),
                "moduleNum": int(m.group(1)),
                "slug": lesson_slug(m.group(3).strip()),
                **titled(m.group(3).strip()),
                **described(labelled_text(body, "Lesson Description")),
                "objectives": [inline(o) for o in labelled_list(body, "Learning Objectives")],
                "items": [],
            }
            if current_module is None:
                warn("lesson before any module in %s" % path.name)
                continue
            current_module["lessons"].append(current_lesson)
            continue

        m = RE_PROJECT.match(title)
        if m:
            project = {
                "slug": "course-project",
                **titled(m.group(1).strip()),
                **described(labelled_text(body, "Project Description")),
                "objectives": [inline(o) for o in labelled_list(body, "Learning Objectives")],
                "items": [],
            }
            current_lesson = project
            continue

        # Anything left is an item belonging to the current lesson or project.
        kind, clean_title, duration, optional, subtype = classify_item(title)
        if current_lesson is None:
            warn("orphan item '%s' in %s" % (clean_title[:40], path.name))
            continue

        item_counter += 1
        item = {
            "type": kind,
            "subtype": subtype,
            **titled(clean_title),
            "durationMin": duration,
            "optional": optional,
            "anchor": "item-%d" % (len(current_lesson["items"]) + 1),
        }

        if kind == DIALOGUE:
            item["introHtml"], item["prompt"] = parse_dialogue(body)
            # A Guided Conversation with no fenced prompt would render buttons
            # that open an empty chat, so say so at build time instead.
            if not item["prompt"]:
                warn("no fenced prompt block in '%s' (%s)"
                     % (item["title"][:48], path.name))
            elif len(item["prompt"]) < 400:
                warn("prompt looks truncated (%d chars) in '%s' (%s)"
                     % (len(item["prompt"]), item["title"][:40], path.name))
        elif kind in (KNOWLEDGE_CHECK, GRADED_QUIZ):
            item["quiz"] = parse_quiz(body, kind)
        else:
            item["bodyHtml"] = render(body, base_level=3)

        current_lesson["items"].append(item)

    if course is None:
        raise ValueError("no course heading found in %s" % path)
    course["project"] = project

    if prompts_path and prompts_path.exists():
        _verify_prompts(course, parse_prompt_file(prompts_path), warn)

    return course


def _bullets(lines):
    out = []
    for line in lines:
        s = line.strip()
        if s.startswith("- ") or s.startswith("* "):
            out.append(s[2:].strip())
    return out


def _verify_prompts(course, prompts, warn):
    """Cross-check the embedded prompts against the standalone prompt files."""
    checked = 0
    for module in course["modules"]:
        for lesson in module["lessons"]:
            key = (module["num"], lesson["num"])
            reference = prompts.get(key)
            if reference is None:
                continue
            for item in lesson["items"]:
                if item["type"] != DIALOGUE:
                    continue
                checked += 1
                if item["prompt"].strip() != reference.strip():
                    warn("dialogue prompt differs from prompt file at C%d M%d L%d"
                         % (course["num"], module["num"], lesson["num"]))
    return checked
