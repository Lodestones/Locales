#!/usr/bin/env python3
"""Checks every project's locale files against its en_us.json.

    python3 scripts/validate.py          check everything
    python3 scripts/validate.py --fix    also rewrite manifests and reformat files

Errors fail the check. Missing translations are only reported: a key a locale
doesn't have falls back to English in game. Run with --github inside Actions to
get annotations on the pull request and a summary on the run page.
"""
import collections
import json
import os
import re
import sys
from pathlib import Path

# The folder being checked. CI runs the base branch's copy of this script against
# a pull request's files, so the two can live apart.
ROOT = Path(os.environ.get("LOCALES_ROOT") or Path(__file__).resolve().parent.parent).resolve()
CODE = re.compile(r"^[a-z]{2,3}_[a-z]{2,4}$")
TAG = re.compile(r"<[^<>]+>")
# A command as players type it: a slash at the start of the text or after a space,
# quote, bracket or tag. Not the slash inside "and/or" or a URL.
COMMAND = re.compile(r"(?:^|(?<=[\s\"'(\[>]))/[a-z][a-z0-9_-]*")
METADATA = {"locale.display_name", "locale.sort_order", "locale.version"}
# Generous, but stops a value being used to dump something huge into chat.
MAX_LENGTH_FACTOR, MAX_LENGTH_SLACK = 4, 200
MAX_FILE_BYTES = 1_000_000

github = "--github" in sys.argv
fix = "--fix" in sys.argv
errors, notes, summary = [], [], []

# Phrases the plugin matches against what a player types, so they must stay as
# they are in every language. Keyed "<Project folder>/<key>".
literals_path = Path(__file__).resolve().parent / "literals.json"
LITERALS = json.loads(literals_path.read_text(encoding="utf-8")) if literals_path.exists() else {}


def rel(path):
    return path.relative_to(ROOT).as_posix()


def line_of(text, key):
    needle = json.dumps(key, ensure_ascii=False) + ":"
    index = text.find(needle)
    return text.count("\n", 0, index) + 1 if index >= 0 else 1


def error(path, message, line=1):
    errors.append((rel(path), line, message))


def note(message):
    notes.append(message)


def canonical(data):
    return json.dumps(dict(sorted(data.items())), indent=2, ensure_ascii=False) + "\n"


def load(path):
    """The file as (text, data), or (text, None) when it can't be used."""
    raw = path.read_bytes()
    if len(raw) > MAX_FILE_BYTES:
        error(path, f"file is larger than {MAX_FILE_BYTES // 1000} KB")
        return "", None
    if raw.startswith(b"\xef\xbb\xbf"):
        error(path, "starts with a byte order mark; save it as UTF-8 without BOM")
        raw = raw[3:]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        error(path, f"is not valid UTF-8 ({e})")
        return "", None

    duplicates = []

    def pairs(items):
        seen = {}
        for key, value in items:
            if key in seen:
                duplicates.append(key)
            seen[key] = value
        return seen

    try:
        data = json.loads(text, object_pairs_hook=pairs)
    except json.JSONDecodeError as e:
        error(path, f"is not valid JSON: {e.msg}", e.lineno)
        return text, None
    for key in duplicates:
        error(path, f'"{key}" appears more than once', line_of(text, key))
    if not isinstance(data, dict):
        error(path, "must be one JSON object of key to text")
        return text, None
    for key, value in data.items():
        if not isinstance(value, str):
            error(path, f'"{key}" must be a string', line_of(text, key))
    if any(not isinstance(v, str) for v in data.values()):
        return text, None
    return text, data


