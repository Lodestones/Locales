#!/usr/bin/env python3
"""Checks what a pull request changes, on top of what it changes it to.

    BASE_SHA=... HEAD_SHA=... AUTHOR_ASSOCIATION=... python3 scripts/check_pr.py

Contributors translate. They may add or edit a language file, update a manifest to
list a new one, and touch the README. Everything else is for maintainers:
- en_us.json is the English every other file is checked against, kept in step
  with the plugins themselves, so a change there has to come from a maintainer;
- the scripts and workflows are what does the checking.
"""
import os
import re
import subprocess
import sys

MAINTAINERS = {"OWNER", "MEMBER", "COLLABORATOR"}
LOCALE = re.compile(r"^(?:[A-Z][A-Za-z-]*/)+[a-z]{2,3}_[a-z]{2,4}\.json$")
MANIFEST = re.compile(r"^(?:[A-Z][A-Za-z-]*/)+manifest\.json$")

base, head = os.environ["BASE_SHA"], os.environ["HEAD_SHA"]
association = os.environ.get("AUTHOR_ASSOCIATION", "NONE")

if association in MAINTAINERS:
    print(f"Author is a maintainer ({association}); no path restrictions.")
    sys.exit(0)

diff = subprocess.run(["git", "diff", "--name-status", "--no-renames", f"{base}...{head}"],
                      capture_output=True, text=True, check=True).stdout
problems = []
for line in diff.splitlines():
    status, path = line.split("\t", 1)
    if path.endswith("/en_us.json") or path == "en_us.json":
        problems.append((path, "the English source is maintained alongside the plugins; open an issue to suggest a change to it"))
    elif status == "D":
        problems.append((path, "removing files is for maintainers; open an issue instead"))
    elif LOCALE.match(path) or MANIFEST.match(path) or path == "README.md":
        continue
    else:
        problems.append((path, "only language files, manifests and the README can be changed in a contribution"))

for path, message in problems:
    print(f"error: {path}: {message}")
    print(f"::error file={path}::{message}")
if problems and os.environ.get("GITHUB_STEP_SUMMARY"):
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as out:
        out.write("## Pull request scope\n\n| File | Problem |\n|---|---|\n")
        for path, message in problems:
            out.write(f"| `{path}` | {message} |\n")
print(f"{len(problems)} problem(s)")
sys.exit(1 if problems else 0)
