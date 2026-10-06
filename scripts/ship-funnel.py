#!/usr/bin/env python3
"""Ingest a dropped funnel folder, fill required files, then commit and push."""

from __future__ import annotations

import argparse
import html
import importlib.util
import json
import os
import re
import shlex
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
FUNNELS = ROOT / "funnels"
SKIP_ROOT_DIRS = {
    ".cursor",
    ".git",
    ".github",
    "_site",
    "funnels",
    "registry",
    "rules",
    "scripts",
    "shared",
}

SLUG_RE = re.compile(r"[^a-z0-9]+")
BOOTSTRAP_ANY = re.compile(
    r"""<script\b[^>]*\bsrc\s*=\s*['"][^'"]*bootstrap\.js['"][^>]*>\s*</script>""",
    re.I,
)
BOOTSTRAP_CANONICAL = re.compile(
    r"""<script\b[^>]*\bsrc\s*=\s*['"]/shared/bootstrap\.js['"][^>]*>""",
    re.I,
)
STYLE_TAG = re.compile(r"""<link\b[^>]*\bhref\s*=\s*['"]style\.css['"]""", re.I)
APP_TAG = re.compile(r"""<script\b[^>]*\bsrc\s*=\s*['"]app\.js['"]""", re.I)
TITLE_RE = re.compile(r"<title\b[^>]*>\s*(.*?)\s*</title>", re.I | re.S)
DESC_RE = re.compile(
    r"""<meta\b[^>]*\bname\s*=\s*['"]description['"][^>]*\bcontent\s*=\s*['"](.*?)['"]""",
    re.I,
)
H1_RE = re.compile(r"<h1\b[^>]*>\s*(.*?)\s*</h1>", re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")
CONVERSION_MARK = "data-aihive-conversions"

EVENT_CHECKS = (
    ("form_submit", re.compile(r"<form\b", re.I)),
    ("cta_click", re.compile(r"data-cta\b|class\s*=\s*['\"][^'\"]*\bcta\b", re.I)),
    ("whatsapp_click", re.compile(r"wa\.me/|api\.whatsapp\.com|whatsapp\.com/send|whatsapp:", re.I)),
    ("calendly_click", re.compile(r"calendly\.com", re.I)),
    ("phone_click", re.compile(r"tel:", re.I)),
    ("email_click", re.compile(r"mailto:", re.I)),
)

DEFAULT_CHANNELS = {
    "whatsapp": "https://wa.me/15550000000",
    "phone": "tel:+15550000000",
    "email": "mailto:hello@theaihive.space",
    "calendly": "https://calendly.com/theaihive/strategy-session",
}

VENDOR_BLOCKS = (
    re.compile(r"<!--\s*Google Tag Manager\s*-->[\s\S]*?<!--\s*End Google Tag Manager\s*-->", re.I),
    re.compile(r"<!--\s*Google Tag Manager \(noscript\)\s*-->[\s\S]*?<!--\s*End Google Tag Manager \(noscript\)\s*-->", re.I),
    re.compile(r"<!--\s*Meta Pixel[\s\S]*?</script>", re.I),
    re.compile(r"<noscript>\s*<(?:iframe|img)[^>]*(?:googletagmanager\.com|facebook\.com/tr)[\s\S]*?</noscript>", re.I),
    re.compile(
        r"<script\b[^>]*src=['\"][^'\"]*(?:googletagmanager\.com|connect\.facebook\.net|clarity\.ms|snap\.licdn\.com)[^'\"]*['\"][^>]*>\s*</script>",
        re.I,
    ),
    re.compile(r"<script\b[^>]*>[\s\S]{0,4000}(?:googletagmanager\.com|connect\.facebook\.net|clarity\.ms/tag)[\s\S]{0,2000}?</script>", re.I),
)

BOOTSTRAP_SNIPPET = '<script src="/shared/bootstrap.js"></script>'
STYLE_SNIPPET = '<link rel="stylesheet" href="style.css">'
APP_SNIPPET = '<script src="app.js"></script>'

STARTER_JS = '(function () {\n  "use strict";\n})();\n'

STARTER_CSS = """:root {
  --field: #e4edf1;
  --ink: #12202b;
  --ink-soft: #243848;
  --yellow: #ffcc00;
  --display: "Familjen Grotesk", "Avenir Next", "Segoe UI", sans-serif;
  --body: "Atkinson Hyperlegible", "Segoe UI", sans-serif;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--field);
  color: var(--ink);
  font-family: var(--body);
  font-size: 1.125rem;
  line-height: 1.5;
}

a { color: inherit; }

:focus-visible {
  outline: 2px solid var(--ink);
  outline-offset: 3px;
}

main {
  width: min(44rem, calc(100% - 2.5rem));
  margin: 0 auto;
  padding: 2rem 0 4rem;
}

h1 {
  margin: 0;
  font-family: var(--display);
  font-size: clamp(2.4rem, 6vw, 4rem);
  letter-spacing: -0.03em;
  line-height: 0.95;
}

label { display: block; margin: 1rem 0 0.3rem; font-weight: 700; }

input, textarea {
  width: 100%;
  border: 2px solid var(--ink);
  border-radius: 0;
  padding: 0.55rem 0.65rem;
  font: inherit;
}

button, .cta {
  display: inline-flex;
  align-items: center;
  min-height: 48px;
  margin-top: 1rem;
  padding: 0.4rem 0.9rem;
  border: 0;
  background: var(--ink);
  color: var(--yellow);
  font-family: var(--display);
  font-weight: 700;
  cursor: pointer;
  text-decoration: none;
}
"""


def log(message: str) -> None:
    print(message)


def slugify(name: str) -> str:
    slug = SLUG_RE.sub("-", name.strip().lower()).strip("-")
    return slug


def plain(text: str) -> str:
    return re.sub(r"\s+", " ", TAG_RE.sub("", text or "")).strip()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def write_if_missing(path: Path, contents: str) -> bool:
    if path.exists():
        return False
    path.write_text(contents, encoding="utf-8")
    return True


def first_html(folder: Path) -> Path | None:
    index = folder / "index.html"
    if index.is_file():
        return index
    pages = sorted(folder.glob("*.html"))
    return pages[0] if pages else None


def starter_html(title: str, description: str) -> str:
    safe_title = html.escape(title)
    safe_description = html.escape(description, quote=True)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_title}</title>
  <meta name="description" content="{safe_description}">
  {STYLE_SNIPPET}
