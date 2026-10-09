#!/usr/bin/env python3
"""Checks every plugin folder's locale files against its en_us.json.

    python3 scripts/validate.py            check everything
    python3 scripts/validate.py --fix      also rewrite each manifest.json to match its folder

Errors fail the check. Missing translations are only reported: a key a locale
doesn't have falls back to English in game.
"""
import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODE = re.compile(r"^[a-z]{2,3}_[a-z]{2,4}$")
TAG = re.compile(r"<[^<>]+>")

errors = []
notes = []


def error(path, message):
    errors.append(f"{path.relative_to(ROOT)}: {message}")


def load(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        error(path, f"not valid UTF-8 JSON ({e})")
        return None
    if not isinstance(data, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in data.items()):
        error(path, "must be one flat object of string keys to string values")
        return None
    return data


def check_plugin(folder, fix):
    english_path = folder / "en_us.json"
    if not english_path.exists():
        error(folder, "has no en_us.json, the source every other locale is checked against")
        return
    english = load(english_path)
    if english is None:
        return

    codes = []
    for path in sorted(folder.glob("*.json")):
        if path.name == "manifest.json":
            continue
        code = path.stem
        if not CODE.match(code):
            error(path, "file name must be a lowercase locale code like fr_fr.json")
            continue
        codes.append(code)
        if code == "en_us":
            continue

        data = load(path)
        if data is None:
            continue
        if not data.get("locale.display_name", "").strip():
            error(path, 'needs "locale.display_name", the language\'s own name (e.g. "Français")')

        for key, value in data.items():
            if key not in english:
                error(path, f'"{key}" is not a key in en_us.json (typo, or a key that was removed?)')
                continue
            if key.startswith("locale."):
                continue
            source = english[key]
            if collections.Counter(TAG.findall(source)) != collections.Counter(TAG.findall(value)):
                error(path, f'"{key}" must keep exactly the tags of the English text: {TAG.findall(source)}')
            if source.count("%s") != value.count("%s"):
                error(path, f'"{key}" must keep the same number of %s as the English text')

        missing = [k for k in english if k not in data and not k.startswith("locale.")]
        if missing:
            notes.append(f"{path.relative_to(ROOT)}: {len(missing)} key(s) not translated yet, shown in English")

    manifest_path = folder / "manifest.json"
    expected = {code: f"{code}.json" for code in codes}
    current = None
    if manifest_path.exists():
        current = load(manifest_path)
    if current != expected:
        if fix:
            manifest_path.write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
            notes.append(f"{manifest_path.relative_to(ROOT)}: rewritten")
        else:
            error(manifest_path, "does not list exactly this folder's locale files; run scripts/validate.py --fix")


def main():
    fix = "--fix" in sys.argv
    plugins = [p for p in sorted(ROOT.iterdir()) if p.is_dir() and not p.name.startswith(".") and p.name != "scripts"]
    for folder in plugins:
        check_plugin(folder, fix)
    for note in notes:
        print(f"note: {note}")
    for message in errors:
        print(f"error: {message}")
    print(f"{len(plugins)} plugin(s), {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
