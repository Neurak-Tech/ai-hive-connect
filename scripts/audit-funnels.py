#!/usr/bin/env python3
"""Scan funnel HTML and JS for conversion actions and write the registry."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EVENT_PATTERNS = (
    ("form_submit", re.compile(r"<form\b", re.I)),
    ("cta_click", re.compile(r"data-cta\b|class\s*=\s*['\"][^'\"]*\bcta\b", re.I)),
    ("whatsapp_click", re.compile(r"wa\.me/|api\.whatsapp\.com|whatsapp\.com/send|whatsapp:", re.I)),
    ("calendly_click", re.compile(r"calendly\.com", re.I)),
    ("phone_click", re.compile(r"tel:", re.I)),
    ("email_click", re.compile(r"mailto:", re.I)),
)

BYPASS_MARKERS = ("AIHIVE_DISABLE_TRACKING", "data-aihive-bypass")
BOOTSTRAP = re.compile(r"/shared/bootstrap\.js")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def funnel_dirs(root: Path) -> list[Path]:
    base = root / "funnels"
    if not base.is_dir():
        return []
    return sorted(path for path in base.iterdir() if path.is_dir() and not path.name.startswith("."))


def scan_funnel(folder: Path, scanned_at: str) -> dict:
    html = read_text(folder / "index.html")
    script = read_text(folder / "app.js")
    meta = read_text(folder / "funnel.json")
    text = "\n".join((html, script, meta))
    events = []
    signals = {}
    for name, pattern in EVENT_PATTERNS:
        count = len(pattern.findall(text))
        if count:
            events.append(name)
            signals[name] = count

    bypass = any(marker in text for marker in BYPASS_MARKERS)
    has_bootstrap = bool(BOOTSTRAP.search(html))
    if bypass:
        status = "bypass"
    elif not has_bootstrap:
        status = "missing_bootstrap"
    elif events:
        status = "tracked"
    else:
        status = "no_conversions"

    return {
        "funnel": folder.name,
        "status": status,
        "events": events,
        "last_scan": scanned_at,
        "signals": signals,
    }


def load_registry(path: Path) -> dict:
    if not path.is_file():
        return {"version": 1, "generated_at": "", "funnels": []}
    return json.loads(path.read_text(encoding="utf-8"))


def blank_sha(value: str) -> bool:
    text = (value or "").strip().lower()
    return text in {"", "0" * 40, "null", "none"}


def touched_slugs(root: Path, since: str) -> set[str] | None:
    if blank_sha(since):
        return None
    result = subprocess.run(
        ["git", "diff", "--name-status", "--find-renames", f"{since}...HEAD", "--", "funnels"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or "git diff failed")
    slugs: set[str] = set()
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        for path in parts[1:]:
            pieces = Path(path).parts
            if len(pieces) >= 2 and pieces[0] == "funnels":
                slugs.add(pieces[1])
    return slugs


def build_registry(root: Path, slugs: set[str] | None, registry_path: Path | None = None) -> dict:
    scanned_at = utc_now()
    existing_path = registry_path or (root / "registry" / "conversion-status.json")
    current = load_registry(existing_path)
    by_slug = {entry["funnel"]: entry for entry in current.get("funnels", [])}
    folders = {path.name: path for path in funnel_dirs(root)}

    if slugs is None:
        scan = set(folders)
        drop = set(by_slug) - scan
    else:
        scan = slugs & set(folders)
        drop = slugs - set(folders)

    for slug in scan:
        by_slug[slug] = scan_funnel(folders[slug], scanned_at)
    for slug in drop:
        by_slug.pop(slug, None)

    return {
        "version": 1,
        "generated_at": scanned_at,
        "funnels": [by_slug[slug] for slug in sorted(by_slug)],
    }


def write_registry(path: Path, registry: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Update registry/conversion-status.json")
    parser.add_argument("--all", action="store_true", help="Scan every funnel")
    parser.add_argument("--since", default="", help="Git SHA; scan funnels changed since that commit")
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args()
    root = Path(args.root).resolve()
    slugs = None if args.all or blank_sha(args.since) else touched_slugs(root, args.since)
    registry = build_registry(root, slugs)
    destination = root / "registry" / "conversion-status.json"
    write_registry(destination, registry)
    print(f"Scanned {len(registry['funnels'])} funnel(s) into {destination}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
