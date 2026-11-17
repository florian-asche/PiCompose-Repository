#!/usr/bin/env python3
"""
Print the version a package build gets.

Usage: package-version.py --channel <stable|nightly|test> [--tag <tag>] [--stamp <timestamp>] [--sha <sha>] [--source <dir>]

stable: the release tag without a leading v, for example v1.2.0 gives 1.2.0.
nightly, test: the next patch version after the newest tag of the repository in
--source (0.0.1 without any tag), followed by ~git<stamp>.<sha> or
~test<stamp>.<sha>. The ~ sorts the build below the release it leads to.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

TAG_PATTERN = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def latest_version(source: Path) -> tuple[int, int, int]:
    """
    Newest release version among the tags of a repository.
    :param source: Directory of the git repository.
    """
    tags = subprocess.run(["git", "tag", "--list"], cwd=source, check=True, capture_output=True, text=True).stdout.split()
    versions = [tuple(int(part) for part in match.groups()) for tag in tags if (match := TAG_PATTERN.match(tag))]
    return max(versions) if versions else (0, 0, 0)  # type: ignore[return-value]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--channel", required=True, choices=["stable", "nightly", "test"])
    parser.add_argument("--tag")
    parser.add_argument("--stamp")
    parser.add_argument("--sha")
    parser.add_argument("--source", type=Path, default=Path("."))
    args = parser.parse_args()

    if args.channel == "stable":
        if not args.tag or not re.fullmatch(r"v?\d+(\.\d+)*", args.tag):
            sys.exit(f"Release tag '{args.tag}' is not a version like v1.2.3")
        print(args.tag.removeprefix("v"))
        return

    if not args.stamp or not args.sha:
        sys.exit("--stamp and --sha are required for nightly and test builds")
    major, minor, patch = latest_version(args.source)
    label = "git" if args.channel == "nightly" else "test"
    print(f"{major}.{minor}.{patch + 1}~{label}{args.stamp}.{args.sha}")


if __name__ == "__main__":
    main()
