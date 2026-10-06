#!/usr/bin/env python3
"""Protection and audit checks against a copy of this repository."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_script(filename: str):
    path = ROOT / "scripts" / filename
    spec = importlib.util.spec_from_file_location(filename.replace("-", "_").removesuffix(".py"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit_funnels = load_script("audit-funnels.py")
validate_protection = load_script("validate-protection.py")


def copy_repo(destination: Path) -> None:
    shutil.copytree(
        ROOT,
        destination,
        ignore=shutil.ignore_patterns("_site", ".git", "__pycache__"),
        dirs_exist_ok=True,
    )


def assert_ok(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    errors = validate_protection.protection_errors(ROOT)
    assert_ok(errors == [], "clean tree failed:\n" + "\n".join(errors))

    registry = audit_funnels.build_registry(ROOT, None)
    sample = next(item for item in registry["funnels"] if item["funnel"] == "strategy-session")
    expected = [
        "form_submit",
        "cta_click",
        "whatsapp_click",
        "calendly_click",
        "phone_click",
        "email_click",
    ]
    assert_ok(sample["status"] == "tracked", f"unexpected status {sample['status']}")
    assert_ok(sample["events"] == expected, f"unexpected events {sample['events']}")

    with tempfile.TemporaryDirectory(prefix="aihive-rules-") as tmp:
        root = Path(tmp) / "repo"
        copy_repo(root)
        original = json.loads((root / "shared" / "config.json").read_text(encoding="utf-8"))
        base_ids = validate_protection.locked_view(original)

        page = root / "funnels" / "strategy-session" / "index.html"
        page.write_text(page.read_text(encoding="utf-8").replace("/shared/bootstrap.js", "/tracking.js"), encoding="utf-8")
        broken = validate_protection.protection_errors(root)
        assert_ok(any("bootstrap.js" in error for error in broken), "missing bootstrap was allowed")

        copy_repo(root)
        config_path = root / "shared" / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["analytics"]["ga4"] = "G-TEST1234"
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        drifted = validate_protection.protection_errors(root, base_ids, "")
        assert_ok(any("does not match" in error for error in drifted), "lock drift was allowed")
        assert_ok(any("analytics IDs changed" in error for error in drifted), "ID edit was allowed")

        lock_path = root / "rules" / "analytics-lock.json"
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        lock["analytics"]["ga4"] = "G-TEST1234"
        lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
        locked = validate_protection.protection_errors(root, base_ids, "")
        assert_ok(any("analytics IDs changed" in error for error in locked), "trailer was not required")
        approved = validate_protection.protection_errors(
            root,
            base_ids,
            "Update measurement ids\n\nAnalytics-Lock-Update: approved\n",
        )
        assert_ok(approved == [], "approved ID update failed:\n" + "\n".join(approved))

        copy_repo(root)
        script = root / "funnels" / "strategy-session" / "app.js"
        script.write_text(script.read_text(encoding="utf-8") + "\nwindow.AIHIVE_DISABLE_TRACKING = true;\n", encoding="utf-8")
        bypassed = validate_protection.protection_errors(root)
        assert_ok(any("bypasses central tracking" in error for error in bypassed), "bypass was allowed")

        copy_repo(root)
        pixels = root / "shared" / "pixels.js"
        pixels.write_text(pixels.read_text(encoding="utf-8").replace("fbevents.js", "removed.js"), encoding="utf-8")
        gutted = validate_protection.protection_errors(root)
        assert_ok(any("fbevents.js" in error for error in gutted), "pixel removal was allowed")

    print("rules: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