</head>
<body>
  <main>
    <h1>{safe_title}</h1>
    <p>{html.escape(description)}</p>
    <p><a class="cta" href="#request">Request it</a></p>
    <form id="request" name="{slugify(title)}" novalidate>
      <label for="email">Email</label>
      <input id="email" name="email" type="email" autocomplete="email" required>
      <button type="submit">Send</button>
    </form>
  </main>
  {BOOTSTRAP_SNIPPET}
  {APP_SNIPPET}
</body>
</html>
"""


def strip_vendor_loaders(html: str) -> str:
    updated = html
    for pattern in VENDOR_BLOCKS:
        updated = pattern.sub("", updated)
    return updated


def insert_before(html: str, marker: str, snippet: str) -> str:
    index = html.lower().rfind(marker.lower())
    if index == -1:
        return html.rstrip() + "\n" + snippet + "\n"
    return html[:index] + snippet + "\n" + html[index:]
    index = html.lower().rfind(marker.lower())
    if index == -1:
        return html.rstrip() + "\n" + snippet + "\n"
    return html[:index] + snippet + "\n" + html[index:]


def wrap_fragment(html: str, title: str, description: str) -> str:
    lower = html.lower()
    if "<html" in lower:
        return html
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"  <title>{title}</title>\n"
        f'  <meta name="description" content="{description}">\n'
        "</head>\n"
        "<body>\n"
        f"{html.rstrip()}\n"
        "</body>\n"
        "</html>\n"
    )


def ensure_html(folder: Path, slug: str) -> str:
    page = first_html(folder)
    title = slug.replace("-", " ").title() + " — AIHive"
    description = "One page for one offer, published by AIHive Funnels."
    if page is None:
        (folder / "index.html").write_text(starter_html(title, description), encoding="utf-8")
        log(f"  created index.html")
        return read_text(folder / "index.html")

    if page.name != "index.html":
        target = folder / "index.html"
        if target.exists():
            raise SystemExit(f"ship: {folder} has {page.name} and index.html")
        page.rename(target)
        log(f"  renamed {page.name} -> index.html")
        page = target

    html = wrap_fragment(read_text(page), title, description)
    cleaned = strip_vendor_loaders(html)
    if cleaned != html:
        log("  removed vendor tracking loaders")
        html = cleaned
    found_title = plain(TITLE_RE.search(html).group(1) if TITLE_RE.search(html) else "")
    found_h1 = plain(H1_RE.search(html).group(1) if H1_RE.search(html) else "")
    found_desc = DESC_RE.search(html).group(1).strip() if DESC_RE.search(html) else ""
    title = found_title or found_h1 or title
    description = found_desc or description

    if BOOTSTRAP_ANY.search(html) and not BOOTSTRAP_CANONICAL.search(html):
        html = BOOTSTRAP_ANY.sub(BOOTSTRAP_SNIPPET, html, count=1)
        log("  pointed bootstrap.js at /shared/bootstrap.js")
    if not BOOTSTRAP_CANONICAL.search(html):
        html = insert_before(html, "</body>", "  " + BOOTSTRAP_SNIPPET)
        log("  injected /shared/bootstrap.js")
    if not STYLE_TAG.search(html):
        html = insert_before(html, "</head>", "  " + STYLE_SNIPPET)
        log("  linked style.css")
    if not APP_TAG.search(html):
        html = insert_before(html, "</body>", "  " + APP_SNIPPET)
        log("  loaded app.js")

    page.write_text(html, encoding="utf-8")
    return html


def ensure_meta(folder: Path, slug: str, html: str) -> None:
    title = plain(TITLE_RE.search(html).group(1) if TITLE_RE.search(html) else "") or (
        slug.replace("-", " ").title() + " — AIHive"
    )
    description = DESC_RE.search(html).group(1).strip() if DESC_RE.search(html) else (
        "One page for one offer, published by AIHive Funnels."
    )
    path = folder / "funnel.json"
    if path.is_file():
        try:
            meta = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            raise SystemExit(f"ship: {path} is not valid JSON")
        meta.setdefault("title", title)
        meta.setdefault("description", description)
        meta.setdefault("image", "")
        meta.setdefault("formAction", "")
        meta.setdefault("formMethod", "POST")
    else:
        meta = {
            "title": title,
            "description": description,
            "image": "",
            "formAction": "",
            "formMethod": "POST",
        }
        log("  created funnel.json")
    path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta


def missing_events(html: str) -> list[str]:
    return [name for name, pattern in EVENT_CHECKS if not pattern.search(html)]


def conversion_block(missing: list[str], contacts: dict) -> str:
    parts = ['<aside class="aihive-conversions" data-aihive-conversions>']
    if "cta_click" in missing:
        parts.append('  <a class="cta" href="#aihive-request">Request this</a>')
    if "form_submit" in missing:
        parts.append(
            '  <form id="aihive-request" name="aihive-request" novalidate>'
            '<label for="aihive-email">Email</label>'
            '<input id="aihive-email" name="email" type="email" autocomplete="email" required>'
            '<button type="submit">Send</button></form>'
        )
    if "whatsapp_click" in missing:
        parts.append(f'  <a href="{html.escape(contacts["whatsapp"], quote=True)}" rel="noopener noreferrer">WhatsApp</a>')
    if "phone_click" in missing:
        parts.append(f'  <a href="{html.escape(contacts["phone"], quote=True)}">Call</a>')
    if "email_click" in missing:
        parts.append(f'  <a href="{html.escape(contacts["email"], quote=True)}">Email</a>')
    if "calendly_click" in missing:
        parts.append(f'  <a href="{html.escape(contacts["calendly"], quote=True)}" rel="noopener noreferrer">Calendar</a>')
    parts.append("</aside>")
    return "\n".join(parts)


def ensure_conversions(folder: Path, html: str) -> str:
    missing = missing_events(html)
    if not missing:
        return html
    if CONVERSION_MARK in html:
        html = re.sub(
            r'<aside\b[^>]*data-aihive-conversions[\s\S]*?</aside>',
            "",
            html,
            count=1,
            flags=re.I,
        )
        missing = missing_events(html)
        if not missing:
            (folder / "index.html").write_text(html, encoding="utf-8")
            return html
    meta = {}
    meta_path = folder / "funnel.json"
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            meta = {}
    contacts = {
        key: str(meta.get(key) or DEFAULT_CHANNELS[key])
        for key in DEFAULT_CHANNELS
    }
    html = insert_before(html, "</body>", conversion_block(missing, contacts))
    (folder / "index.html").write_text(html, encoding="utf-8")
    log("  added conversion events: " + ", ".join(missing))
    return html


def setup_funnel(folder: Path) -> str:
    slug = folder.name
    log(f"Setting up funnels/{slug}")
    html = ensure_html(folder, slug)
    if write_if_missing(folder / "app.js", STARTER_JS):
        log("  created app.js")
    if write_if_missing(folder / "style.css", STARTER_CSS):
        log("  created style.css")
    ensure_meta(folder, slug, html)
    html = read_text(folder / "index.html")
    ensure_conversions(folder, html)
    return slug


def destination_for(source: Path, slug: str) -> Path:
    target = FUNNELS / slug
    if source.resolve() == target.resolve():
        return target
    if target.exists():
        raise SystemExit(f"ship: funnels/{slug} already exists")
    return target


def ingest(source: Path, slug_override: str = "") -> str:
    source = source.resolve()
    if not source.is_dir():
        raise SystemExit(f"ship: {source} is not a folder")
    slug = slug_override or slugify(source.name)
    if not slug:
        raise SystemExit(f"ship: cannot make a URL from {source.name}")
    FUNNELS.mkdir(exist_ok=True)
    target = destination_for(source, slug)
    if source.resolve() != target.resolve():
        if source.parent.resolve() == FUNNELS.resolve() and source.name != slug:
            source.rename(target)
            log(f"Renamed funnels/{source.name} -> funnels/{slug}")
        else:
            shutil.move(str(source), str(target))
            log(f"Moved {source} -> funnels/{slug}")
    return setup_funnel(target)


def dropped_root_folders() -> list[Path]:
    found = []
    for path in sorted(ROOT.iterdir()):
        if not path.is_dir() or path.name in SKIP_ROOT_DIRS or path.name.startswith("."):
            continue
        found.append(path)
    return found


def load_script(filename: str):
    path = ROOT / "scripts" / filename
    name = filename.replace("-", "_").removesuffix(".py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_python(script: str, *args: str) -> None:
    module = load_script(script)
    previous = sys.argv
    sys.argv = [script, *args]
    try:
        code = module.main()
    finally:
        sys.argv = previous
    if code:
        raise SystemExit(code)


def run_cmd(args: list[str]) -> SimpleNamespace:
    with tempfile.TemporaryDirectory(prefix="aihive-ship-") as tmp:
        stdout_path = Path(tmp) / "stdout"
        stderr_path = Path(tmp) / "stderr"
        quoted = " ".join(shlex.quote(part) for part in args)
        command = (
            f"cd {shlex.quote(str(ROOT))} && {quoted} "
            f">{shlex.quote(str(stdout_path))} 2>{shlex.quote(str(stderr_path))}"
        )
        status = os.system(command)
        if os.WIFEXITED(status):
            code = os.WEXITSTATUS(status)
        elif os.WIFSIGNALED(status):
            code = 128 + os.WTERMSIG(status)
        else:
            code = 1
        return SimpleNamespace(
            returncode=code,
            stdout=stdout_path.read_text(encoding="utf-8") if stdout_path.exists() else "",
            stderr=stderr_path.read_text(encoding="utf-8") if stderr_path.exists() else "",
        )


def git(*args: str, check: bool = True) -> SimpleNamespace:
    result = run_cmd(["git", *args])
    if check and result.returncode != 0:
        sys.stderr.write(result.stderr or result.stdout)
        raise SystemExit(result.returncode)
    return result


def git_available() -> bool:
    return shutil.which("git") is not None


def in_repo() -> bool:
    result = git("rev-parse", "--is-inside-work-tree", check=False)
    return result.returncode == 0 and result.stdout.strip() == "true"


def ensure_repo() -> None:
    if in_repo():
        return
    log("Initializing git repository on branch main")
    git("init", "-b", "main")


def current_branch() -> str:
    result = git("rev-parse", "--abbrev-ref", "HEAD")
    return result.stdout.strip() or "main"


def remote_url() -> str:
    result = git("remote", "get-url", "origin", check=False)
    return result.stdout.strip()


def commit_and_push(slugs: list[str], push: bool) -> None:
    if not git_available():
        raise SystemExit("ship: git is not installed")
    ensure_repo()
    git("add", "-A")
    status = git("status", "--porcelain")
    if not status.stdout.strip():
        log("Nothing new to commit")
    else:
        if len(slugs) == 1:
            message = f"Publish funnel {slugs[0]}"
        elif slugs:
            message = "Publish funnels: " + ", ".join(slugs)
        else:
            message = "Publish AIHive Funnels"
        commit = git("commit", "-m", message, check=False)
        if commit.returncode != 0:
            sys.stderr.write(commit.stderr or commit.stdout)
            raise SystemExit(commit.returncode)
        log(f"Committed: {message}")

    if not push:
        log("Skipped git push")
        return

    origin = remote_url()
    if not origin:
        log("No git remote named origin. Add one, then run ./ship again:")
        log("  git remote add origin git@github.com:<owner>/aihive-funnels.git")
        log("  git push -u origin main")
        return

    branch = current_branch()
    log(f"Pushing {branch} to origin")
    pushed = git("push", "-u", "origin", branch, check=False)
    if pushed.returncode != 0:
        sys.stderr.write(pushed.stderr or pushed.stdout)
        raise SystemExit(pushed.returncode)
    log("Pushed. GitHub Actions will deploy Pages from main.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Set up a dropped funnel folder and push it to GitHub"
    )
    parser.add_argument(
        "folder",
        nargs="?",
        default="",
        help="Dropped folder. If omitted, ingest extra folders at the repo root, then set up every funnel.",
    )
    parser.add_argument("--slug", default="", help="Override the published folder name")
    parser.add_argument("--no-push", action="store_true", help="Commit locally and skip git push")
    parser.add_argument("--no-git", action="store_true", help="Set up files only")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    slugs: list[str] = []

    if args.folder:
        slugs.append(ingest(Path(args.folder).expanduser(), args.slug))
    else:
        if args.slug:
            raise SystemExit("ship: --slug needs a folder path")
        for dropped in dropped_root_folders():
            slugs.append(ingest(dropped))
        folders = [
            path
            for path in FUNNELS.iterdir()
            if FUNNELS.is_dir() and path.is_dir() and not path.name.startswith(".")
        ]
        if not folders:
            raise SystemExit("ship: drop a folder here, or pass its path: ./ship path/to/folder")
        for folder in sorted(folders):
            wanted = slugify(folder.name)
            if wanted != folder.name:
                slugs.append(ingest(folder, wanted))
                continue
            setup_funnel(folder)
            if folder.name not in slugs:
                slugs.append(folder.name)

    run_python("validate-protection.py")
    run_python("audit-funnels.py", "--all")
    run_python("assemble-site.py")

    if not args.no_git:
        commit_and_push(slugs, push=not args.no_push)

    live = "https://connect.theaihive.space"
    for slug in slugs:
        log(f"Live path: {live}/{slug}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
