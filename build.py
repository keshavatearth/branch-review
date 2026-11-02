#!/usr/bin/env python3
"""Build a single-file branch review from a data file.

    python3 build.py data.json [out.html]

Inlines the data into template.html, or into a template.html next to the data
file when there is one (a project trying out changes before they reach the
kit). The data replaces the template's own sample, so template.html opened on
its own is a working example. Image values in data["images"] that are
file paths (relative to the data file) become data: URIs, so the page has no
outside files. Output defaults to the data file's name with .html.
"""

import base64
import html
import json
import mimetypes
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__.strip().split("\n\n")[1])
    src = Path(sys.argv[1]).expanduser().resolve()
    out = Path(sys.argv[2]).expanduser().resolve() if len(sys.argv) == 3 else src.with_suffix(".html")
    data = json.loads(src.read_text(encoding="utf-8"))

    for key, value in (data.get("images") or {}).items():
        if value.startswith("data:"):
            continue
        path = (src.parent / value).resolve()
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data["images"][key] = f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"

    ids = {i["id"] for i in data.get("items", [])}
    hashes = {c["h"] for c in data["commits"]}
    problems = [f"item {i['id']}: unknown commit {h}" for i in data.get("items", []) for h in i.get("commits", []) if h not in hashes]
    problems += [f"lane {l['name']}: unknown item {l['item']}" for l in data["lanes"] if l.get("item") and l["item"] not in ids]
    problems += [f"commit {c['h']}: unknown stream {c['stream']}" for c in data["commits"] if c["stream"] not in data.get("streams", {})]
    if not data.get("items"):
        problems.append("no items: add at least an overview item")
    for p in problems:
        print(f"warning: {p}", file=sys.stderr)

    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    title = data.get("pageTitle") or f"{data.get('title', '')} {data.get('subtitle', '')}".strip()
    local = src.parent / "template.html"
    page = (local if local.exists() else HERE / "template.html").read_text(encoding="utf-8")
    page = re.sub(r"<title>.*?</title>", lambda m: f"<title>{html.escape(title)}</title>", page, count=1, flags=re.S)
    page, n = re.subn(r'(<script id="review-data" type="application/json">).*?(</script>)',
                      lambda m: m.group(1) + payload + m.group(2), page, count=1, flags=re.S)
    if n != 1:
        sys.exit("template.html has no review-data script to fill")
    out.write_text(page, encoding="utf-8")
    print(f"{out} ({len(page) // 1024} KB)")


if __name__ == "__main__":
    main()
