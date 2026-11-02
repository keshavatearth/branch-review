# Branch review

A one-screen page for reviewing the work in a git repo: what was built, where it lives, and what still needs a decision. One self-contained HTML file, built from a JSON data file, for any project. Plain Python 3 and git, no dependencies.

**[Live sample](https://keshavatearth.github.io/branch-review/template.html)**: `template.html` opened on its own, showing a small made-up notes app.

## What makes it work

- **One screen, no long scroll.** A branch graph sits across the top. A list of boards runs down the left, and the selected one fills the right.
- **Boards first, commits second.** A board is one piece of work in product language ("Meetings", "Site deploy fix"), not a commit. Selecting a board highlights its commits in the graph. Its commits sit at its foot, under *Under the hood*. A commit page has a dark COMMIT tag, a lighter background, its files and diffs, and steps to the older and newer commit on the same branch (from the first commit of a branch, "older" is the branch point).
- **The whole timeline at a glance.** The graph fits the width by default. **− Fit +** spreads it out like an editing app's timeline, and zooming in is what turns on horizontal scrolling. Branch names stay pinned on the left, and their column shrinks, then shortens names, when space is tight. The eye button hides the graph and remembers the choice.
- **Decisions are visible at a glance.** Each board has a status. The first board collects everything that needs a call, with severity stripes.
- **The reader decides on the page.** Boards marked for review get Approve / Needs changes / Drop / Park with a note, plus *my pick*. **Copy my calls** copies every call as text to paste back to the agent, so decisions don't turn into a round of questions in chat.
- **Show, don't describe.** Screenshots, with a before/after toggle when there's an old version. Before/after lists for navigation or repo state. A toggleable mock when no screenshot exists.
- **Small conveniences.** Hover any commit to copy its id. Back and forward work, and a link like `page.html#a3a44b3` opens that commit. **How to read this** explains the page, and opens by itself on a first visit.
- **Half a screen is fine.** Below 1000px the board list becomes a drawer behind a bar that names the previous and next board (or, on a commit page, the older and newer commit) on each side.
- **The project's own look.** Colors and fonts come from the project's design tokens, in both light and dark.

## Making one for a project

Keep the review in the project's own folder, for example `<repo>/reviews/branch-review.json` and `.html`, with `reviews/shots/` for screenshots, and update it in place as work moves.

1. Pull the graph out of git:

   ```bash
   python3 git_data.py ~/path/to/repo --branches main,feature-a,feature-b --base <first-commit-to-show> -o ~/path/to/repo/reviews/branch-review.json
   ```

   This fills `lanes`, `commits` (lane, column, parents, pushed/local, date, message, per-file counts) and `ticks`. Add `--patches` for per-file diffs on commit pages (code first, capped by `--patch-lines` and `--commit-lines`; `--patch-skip` takes path prefixes such as vendored code). Leave out any file holding private text: diffs copy content into the page. With no `--branches` it takes every local branch, main first. `--base` defaults to the oldest merge-base with the first branch.

2. Fill in the judgement layer by hand, or have an agent do it, in the same JSON: `title`, `streams` (rename the auto `lane0…` streams into kinds of work, then set each commit's `stream`), lane `note` and `item`, `items`, `images`, `explainer` and `theme`. `examples/sample.json` is a complete example: it's the sample `template.html` shows. Write boards in plain product language: what a person sees, what's done, what needs deciding.

3. Build and open it:

   ```bash
   python3 build.py ~/path/to/repo/reviews/branch-review.json   # writes branch-review.html next to it
   ```

   `build.py` replaces the template's sample with your data and turns image paths (relative to the JSON) into data URIs, so the page is a single file. It warns about unknown commit hashes, item ids and streams. To try template changes on one project first, put a copy of `template.html` next to its JSON: `build.py` uses that copy instead of the kit's.

It works well with a coding agent writing the boards. A prompt that works: *"Make a branch review for ~/path/to/repo using path/to/branch-review: run git_data.py, then write the boards from the commits and the docs, then build it in the repo's reviews/ folder."*

To change the sample itself, edit `examples/sample.json` and run `python3 build.py examples/sample.json template.html`.

## Data format

Top level:

| Key | What it holds |
| --- | --- |
| `title`, `subtitle`, `pageTitle`, `mark` | Header text, browser-tab title, the one-glyph mark |
| `explainer` | Optional `{what, graph, boards, calls}` (HTML) for the four *How to read this* panels. Each one left out gets a generic default |
| `chips` | Optional `[{dot: ok\|warn\|bad\|acc, html}]`, small status chips under the title. Leave empty for none |
| `theme` | `{light: {--token: value}, dark: {...}}`. Overrides any token in `template.html`'s `:root` (colors, `--f-display`, `--f-body`, `--panel*` for the sidebar-style blocks) |
| `streams` | `{key: {label, light, dark}}`, the kinds of work that color the dots and the legend |
| `lanes` | `[{name, note, item}]`, one per branch. `item` is the board opened by clicking the branch name |
| `commits` | `[{h, lane, col, parents, state: base\|pushed\|local, stream, date, subject, body, files: [[path, add, del]], patches: {path: diff}}]` |
| `ticks`, `flags`, `bands` | Graph labels: `{col, label}` or `{from, to, label}`. `{lane, col, text}` under a dot. `{lane, from, to}` as a highlight band |
| `graphHint` | The line of help under the legend |
| `fileGroups` | `[{prefix, label}]` to fold a folder (vendored code, say) into one row on commit pages |
| `images` | `{key: "relative/path.jpg"}`, referenced by boards |
| `items` | The boards, in order. Group names come from each board's `group` |
| `verdicts`, `storageKey` | Optional. The verdict buttons (default Approve / Needs changes / Drop / Park) and the browser-storage key for the reader's calls and view settings |

A board: `id`, `group`, `label`, `status: [kind, text]`, `stream`, `where` (branch), `title`, `lede` (HTML), `callouts: [{sev, h, p, ol|ul}]`, `blocks`, `bullets` (HTML) with an optional `bulletsLabel`, `shots: [{img, cap, tab}]` or `mock`, `cmds`, `commits` (listed under *Under the hood*), `review: true` (show the verdict buttons) and `rec` (the verdict key marked *my pick*). Status and severity kinds are `ok`, `warn`, `bad`, `acc`, `nt` and `info`.

Blocks, rendered above the bullets in the order given:

- `ba`: two sidebar panels, before → after. `{before: {title, note, rows: [{text, gone}]}, after: {title, note, rows: [{text, why, tag, tagKind: new|chg|bad, item}]}}`. Rows with an `item` are clickable.
- `asks`: decision rows with a severity stripe. `{label, rows: [{sev, title, text, item, pill}]}`.
- `path`: a short flow of steps. `{label, steps: [...], link: {item, text}}`.
- `steps`: a numbered list, with optional commands and a done tick. `{label, rows: [{title, text, cmds, item, itemText, done}]}`.
- `table`: `{label, head: [...], rows: [[cell, ...] | {section}]}`. Cells are HTML; a cell given as `[kind, text]` is a status.
- `group`: one slice of a big commit. `{label, status, commits, files: [substring | "^prefix"], rows: [[adds|changes|removes|note, html]], item, itemText}`, with the slice's diffs underneath.
- `mock`: a two-state illustration with a toggle button. `{label, meta: [left, right], a: {text, btn}, b: {text, btn, mono}}`.
- `html`: `{html}`, for anything else.

## Files

- `template.html`: the page, with the sample inside so it opens on its own. All UI lives here, data-driven, light and dark.
- `git_data.py`: repo → data skeleton.
- `build.py`: data → single HTML file.
- `examples/sample.json`: the sample's data.

MIT licensed.
