# Knowledge InSight

Static site for Knowledge InSight's open-access learning programs, built from
Markdown. Destined for `knowledgeinsight.org`.

## Running it locally

The site uses clean directory URLs and fetches quiz data, so open it through a
server rather than from the filesystem. Opening `index.html` directly will load
the page but the quizzes will not run.

**Double-click `serve.bat`.** It rebuilds, starts the server, and opens a
browser. Ctrl+C stops it.

Or do the same thing by hand:

```sh
py -3 tools/serve.py           # build + serve + open a browser
py -3 tools/serve.py --port 8080 --no-open --no-build
```

Or with nothing but the standard library, if you have already built:

```sh
py -3 -m http.server 8000      # then visit http://localhost:8000
```

`serve.py` exists because the plain one-liner has two rough edges on Windows:
it does not rebuild, and if port 8000 is already taken `http.server` will
silently bind it anyway — `SO_REUSEADDR` is permissive there — leaving two
servers fighting over one port. `serve.py` refuses a busy port and steps to
the next free one.

## Building

```sh
py -3 tools/build.py          # build
py -3 tools/build.py --clean  # wipe generated output first
py -3 tools/check.py          # HTML, links, anchors, quiz payloads
py -3 tools/jslint.py         # structural check on the JavaScript
```

No dependencies beyond Python 3. Nothing is installed; no Node, no bundler.

## Where to edit what

**Never edit the HTML.** `index.html`, `about.html`, and everything under
`programs/` are generated and are overwritten by every build. Each one opens
with a banner saying so. Edits there are lost on the next `tools/build.py`.

| To change | Edit |
| :---- | :---- |
| Site copy, About text, bio, program titles, vetting status | `content/site.json` |
| Course, module, lesson, and item content | `markdown/` |
| Page structure and markup | `tools/build.py` |
| Styling | `assets/css/main.css` |
| Behaviour | `assets/js/` |

## How it works

`markdown/` holds the authored source and is the only place content is edited.
`tools/build.py` parses it and writes pre-rendered HTML, so every reading is in
the page source: the site reads fine with JavaScript disabled and indexes
properly. JavaScript adds navigation state, progress, the quizzes, and the
Guided Conversation links.

```
markdown/           authored source (never edited by the build)
content/site.json   org copy and the program registry — edit this, not the code
content/<program>/  generated: program.json nav tree + one JSON per quiz
tools/              build, parser, Markdown renderer, checks
assets/             stylesheet, scripts, images
index.html          generated splash
about.html          generated
programs/           generated program, course, module, and lesson pages
```

Generated output is committed so the repo can be served directly by GitHub
Pages or any static host.

### Content model

`Program > Course > Module > Lesson > Item`, with item types `reading`,
`dialogue`, `journal`, `knowledge-check`, `graded-quiz`, and `assignment`.
Adding a type — `video`, say — means adding an icon, a colour pair, and a
render branch; the rail, progress, and navigation pick it up unchanged.

Nothing in the templates is specific to phenomenology. A second program is a
new entry in `content/site.json` plus its Markdown files.

### Parsing

Structure is read from headings alone, as the content brief recommends. The
in-file Contents tables are ignored: they are malformed (a three-column header
over four-cell rows) and the headings are the better source. The build is
strict about counts and prints a warning rather than failing silently.

Two quirks of the export are handled in `tools/mdrender.py`: backslash escapes
before punctuation (`2017\.`) are unescaped rather than rendered, and bold
spans may wrap italics (`**Garb of ideas (*Ideenkleid*):**`).

### Learning-page navigation

Learning pages carry one sticky bar and one column. The bar holds the
breadcrumb (each segment opens its siblings — the lesson picker lists every
lesson in the course, grouped by module), the course completion percentage and
a progress line on its bottom edge, previous/next lesson, and previous/next
item with a dropdown of the lesson's items. The masthead is deliberately
`position: static` on these pages so only one thing is pinned.

`assets/js/lessonnav.js` tracks the current item as the last one whose top has
passed under the bar, which is what a reader means by where they are — several
items are partly visible at any moment, so "first intersecting" would jump
around.

### Guided Conversations

Each prompt is stored once, as the text of the `<pre>` inside the collapsed
"Show the full prompt" panel. `assets/js/dialogue.js` reads it from there and
builds each assistant's URL at click time, so a link format lives in one place
rather than in 38 Markdown files.

