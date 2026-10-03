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

## Testing on a phone

Double-click **`serve-phone.bat`**, or run:

```sh
py -3 tools/serve.py --lan
```

It prints the address to type into the phone's browser, for example
`http://192.168.0.52:8000/`. The phone must be on the same Wi-Fi.

`--lan` binds every network interface, which exposes the site to anything on
your local network for as long as it runs. That is why it is opt-in: plain
`serve.bat` stays on this machine.

If the phone cannot connect, Windows Firewall is blocking inbound traffic to
Python. Windows normally prompts the first time and an Allow click creates the
rule. To check or create it (needs an elevated PowerShell):

```powershell
# is there already a rule?
Get-NetFirewallApplicationFilter | Where-Object { $_.Program -like '*python*' } |
  ForEach-Object { $_ | Get-NetFirewallRule } | Where-Object Direction -eq Inbound |
  Select-Object DisplayName, Profile, Action, Enabled

# if not, allow just this port on private and public networks
New-NetFirewallRule -DisplayName "Knowledge InSight dev server" -Direction Inbound `
  -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private,Public
```

Remove it again with
`Remove-NetFirewallRule -DisplayName "Knowledge InSight dev server"`.

### Finding layout bugs without a phone

Horizontal scroll is almost always one element refusing to shrink, and
guessing which is slower than measuring. Two dev tools, neither part of the
site:

```sh
# every element wider than a 390px viewport, with the widths that caused it
start "" "http://localhost:8000/tools/overflow-probe.html?w=390&url=/programs/phenomenology-consciousness/map/"

# a screenshot at a true phone viewport
powershell -File tools/shoot.ps1 -Path "/programs/.../map/" -Width 390 -Out shot.png
```

`overflow-probe.html` renders a page in an iframe at an exact width and reports
the overflow and the elements causing it. `?open=lesson|module|course|item`
clicks that control first, since a dropdown bug only shows once the menu is
open; `?measure=sel1|sel2` prints rendered widths and flex values.

Headless Edge's `--window-size` does **not** resize the layout viewport, it
only crops the capture, so a naive phone-width screenshot shows a desktop
layout with its right side cut off. `shoot.ps1` goes through the probe's iframe
to get a real narrow viewport.

### What differs on a phone

Served over plain `http`, the page is not a *secure context*, so
`navigator.clipboard` does not exist. `assets/js/site.js` falls back to a
`document.execCommand` path written to work on iOS, which ignores `.select()`
on a readonly textarea and ignores off-screen elements. Test the **Copy
prompt** button there specifically; it takes a different code path than on
desktop.

The "Claude desktop app" button is hidden on touch devices, since the
`claude://` scheme has nothing to open.

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
`dialogue`, `journal`, `activity`, `knowledge-check`, `graded-quiz`, and
`assignment`. A ✍️ item is a journal if its title says "Journal Entry" or
starts "Journal Prompt", an activity if it starts "Hands-on Activity", and an
assignment otherwise.
Adding a type — `video`, say — means adding an icon, a colour pair, and a
render branch; the rail, progress, and navigation pick it up unchanged.

Nothing in the templates is specific to phenomenology. A new program is a
new entry in `content/site.json` plus its Markdown files, which may sit in a
subfolder of `markdown/` (`"website": "AI Literacy/Course 1 - ….md"`). Order
in the `programs` array is order on the splash page. An optional `rhythm`
list on the program describes its lesson pattern on the program page; without
one, the original program's pattern is shown.

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
"feedbackUrl": "https://docs.google.com/forms/d/e/<form-id>/viewform",
"feedbackLocationField": "entry.1111111111",
"feedbackTitleField":    "entry.2222222222",
"feedbackPageField":     "entry.3333333333"
```

Get the field ids from the form's **Send > Get pre-filled link**. With them set,
every item gains a quiet "Report an issue with this item" link, and
`assets/js/feedback.js` prefills three values:

| Field | Example | Why |
| :---- | :---- | :---- |
| location | `c1.m1.l2.i7` | stable id; survives a retitled lesson and sorts in the sheet |
| where | `Course 1 - Module 1 - Lesson 2 - Item 7: Map the Aboutness…` | readable at a glance |
| page | the full URL including `#item-7` | jumps straight back to the item |

Leave `feedbackUrl` blank and no per-item links render at all, and the status
page shows an honest placeholder rather than a dead button.

`content/<program>/locations.csv` is generated on every build: one row per item
with its id, title, and URL. Paste it into a second tab of the responses sheet
so a report that says `c3.m2.l1.i6` is readable with a VLOOKUP, without putting
titles into the form where they would go stale.

Google Forms has no hidden fields, so a learner can see and edit the prefilled
values. Keeping them in a final section headed "Page details (filled in
automatically)" is the usual accommodation.

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
| `ki-wordmark.svg` | new | transparent wordmark for print and decks (not used by the site) |
| `og-card.jpg` | `KI background.png` | social sharing card, 1200x630 |
| `adam-h.jpg` | `adam-h.jpg` | About page portrait |

`images/` now holds only the four originals that an asset is derived from.
`py -3 tools/unused.py` reports any file that nothing references, and treats a
source image as used when something in `assets/img/` was generated from it.
| `apple-touch-icon.png`, `favicon-32.png` | `logo.png` | icons |

The header mark is drawn from the icon sprite rather than loaded as an image,
so it inherits `currentColor` and sits correctly on the dark blue bar.
