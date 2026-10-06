#!/usr/bin/env python3
"""Copy funnels to the domain root and publish the shared runtime."""

from __future__ import annotations

import html
import json
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "_site"

SHARED_FILES = (
    "bootstrap.js",
    "meta.js",
    "analytics.js",
    "pixels.js",
    "conversion-tracker.js",
    "config.json",
    "directory.css",
    "directory.js",
    "mark.svg",
)

TITLE_RE = re.compile(r"<title\b[^>]*>.*?</title>", re.I | re.S)
CANONICAL_RE = re.compile(
    r"""<link\b[^>]*\brel\s*=\s*['"]canonical['"][^>]*>""",
    re.I,
)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def meta_pattern(attribute: str, key: str) -> re.Pattern[str]:
    return re.compile(
        rf"""<meta\b[^>]*\b{attribute}\s*=\s*['"]{re.escape(key)}['"][^>]*>""",
        re.I,
    )


def upsert_meta(document: str, attribute: str, key: str, content: str) -> str:
    tag = f'<meta {attribute}="{html.escape(key, quote=True)}" content="{html.escape(content, quote=True)}">'
    pattern = meta_pattern(attribute, key)
    if pattern.search(document):
        return pattern.sub(tag, document, count=1)
    return document.replace("</head>", tag + "\n</head>", 1)


def upsert_title(document: str, title: str) -> str:
    tag = f"<title>{html.escape(title)}</title>"
    if TITLE_RE.search(document):
        return TITLE_RE.sub(tag, document, count=1)
    return document.replace("</head>", tag + "\n</head>", 1)


def upsert_canonical(document: str, href: str) -> str:
    tag = f'<link rel="canonical" href="{html.escape(href, quote=True)}">'
    if CANONICAL_RE.search(document):
        return CANONICAL_RE.sub(tag, document, count=1)
    return document.replace("</head>", tag + "\n</head>", 1)


def existing_title(document: str) -> str:
    match = TITLE_RE.search(document)
    if not match:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", match.group(0))).strip()


def existing_description(document: str) -> str:
    match = meta_pattern("name", "description").search(document)
    if not match:
        return ""
    content = re.search(r"""content\s*=\s*['"](.*?)['"]""", match.group(0), re.I)
    return content.group(1).strip() if content else ""


def choose(*values: str) -> str:
    for value in values:
        text = (value or "").strip()
        if text:
            return text
    return ""


def apply_meta(document: str, title: str, description: str, canonical: str, site: dict, image: str, robots: str = "") -> str:
    updated = upsert_title(document, title)
    updated = upsert_meta(updated, "name", "description", description)
    if robots:
        updated = upsert_meta(updated, "name", "robots", robots)
    if canonical:
        updated = upsert_canonical(updated, canonical)
        updated = upsert_meta(updated, "property", "og:url", canonical)
    updated = upsert_meta(updated, "property", "og:title", title)
    updated = upsert_meta(updated, "property", "og:description", description)
    updated = upsert_meta(updated, "property", "og:type", "website")
    updated = upsert_meta(updated, "property", "og:site_name", site.get("name") or "AIHive")
    updated = upsert_meta(updated, "property", "og:locale", site.get("locale") or "en_US")
    updated = upsert_meta(updated, "name", "twitter:title", title)
    updated = upsert_meta(updated, "name", "twitter:description", description)
    if site.get("twitter"):
        updated = upsert_meta(updated, "name", "twitter:site", site["twitter"])
    if image:
        updated = upsert_meta(updated, "property", "og:image", image)
        updated = upsert_meta(updated, "name", "twitter:image", image)
        updated = upsert_meta(updated, "name", "twitter:card", "summary_large_image")
    else:
        updated = upsert_meta(updated, "name", "twitter:card", "summary")
    return updated


