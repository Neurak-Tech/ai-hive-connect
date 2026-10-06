#!/usr/bin/env python3
"""Block funnel changes that drop tracking or rewrite analytics IDs."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZERO = "0" * 40

BOOTSTRAP_TAG = re.compile(
    r"""<script\b[^>]*\bsrc\s*=\s*['"]/shared/bootstrap\.js['"][^>]*>""",
    re.I,
)
STYLE_TAG = re.compile(r"""<link\b[^>]*\bhref\s*=\s*['"]style\.css['"]""", re.I)
APP_TAG = re.compile(r"""<script\b[^>]*\bsrc\s*=\s*['"]app\.js['"]""", re.I)


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"protection: missing {path}")
    except json.JSONDecodeError as error:
        raise SystemExit(f"protection: {path} is not valid JSON ({error})")


def load_policy(root: Path) -> dict:
    return load_json(root / "rules" / "policy.json")


def locked_view(config: dict) -> dict:
    return {
        "analytics": config.get("analytics") or {},
        "linkedinConversions": config.get("linkedinConversions") or {},
    }


def changed_keys(left: dict, right: dict, prefix: str = "") -> list[str]:
    keys = set(left) | set(right)
    changes = []
    for key in sorted(keys):
        path = f"{prefix}{key}"
        before = left.get(key)
        after = right.get(key)
        if isinstance(before, dict) and isinstance(after, dict):
            changes.extend(changed_keys(before, after, path + "."))
        elif before != after:
            changes.append(path)
    return changes


def read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def blank_sha(value: str) -> bool:
    text = (value or "").strip().lower()
    return text in {"", ZERO, "null", "none"}


