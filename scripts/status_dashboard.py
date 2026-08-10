#!/usr/bin/env python3
"""Build the Compass local progress dashboard (dashboard.html) from STATUS.json.

STATUS.json (repo root) is the only hand-edited input — project, focus,
build phases, human gates, and the milestone log. Derived live at
generation time: optional check commands and recent git history. Stdlib
only, no network, no third-party deps. Output is a static, self-contained
page with inline CSS that refreshes itself every 60s when left open.

Usage:
  python3 scripts/status_dashboard.py [--skip-checks]

After editing STATUS.json, re-run this and open dashboard.html.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATUS_FILE = ROOT / "STATUS.json"
OUT = ROOT / "dashboard.html"

CHIP = {
    "done": ("DONE", "#1f883d"),
    "in_progress": ("IN PROGRESS", "#9a6700"),
    "blocked": ("BLOCKED", "#cf222e"),
    "pending": ("PENDING", "#57606a"),
}


def run_checks(checks: list) -> list:
    results = []
    for c in checks:
        if "--skip-checks" in sys.argv:
            results.append((c["name"], "skipped", True))
            continue
        try:
            r = subprocess.run(
                c["command"], shell=True, cwd=ROOT,
                capture_output=True, text=True, timeout=600,
            )
            tail = ((r.stdout or r.stderr).strip().splitlines() or ["(no output)"])[-1]
            results.append((c["name"], tail, r.returncode == 0))
        except Exception as e:  # noqa: BLE001 - dashboard must render regardless
            results.append((c["name"], f"could not run: {e}", False))
    return results


def git_info() -> dict:
    def g(*args):
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True,
        ).stdout.strip()

    commits = g("log", "-8", "--pretty=%h|%ad|%s", "--date=format:%b %d %H:%M")
    return {
        "count": g("rev-list", "--count", "HEAD") or "0",
        "recent": [c.split("|", 2) for c in commits.splitlines() if c],
    }


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main() -> None:
    if not STATUS_FILE.exists():
        print(f"ERROR: {STATUS_FILE} not found", file=sys.stderr)
        sys.exit(1)

    status = json.loads(STATUS_FILE.read_text())
    checks = run_checks(status.get("checks", []))
    git = git_info()

    stages = status.get("stages", [])
    done = sum(1 for s in stages if s.get("status") == "done")
    pct = done * 100 // max(1, len(stages))

    phases_html = "\n".join(
        f"<tr><td><span class='chip' style='background:{CHIP.get(s.get('status'), CHIP['pending'])[1]}'>"
        f"{CHIP.get(s.get('status'), CHIP['pending'])[0]}</span></td>"
        f"<td><strong>{esc(s.get('name', s.get('id', '')))}</strong>"
        f"{('<br><small>' + esc(s.get('note', '')) + '</small>') if s.get('note') else ''}</td></tr>"
        for s in stages
    )

    gates_html = "\n".join(
        f"<li><strong>{esc(w.get('what', ''))}</strong> — {esc(w.get('who', ''))}"
        f"{(' · <code>' + esc(w['artifact']) + '</code>') if w.get('artifact') else ''}</li>"
        for w in status.get("waiting_on_human", [])
    ) or "<li>nothing — build on</li>"

    checks_html = "\n".join(
        f"<span class='check' style='background:{'#1f883d' if ok else '#cf222e'}'>"
        f"{esc(name)}: {esc(label)}</span>"
        for name, label, ok in checks
    )

    log_html = "\n".join(
        f"<li><span class='d'>{esc(e.get('date', ''))}</span> {esc(e.get('entry', ''))}</li>"
        for e in reversed(status.get("log", []))
    )

    commits_html = "\n".join(
        f"<li><code>{esc(h)}</code> <span class='d'>{esc(d)}</span> {esc(s)}</li>"
        for h, d, s in git["recent"]
    ) or "<li>not a git repository, or no commits yet</li>"

    project = status.get("project", "Compass")
    vision = status.get("vision", "")
    focus = status.get("focus", "")

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="60">
<title>{esc(project)} — status dashboard</title>
<style>
 body {{ font-family: -apple-system, "Segoe UI", sans-serif; max-width: 1000px;
        margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; line-height: 1.45;
        background: #ffffff; }}
 h1 {{ font-size: 1.5rem; margin-bottom: 0.2rem; }}
 h2 {{ font-size: 1.15rem; margin-top: 2rem; }}
 .sub {{ color: #57606a; margin-top: 0; }}
 .card {{ background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 8px;
         padding: 1rem 1.25rem; margin: 1rem 0; }}
 .card.warn {{ background: #fff8c5; border-color: #d4a72c; }}
 .chip {{ color: #fff; border-radius: 10px; padding: 2px 9px; font-size: 0.72rem;
         font-weight: 700; white-space: nowrap; }}
 .check {{ color: #fff; border-radius: 8px; padding: 6px 10px; font-weight: 700;
          display: inline-block; margin: 2px 6px 2px 0; font-size: 0.85rem; }}
 table {{ border-collapse: collapse; width: 100%; }}
 td {{ padding: 6px 8px; border-bottom: 1px solid #e6e8eb; vertical-align: top; }}
 .bar {{ background: #e6e8eb; border-radius: 6px; height: 12px; margin: 6px 0 2px; }}
 .bar > div {{ background: #1f883d; height: 12px; border-radius: 6px; width: {pct}%; }}
 ul {{ padding-left: 1.2rem; }}
 li {{ margin: 4px 0; }}
 code {{ background: #eef0f2; border-radius: 4px; padding: 1px 5px; font-size: 0.85em; }}
 .d {{ color: #57606a; font-size: 0.85rem; margin-right: 4px; }}
 small {{ color: #57606a; }}
 footer {{ color: #57606a; font-size: 0.8rem; margin-top: 2rem; }}
</style></head><body>
<h1>{esc(project)} — status dashboard</h1>
<p class="sub">{esc(vision)}</p>
<div class="card">
 <strong>Now:</strong> {esc(focus)}<br>
 {checks_html}
 <div class="bar"><div></div></div>
 <small>{done} of {len(stages)} phases done ({pct}%)</small>
</div>
<div class="card warn">
 <strong>Waiting on a human</strong>
 <ul>{gates_html}</ul>
</div>
<h2>Build phases</h2>
<table>{phases_html}</table>
<h2>Milestone log</h2>
<ul>{log_html}</ul>
<h2>Recent commits ({esc(git['count'])} total)</h2>
<ul>{commits_html}</ul>
<footer>Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} by
scripts/status_dashboard.py from STATUS.json. Page self-refreshes every 60s.</footer>
</body></html>"""

    OUT.write_text(html, encoding="utf-8")
    summary = ", ".join(
        "{} {}".format(n, "ok" if ok else "FAIL") for n, _, ok in checks
    ) or "none"
    print(f"wrote {OUT} ({done}/{len(stages)} phases done; checks: {summary})")


if __name__ == "__main__":
    main()
