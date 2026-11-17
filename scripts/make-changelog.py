#!/usr/bin/env python3
"""
Write debian/changelog with a single entry made from release or pull request text.

Usage: make-changelog.py <source-dir> --version <version> --notes-file <file> [--date <RFC 2822 date>]

The package name and the maintainer come from debian/control. Lines of the
notes become changelog items: Markdown bullets lose their marks, headings,
HTML comments,
empty lines and the "Full Changelog" line GitHub adds are dropped.
"""
import argparse
import re
from email.utils import formatdate
from pathlib import Path

MAX_ITEMS = 30


def notes_to_items(notes: str, version: str) -> list[str]:
    """
    Turn Markdown notes into plain changelog items.
    :param notes: Release or pull request text.
    :param version: Version used when the notes contain no usable line.
    """
    items = []
    for line in notes.splitlines():
        if line.lstrip().startswith(("#", "<!--")):
            continue
        line = re.sub(r"^\s*[*+-]\s+", "", line).strip()
        line = re.sub(r"[^\S ]|[\x00-\x1f]", " ", line)
        if line and not line.lower().startswith("**full changelog**"):
            items.append(line)
    return items[:MAX_ITEMS] or [f"Release {version}."]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--notes-file", required=True, type=Path)
    parser.add_argument("--date", default=None)
    args = parser.parse_args()

    control = (args.source / "debian" / "control").read_text(encoding="utf-8")
    source_name = re.search(r"^Source:\s*(\S+)", control, re.MULTILINE).group(1)  # type: ignore[union-attr]
    maintainer = re.search(r"^Maintainer:\s*(.+)$", control, re.MULTILINE).group(1).strip()  # type: ignore[union-attr]
    items = notes_to_items(args.notes_file.read_text(encoding="utf-8"), args.version)

    body = "\n".join(f"  * {item}" for item in items)
    entry = f"{source_name} ({args.version}) trixie; urgency=medium\n\n{body}\n\n -- {maintainer}  {args.date or formatdate(localtime=True)}\n"
    (args.source / "debian" / "changelog").write_text(entry, encoding="utf-8")


if __name__ == "__main__":
    main()
