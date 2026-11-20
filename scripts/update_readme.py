"""Rewrites the live section of README.md from the GitHub API and now.json.

Standard library only. Runs inside the GitHub Action, or locally:
    GITHUB_REPOSITORY_OWNER=yourname python scripts/update_readme.py
"""
import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USER = os.environ["GITHUB_REPOSITORY_OWNER"]
TOKEN = os.environ.get("GITHUB_TOKEN")
START, END = "<!--LIVE:START-->", "<!--LIVE:END-->"


def api(path):
    req = urllib.request.Request(f"https://api.github.com{path}")
    req.add_header("Accept", "application/vnd.github+json")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def ago(iso):
    then = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    secs = int((datetime.now(timezone.utc) - then).total_seconds())
    for size, unit in ((86400, "d"), (3600, "h"), (60, "m")):
        if secs >= size:
            return f"{secs // size}{unit} ago"
    return "just now"


def latest_commits(limit=5):
    rows = []
    for ev in api(f"/users/{USER}/events/public?per_page=50"):
        if ev["type"] != "PushEvent":
            continue
        repo = ev["repo"]["name"]
        for c in reversed(ev["payload"].get("commits", [])):
            msg = c["message"].splitlines()[0][:70]
            rows.append(f"- `{repo.split('/')[-1]}` {msg} *({ago(ev['created_at'])})*")
            if len(rows) == limit:
                return rows
    return rows or ["- Quiet stretch. Heads down on something."]


def recent_repos(limit=4):
    repos = api(f"/users/{USER}/repos?sort=pushed&per_page=10&type=owner")
    repos = [r for r in repos if not r["fork"] and r["name"] != USER][:limit]
    return [
        f"- [{r['name']}]({r['html_url']}) {r['description'] or ''}".rstrip()
        + f" · {r['language'] or 'n/a'}"
        for r in repos
    ]


def build():
    now = json.loads((ROOT / "now.json").read_text())
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    parts = [
        "### Right now",
        f"- **Building:** {now['building']}",
        f"- **Learning:** {now['learning']}",
        f"- **Reading:** {now['reading']}",
        f"- **Open to:** {now['open_to']}",
        "",
        "### Last commits",
        *latest_commits(),
        "",
        "### Recently active repos",
        *recent_repos(),
        "",
        f"*Last refreshed {stamp}*",
    ]
    return "\n".join(parts)


def main():
    readme = ROOT / "README.md"
    text = readme.read_text()
    block = f"{START}\n{build()}\n{END}"
    new = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: block, text, flags=re.S)
    readme.write_text(new)


if __name__ == "__main__":
    main()