def check_translation(project, path, text, english, data):
    for key, value in data.items():
        line = line_of(text, key)
        if key not in english:
            error(path, f'"{key}" is not a key in en_us.json (a typo, or a key that was removed?)', line)
            continue
        if key in METADATA:
            continue
        source = english[key]
        if not value.strip() and source.strip():
            error(path, f'"{key}" is empty; leave the key out instead and it will show in English', line)
            continue
        if collections.Counter(TAG.findall(source)) != collections.Counter(TAG.findall(value)):
            error(path, f'"{key}" must keep exactly the tags of the English text: {" ".join(TAG.findall(source)) or "(none)"}', line)
        if source.count("%s") != value.count("%s"):
            error(path, f'"{key}" must keep the same number of %s as the English text ({source.count("%s")})', line)
        if source.count("\n") != value.count("\n"):
            error(path, f'"{key}" must keep the same line breaks as the English text ({source.count(chr(10))})', line)
        lead, trail = len(source) - len(source.lstrip(" ")), len(source) - len(source.rstrip(" "))
        if (len(value) - len(value.lstrip(" "))) != lead or (len(value) - len(value.rstrip(" "))) != trail:
            error(path, f'"{key}" must keep the spaces at the start and end of the English text', line)
        for command in COMMAND.findall(source):
            if command not in value:
                error(path, f'"{key}" must keep the command {command} untranslated', line)
        for phrase in LITERALS.get(f"{project}/{key}", []):
            if phrase in source and phrase not in value:
                error(path, f'"{key}" must keep "{phrase}" exactly as written, the plugin matches it against what players type', line)
        if len(value) > len(source) * MAX_LENGTH_FACTOR + MAX_LENGTH_SLACK:
            error(path, f'"{key}" is far longer than the English text', line)

    if not data.get("locale.display_name", "").strip():
        error(path, 'needs "locale.display_name", the language\'s own name (e.g. "Français")')
    order = data.get("locale.sort_order")
    if order is not None and not order.strip().isdigit():
        error(path, '"locale.sort_order" must be a whole number', line_of(text, "locale.sort_order"))


def check_project(folder):
    project = rel(folder)
    english_path = folder / "en_us.json"
    if not english_path.exists():
        error(folder, "has no en_us.json, the source every other locale is checked against")
        return
    english_text, english = load(english_path)
    if english is None:
        return

    codes, row = [], []
    for path in sorted(folder.glob("*.json")):
        if path.name == "manifest.json":
            continue
        code = path.stem
        if not CODE.match(code):
            error(path, "file name must be a lowercase locale code like fr_fr.json")
            continue
        codes.append(code)
        text, data = (english_text, english) if code == "en_us" else load(path)
        if data is None:
            continue
        if code != "en_us":
            check_translation(project, path, text, english, data)
            missing = [k for k in english if k not in data and k not in METADATA]
            translated = len(english) - len(METADATA & english.keys()) - len(missing)
            row.append(f"{code} {translated}/{len(english) - len(METADATA & english.keys())}")
            if missing:
                note(f"{rel(path)}: {len(missing)} key(s) not translated yet, shown in English")
        if text != canonical(data):
            if fix:
                path.write_text(canonical(data), encoding="utf-8")
                note(f"{rel(path)}: reformatted")
            else:
                error(path, "is not formatted like the other files (keys sorted, 2-space indent); run python3 scripts/validate.py --fix")

    manifest_path = folder / "manifest.json"
    expected = {code: f"{code}.json" for code in codes}
    current = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
    if current != expected:
        if fix:
            manifest_path.write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
            note(f"{rel(manifest_path)}: rewritten")
        else:
            error(manifest_path, "does not list exactly this folder's locale files; run python3 scripts/validate.py --fix")
    summary.append((project, len(english) - len(METADATA & english.keys()), row))


def main():
    # Any folder holding locale files is a project, so one can nest a folder per
    # platform (Bookshelf/ for Paper, Bookshelf/Velocity/ for the proxy).
    folders = sorted({p.parent for p in ROOT.rglob("*.json")
                      if not any(part.startswith(".") for part in p.relative_to(ROOT).parts)
                      and p.relative_to(ROOT).parts[0] != "scripts"})
    for folder in folders:
        check_project(folder)

    for message in notes:
        print(f"note: {message}")
    for file, line, message in errors:
        print(f"error: {file}:{line}: {message}")
        if github:
            print(f"::error file={file},line={line}::{message}")
    print(f"{len(folders)} project(s), {len(errors)} error(s)")

    if github and os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as out:
            out.write(f"## Locale check: {'passed' if not errors else f'{len(errors)} error(s)'}\n\n")
            if errors:
                out.write("| File | Line | Problem |\n|---|---|---|\n")
                for file, line, message in errors[:200]:
                    out.write(f"| `{file}` | {line} | {message.replace('|', '/')} |\n")
                out.write("\n")
            out.write("| Project | Keys | Translated |\n|---|---|---|\n")
            for project, keys, row in summary:
                out.write(f"| {project} | {keys} | {', '.join(row)} |\n")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