| Assistant | Link | Prefills |
| :---- | :---- | :---- |
| Claude | `https://claude.ai/new?q=` | yes |
| ChatGPT | `https://chatgpt.com/?q=` | yes |

Only assistants that actually accept a prompt through a link get a button.
Gemini, Copilot and the rest have no such parameter, so a button for them would
open an empty chat and look broken; the copy button covers them, and the note
under the buttons says so.

Neither link format is documented, so every button copies the prompt to the
clipboard before it opens the assistant. If a link stops prefilling, the
learner can paste without needing help.

The standalone `Course N Dialogue Prompts.md` files are not required by the
build, but when present they are cross-checked against the embedded prompts and
any difference is reported as a build warning. All 38 generated Claude URLs
were verified byte-identical to the originals in the source.

### Quizzes

H5P is not used. `assets/js/quiz.js` implements the four question types in the
source — single answer, multiple answers with partial credit, text match with
case- and punctuation-insensitive alternates, and dropdown blanks — and renders
each option's own feedback. Quiz data is fetched on demand, so a lesson page
does not carry its quiz until the learner opens it.

Graded quizzes ship three fixed forms of the same ten questions and rotate them
per attempt, so a retake covers the same topics rather than drawing at random.
The pass target is 80 percent.

### Progress

A flat map of item id to timestamp in `localStorage`, under `ki.progress.v1`.
Rollups for a lesson, course, or program are computed by counting ids under a
prefix (`c1.m1.l1.i7` → `c1.m1.l1` → `c1`), so there is no second data
structure and no server. There are no accounts and nothing is transmitted.

### Vetting status

Programs are published before expert review has finished, so every program,
course, and lesson page carries a seal saying which state it is in. The state
is `status` on the program in `content/site.json`: `in-progress` or `vetted`.
The seal links to a generated `/status/` page explaining what it means and how
to help.

To connect a feedback form, fill in `statuses.in-progress` in
`content/site.json`:

```json
"feedbackUrl": "https://docs.google.com/forms/d/e/<id>/viewform",
"feedbackPageField": "entry.1234567890",
"feedbackTitleField": "entry.0987654321"
```

Get the field ids from the form's **Send > Get pre-filled link**. With them set,
`assets/js/feedback.js` appends the reader's current page URL and title so a
report says where it came from. Leave `feedbackUrl` blank and the site shows an
honest placeholder instead of a dead button.

## Design

Colours are sampled from `images/knowledge-insight-background.jpg` and defined
once as custom properties in `assets/css/main.css`. Chrome takes the blues of
the painted planks; the page itself is white, with the warm paper of the book
pages used as a secondary surface for the outline sidebar and quiet bands;
item-type accents take the orange and yellow book spines plus the plum of the
wordmark. There are no styles in the HTML.

| Token | Hex | Role |
| :---- | :---- | :---- |
| `--blue-700` | `#275f92` | headings, footer |
| `--blue-600` | `#2f75b3` | primary: links, buttons |
| `--blue-400` | `#5997d2` | hover, accents |
| `--slate-900` | `#1f2837` | body text |
| `--paper` | `#faf7f1` | outline sidebar, item rail, quiet bands |
| `--white` | `#ffffff` | page ground, cards, reading surfaces |
| `--amber` | `#e2ae41` | journals, progress |
| `--rust` | `#994310` | quizzes |
| `--plum` | `#8b2060` | Guided Conversations |
| `--teal` | `#1d6b70` | the "fully vetted" seal |

Placeholder cards for programs still in development come from `upcoming` in
`content/site.json`. They are flat and unclickable by design, so a reader can
tell at a glance what they can start today.

## Images

`images/` holds the originals. `assets/img/` holds what the site actually uses:

| File | From | Use |
| :---- | :---- | :---- |
| `hero-books-blue-{480,800,1280,1920}.jpg` | `knowledge-insight-background.jpg` | splash hero, responsive set |
| `ki-mark.svg` | new | favicon and standalone mark |
| `ki-wordmark.svg` | new | transparent wordmark for print and decks |
| `og-card.jpg` | `KI background.png` | social sharing card, 1200x630 |
| `adam-h.jpg` | `adam-h.png` | About page portrait |
| `apple-touch-icon.png`, `favicon-32.png`, `logo-mark-256.png` | `logo.png` | icons |

The header mark is drawn from the icon sprite rather than loaded as an image,
so it inherits `currentColor` and sits correctly on the dark blue bar.
