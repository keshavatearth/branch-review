#!/usr/bin/env python3
"""Pull the branch graph of a git repo into a branch-review data file.

    python3 git_data.py REPO [--branches main,feature,...] [--base REV] [--patches] [-o data.json]

Writes the mechanical half of a review: lanes (one per branch, in the order
given, main first), every commit since --base with its lane, column, parents,
pushed/local state, date, message and per-file line counts, plus date ticks.
The judgement half (streams, lane notes, items, chips, theme, images) is for
the agent to fill in; see README.md.

--base defaults to the oldest merge-base of the branches with the first one,
so the graph starts where the branches last agreed.

--patches adds each commit's diff, per file, for reading in the page. Code
comes first; each file stops at --patch-lines and each commit at
--commit-lines, and paths under --patch-skip get none.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

PALETTE = [  # light, dark: muted categorical colors that read on both grounds
    ("#2f5b8a", "#8db3e2"), ("#9c4626", "#e08a63"), ("#3d7a4a", "#8cc79a"),
    ("#7a4b6e", "#c494b8"), ("#a0781e", "#d9b25a"), ("#2f6c78", "#6fb3bf"),
    ("#8d9096", "#6f747a"),
]


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True, text=True).stdout


CODE = (".swift", ".py", ".sh", ".js", ".ts", ".css", ".html", ".plist", ".entitlements", ".toml", ".json")


def patches(repo, h, skip, per_file, per_commit):
    """{path: diff from the first @@}, code files first, cut to the line budgets."""
    raw = subprocess.run(["git", "-C", repo, "show", "--format=", "-p", "-M", "--no-color", "--no-ext-diff", h],
                         check=True, capture_output=True).stdout.decode("utf-8", "replace")
    out = {}
    for chunk in re.split(r"^diff --git ", raw, flags=re.M)[1:]:
        lines = chunk.split("\n")
        m = re.search(r"^\+\+\+ b/(.*)$", chunk, re.M) or re.search(r"^rename to (.*)$", chunk, re.M)
        path = m.group(1) if m else lines[0].split(" b/", 1)[-1]
        if path == "/dev/null" or not m:
            gone = re.search(r"^--- a/(.*)$", chunk, re.M)
            path = gone.group(1) if gone else path
        if any(path.startswith(p) for p in skip) or "Binary files" in chunk:
            continue
        body = lines[next((i for i, l in enumerate(lines) if l.startswith("@@")), len(lines)):]
        while body and body[-1] == "":
            body.pop()
        if body:
            out[path] = body
    order = sorted(out, key=lambda p: (not p.endswith(CODE), len(out[p])))
    kept, used = {}, 0
    for p in order:
        room = min(per_file, per_commit - used)
        if room < 20:
            break
        body = out[p]
        cut = body[:room] + ([f"… {len(body) - room} more lines not shown"] if len(body) > room else [])
        kept[p] = "\n".join(cut)
        used += min(len(body), room)
    return kept


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("repo")
    ap.add_argument("--branches", help="comma-separated, main first (default: every local branch, main first)")
    ap.add_argument("--base", help="first commit to show (default: oldest merge-base with the first branch)")
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--patches", action="store_true", help="include per-file diffs")
    ap.add_argument("--patch-skip", default="", help="comma-separated path prefixes that get no diff (vendored code, data)")
    ap.add_argument("--patch-lines", type=int, default=400, help="most diff lines per file (default 400)")
    ap.add_argument("--commit-lines", type=int, default=3000, help="most diff lines per commit (default 3000)")
    ap.add_argument("-o", "--out", help="output file (default: stdout)")
    a = ap.parse_args()
    repo = str(Path(a.repo).expanduser().resolve())

    if a.branches:
        branches = [b.strip() for b in a.branches.split(",") if b.strip()]
    else:
        heads = git(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads").split()
        first = next((b for b in ("main", "master") if b in heads), heads[0])
        branches = [first] + sorted(b for b in heads if b != first)

    if a.base:
        base = git(repo, "rev-parse", a.base).strip()
    else:
        bases = {git(repo, "merge-base", branches[0], b).strip() for b in branches}
        base = min(bases, key=lambda h: int(git(repo, "rev-list", "--count", h).strip()))

    # Lane = first branch (in the given order) whose history contains the commit.
    lane = {base: 0}
    for i, b in enumerate(branches):
        for h in git(repo, "rev-list", f"{base}..{b}").split():
            lane.setdefault(h, i)
    order = git(repo, "rev-list", "--reverse", "--topo-order", base, *branches, "--not", f"{base}^@").split()
    order = [h for h in order if h in lane]

    # Pushed = reachable from any remote-tracking branch.
    remotes = git(repo, "for-each-ref", "--format=%(refname)", f"refs/remotes/{a.remote}").split()
    pushed = set(git(repo, "rev-list", *remotes, "--not", f"{base}^@").split()) if remotes else set()

    commits, col, short = [], {}, {}
    for h in order:
        short[h] = git(repo, "rev-parse", "--short", h).strip()
    for h in order:
        fmt = git(repo, "show", "-s", "--format=%P%x00%ad%x00%B", "--date=format:%d %b", h)
        parents_raw, date, body = fmt.split("\x00", 2)
        parents = [p for p in parents_raw.split() if p in lane]
        col[h] = 0 if h == base else 1 + max((col[p] for p in parents), default=0)
        files = []
        for line in git(repo, "show", "--numstat", "--format=", h).splitlines():
            parts = line.split("\t")
            if len(parts) == 3:
                ad, de, path = parts
                files.append([path, int(ad) if ad != "-" else -1, int(de) if de != "-" else -1])
        commits.append({
            "h": short[h], "lane": lane[h], "col": col[h],
            "parents": [short[p] for p in parents],
            "state": "base" if h == base else ("pushed" if h in pushed else "local"),
            "stream": f"lane{lane[h]}", "date": date.lstrip("0"),
            "subject": body.strip().split("\n")[0], "body": body.strip(), "files": files,
        })
        if a.patches and h != base:
            skip = [p.strip() for p in a.patch_skip.split(",") if p.strip()]
            commits[-1]["patches"] = patches(repo, h, skip, a.patch_lines, a.commit_lines)

    # Date ticks along the first lane: one label per run of equal dates.
    ticks, run = [], None
    for c in sorted((c for c in commits if c["lane"] == 0), key=lambda c: c["col"]):
        if run and run["label"] == c["date"]:
            run["to"] = c["col"]
        else:
            run = {"from": c["col"], "to": c["col"], "label": c["date"]}
            ticks.append(run)
    ticks = [{"col": t["from"], "label": t["label"]} if t["from"] == t["to"] else t for t in ticks]

    lanes = []
    for i, b in enumerate(branches):
        up = subprocess.run(["git", "-C", repo, "rev-parse", "--abbrev-ref", f"{b}@{{upstream}}"], capture_output=True, text=True)
        if up.returncode == 0:
            ahead, behind = git(repo, "rev-list", "--left-right", "--count", f"{b}...{up.stdout.strip()}").split()
            note = "pushed" if ahead == "0" and behind == "0" else f"{ahead} not pushed" if behind == "0" else f"{ahead} ahead, {behind} behind {up.stdout.strip()}"
        else:
            note = "only on this Mac"
        lanes.append({"name": b, "note": note, "item": ""})

    data = {
        "title": Path(repo).name, "subtitle": "branch review",
        "repo": repo, "base": short[base],
        "chips": [], "theme": {},
        "streams": {f"lane{i}": {"label": b, "light": PALETTE[i % len(PALETTE)][0], "dark": PALETTE[i % len(PALETTE)][1]} for i, b in enumerate(branches)},
        "lanes": lanes, "ticks": ticks, "flags": [], "bands": [], "fileGroups": [],
        "commits": commits, "items": [], "images": {},
    }
    out = json.dumps(data, indent=1, ensure_ascii=False)
    if a.out:
        Path(a.out).write_text(out + "\n", encoding="utf-8")
        print(f"{len(commits)} commits across {len(branches)} branches -> {a.out}", file=sys.stderr)
    else:
        print(out)


if __name__ == "__main__":
    main()