def funnel_cards(root: Path, site: dict) -> list[dict]:
    cards = []
    base = root / "funnels"
    if not base.is_dir():
        return cards
    for folder in sorted(path for path in base.iterdir() if path.is_dir() and not path.name.startswith(".")):
        if not (folder / "index.html").is_file():
            continue
        meta = {}
        meta_path = folder / "funnel.json"
        if meta_path.is_file():
            meta = read_json(meta_path)
        document = (folder / "index.html").read_text(encoding="utf-8")
        title = choose(meta.get("title", ""), existing_title(document), site.get("title", ""), folder.name)
        description = choose(meta.get("description", ""), existing_description(document), site.get("description", ""))
        cards.append({"slug": folder.name, "title": title, "description": description, "meta": meta, "html": document})
    return cards


def write_sitemap(path: Path, domain: str, slugs: list[str]) -> None:
    urls = [domain + "/"] + [f"{domain}/{slug}/" for slug in slugs]
    body = "\n".join(f"  <url><loc>{html.escape(url)}</loc></url>" for url in urls)
    path.write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n"
        f"{body}\n"
        "</urlset>\n",
        encoding="utf-8",
    )


def apply_base(text: str, base: str) -> str:
    prefix = (base or "").rstrip("/")
    if not prefix:
        return text
    return text.replace('"/shared/', f'"{prefix}/shared/').replace("'/shared/", f"'{prefix}/shared/")


def pages_base() -> str:
    if (ROOT / "CNAME").is_file():
        return ""
    return str(os.environ.get("PAGES_BASE_PATH") or "").rstrip("/")


def assemble(root: Path = ROOT, destination: Path = SITE) -> int:
    config = read_json(root / "shared" / "config.json")
    site = config.get("site") or {}
    domain = str(site.get("domain") or "").rstrip("/")
    base = pages_base()
    if destination.exists():
        shutil.rmtree(destination)
    shared_out = destination / "shared"
    shared_out.mkdir(parents=True)
    (destination / "registry").mkdir()

    for name in SHARED_FILES:
        shutil.copy2(root / "shared" / name, shared_out / name)
    for name in ("index.html", "404.html", "CNAME", "robots.txt", ".nojekyll"):
        source = root / name
        if source.is_file() or source.name == ".nojekyll":
            shutil.copy2(source, destination / name)

    registry = root / "registry" / "conversion-status.json"
    if registry.is_file():
        shutil.copy2(registry, destination / "registry" / "conversion-status.json")

    cards = funnel_cards(root, site)
    for card in cards:
        target = destination / card["slug"]
        shutil.copytree(root / "funnels" / card["slug"], target)
        meta = card["meta"]
        image = str(meta.get("image") or site.get("image") or "")
        if image and image.startswith("/"):
            image = domain + image
        page = apply_meta(
            (target / "index.html").read_text(encoding="utf-8"),
            card["title"],
            card["description"],
            f"{domain}/{card['slug']}/",
            site,
            image,
        )
        (target / "index.html").write_text(apply_base(page, base), encoding="utf-8")

    home = (destination / "index.html").read_text(encoding="utf-8")
    if "theaihive.io" not in home.lower():
        home_title = choose(existing_title(home), site.get("title", ""))
        home_description = choose(existing_description(home), site.get("description", ""))
        home = apply_meta(
            home,
            home_title,
            home_description,
            "https://theaihive.io/",
            site,
            str(site.get("image") or ""),
        )
    (destination / "index.html").write_text(home, encoding="utf-8")
    missing = (destination / "404.html").read_text(encoding="utf-8")
    (destination / "404.html").write_text(
        apply_base(
            apply_meta(
                missing,
                choose(existing_title(missing), "Route not found"),
                choose(existing_description(missing), site.get("description", "")),
                "",
                site,
                "",
                robots="noindex",
            ),
            base,
        ),
        encoding="utf-8",
    )

    manifest = [{"slug": card["slug"], "title": card["title"], "description": card["description"]} for card in cards]
    (destination / "funnels.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    write_sitemap(destination / "sitemap.xml", domain, [card["slug"] for card in cards])
    print(f"Assembled {len(cards)} funnel(s) into {destination}")
    return len(cards)


def main() -> int:
    assemble()
    return 0


if __name__ == "__main__":
    sys.exit(main())
