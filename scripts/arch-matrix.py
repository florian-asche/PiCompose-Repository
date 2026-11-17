#!/usr/bin/env python3
"""
Print the GitHub Actions build matrix (architectures) of a package repository as JSON.

Usage: arch-matrix.py <source-dir> [--tag <tag>]

The architectures follow from the Architecture fields in debian/control: only
"all" packages are built on amd64, everything else on amd64, arm64 and armhf.
With --tag the tag (<version> or v<version>) has to match the first entry of
debian/changelog.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ARCHITECTURES = ["amd64", "arm64", "armhf"]
RUNNERS = {"amd64": "ubuntu-24.04", "arm64": "ubuntu-24.04-arm", "armhf": "ubuntu-24.04"}


def package_architectures(source: Path) -> list[str]:
    """
    Architectures a package repository has to be built for.
    :param source: Directory that contains debian/.
    """
    control = (source / "debian" / "control").read_text(encoding="utf-8")
    declared: set[str] = set()
    for stanza in control.split("\n\n"):
        if not stanza.startswith("Package:") and "\nPackage:" not in stanza:
            continue
        match = re.search(r"^Architecture:\s*(.+)$", stanza, re.MULTILINE)
        if match:
            declared.update(match.group(1).split())
    if declared <= {"all"}:
        return ["amd64"]
    if "any" in declared or "linux-any" in declared:
        return ARCHITECTURES
    return [arch for arch in ARCHITECTURES if arch in declared or "all" in declared]


def changelog_version(source: Path) -> str:
    """
    Version of the first debian/changelog entry.
    :param source: Directory that contains debian/.
    """
    first_line = (source / "debian" / "changelog").read_text(encoding="utf-8").splitlines()[0]
    match = re.match(r"^\S+ \((\S+)\)", first_line)
    if not match:
        sys.exit("Cannot parse debian/changelog")
    return match.group(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=Path, help="directory that contains debian/")
    parser.add_argument("--tag", help="release tag, <version> or v<version>")
    args = parser.parse_args()

    if args.tag and changelog_version(args.source) != args.tag.removeprefix("v"):
        sys.exit(f"Tag {args.tag}: debian/changelog has version {changelog_version(args.source)}")

    include = [{"arch": arch, "runner": RUNNERS[arch]} for arch in package_architectures(args.source)]
    print(json.dumps({"include": include}))


if __name__ == "__main__":
    main()