def git_show(root: Path, sha: str, relative: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{sha}:{relative}"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def commit_message_text(root: Path, base: str, head: str) -> str:
    result = subprocess.run(
        ["git", "log", "--format=%B%x1e", f"{base}..{head}"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def check_runtime(root: Path, policy: dict) -> list[str]:
    errors = []
    bootstrap = read_text(root / policy["bootstrap_file"])
    if not bootstrap:
        errors.append(f"{policy['bootstrap_file']} is missing")
    else:
        for name in policy["injections"]:
            if f'"{name}"' not in bootstrap and f"'{name}'" not in bootstrap:
                errors.append(f"{policy['bootstrap_file']} no longer loads {name}")

    required_markers = (
        (policy["pixel_file"], policy["pixel_markers"]),
        (policy["analytics_file"], policy["analytics_markers"]),
        (policy["tracker_file"], policy["tracker_markers"]),
    )
    for relative, markers in required_markers:
        text = read_text(root / relative)
        if not text:
            errors.append(f"{relative} is missing")
            continue
        for marker in markers:
            if marker not in text:
                errors.append(f"{relative} is missing required marker {marker}")
    return errors


def check_pages(root: Path, policy: dict) -> list[str]:
    errors = []
    for relative in policy.get("redirect_pages") or []:
        html = read_text(root / relative)
        if not html:
            errors.append(f"{relative} is missing")
        elif "theaihive.io" not in html.lower():
            errors.append(f"{relative} must redirect to theaihive.io")

    for relative in policy["root_pages"]:
        html = read_text(root / relative)
        if not html:
            errors.append(f"{relative} is missing")
        elif not BOOTSTRAP_TAG.search(html):
            errors.append(f"{relative} must include {policy['bootstrap_src']}")

    funnels = root / "funnels"
    if not funnels.is_dir():
        return errors + ["funnels/ is missing"]

    for folder in sorted(path for path in funnels.iterdir() if path.is_dir() and not path.name.startswith(".")):
        for name in policy["funnel_files"]:
            if not (folder / name).is_file():
                errors.append(f"funnels/{folder.name}/{name} is missing")
        html = read_text(folder / "index.html")
        label = f"funnels/{folder.name}/index.html"
        if html and not BOOTSTRAP_TAG.search(html):
            errors.append(f"{label} must include {policy['bootstrap_src']}")
        if html and not STYLE_TAG.search(html):
            errors.append(f"{label} must link style.css")
        if html and not APP_TAG.search(html):
            errors.append(f"{label} must load app.js")
    return errors


def check_bypass(root: Path, policy: dict) -> list[str]:
    errors = []
    patterns = [re.compile(pattern) for pattern in policy["bypass_patterns"]]
    files = [root / relative for relative in policy["root_pages"]]
    funnels = root / "funnels"
    if funnels.is_dir():
        files.extend(path for path in funnels.rglob("*") if path.suffix in {".html", ".js", ".json"})
    for path in files:
        text = read_text(path)
        if not text:
            continue
        for pattern in patterns:
            if pattern.search(text):
                relative = path.relative_to(root)
                errors.append(f"{relative} bypasses central tracking ({pattern.pattern})")
    return errors


def check_lock(root: Path, policy: dict) -> list[str]:
    config = locked_view(load_json(root / policy["config_file"]))
    lock = locked_view(load_json(root / policy["lock_file"]))
    changes = changed_keys(lock, config)
    if not changes:
        return []
    joined = ", ".join(changes)
    return [f"{policy['config_file']} does not match {policy['lock_file']} ({joined})"]


def check_history(root: Path, policy: dict, base_ids: dict | None, message: str) -> list[str]:
    if base_ids is None:
        return []
    current = locked_view(load_json(root / policy["config_file"]))
    changes = changed_keys(base_ids, current)
    if not changes:
        return []
    trailer = policy["override_trailer"]
    if trailer in message:
        return []
    joined = ", ".join(changes)
    return [
        f"analytics IDs changed ({joined}). Update {policy['lock_file']} in the same commit "
        f"and include this trailer in the commit message: {trailer}"
    ]


def protection_errors(root: Path, base_ids: dict | None = None, message: str = "") -> list[str]:
    policy = load_policy(root)
    errors = []
    errors.extend(check_runtime(root, policy))
    errors.extend(check_pages(root, policy))
    errors.extend(check_bypass(root, policy))
    errors.extend(check_lock(root, policy))
    errors.extend(check_history(root, policy, base_ids, message))
    return errors


def base_ids_from_git(root: Path, base: str) -> dict | None:
    if blank_sha(base):
        return None
    policy = load_policy(root)
    raw = git_show(root, base, policy["config_file"])
    if raw is None:
        return None
    return locked_view(json.loads(raw))


def export_index(root: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "checkout-index", "-a", "-f", f"--prefix={destination}/"],
        cwd=root,
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AIHive funnel protection rules")
    parser.add_argument("--base", default="", help="Base SHA for the analytics ID comparison")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--staged", action="store_true", help="Validate the git index")
    parser.add_argument("--message-file", default="", help="Commit message path, used with --staged")
    parser.add_argument("--root", default="")
    args = parser.parse_args()

    if args.staged:
        with tempfile.TemporaryDirectory(prefix="aihive-index-") as tmp:
            snapshot = Path(tmp)
            export_index(ROOT, snapshot)
            message = ""
            if args.message_file:
                message = Path(args.message_file).read_text(encoding="utf-8")
            previous = None
            raw = git_show(ROOT, "HEAD", "shared/config.json")
            if raw is not None:
                previous = locked_view(json.loads(raw))
            errors = protection_errors(snapshot, previous, message)
    else:
        root = Path(args.root).resolve() if args.root else ROOT
        message = ""
        base_ids = None
        if not args.root and not blank_sha(args.base):
            base_ids = base_ids_from_git(root, args.base)
            head = args.head or "HEAD"
            message = commit_message_text(root, args.base, head)
        errors = protection_errors(root, base_ids, message)

    if errors:
        for error in errors:
            print(f"protection: {error}", file=sys.stderr)
        return 1
    print("protection: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
