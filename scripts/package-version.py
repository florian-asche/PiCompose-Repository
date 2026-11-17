#!/usr/bin/env python3
"""
Print the version a package build gets, or check the version of a release.

Usage: package-version.py --channel <nightly|dev> --stamp <timestamp> --sha <sha> [--source <dir>]
       package-version.py --release-version <version> [--source <dir>]

The base is the version of the first entry of debian/changelog in --source, which is
the last release. nightly gives <base>+git<stamp>.<sha> and dev gives <base>+dev<stamp>.<sha>.
Both sort above the last release and below every later one, and the timestamp makes a newer
build sort above an older one.

With --release-version the version is checked instead: it has to look like 1.2.3 and be
higher than the base. It is printed unchanged.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path


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
    parser.add_argument("--channel", choices=["nightly", "dev"])
    parser.add_argument("--release-version")
    parser.add_argument("--stamp")
    parser.add_argument("--sha")
    parser.add_argument("--source", type=Path, default=Path("."))
    args = parser.parse_args()

    base = changelog_version(args.source)

    if args.release_version:
        if not re.fullmatch(r"\d+\.\d+\.\d+", args.release_version):
            sys.exit(f"Version '{args.release_version}' is not a version like 1.2.3")
        newer = subprocess.run(["dpkg", "--compare-versions", args.release_version, "gt", base], check=False)
        if newer.returncode != 0:
            sys.exit(f"Version {args.release_version} is not higher than the last release {base}")
        print(args.release_version)
        return

    if not args.channel or not args.stamp or not args.sha:
        sys.exit("--channel, --stamp and --sha are required for nightly and dev builds")
    label = "git" if args.channel == "nightly" else "dev"
    print(f"{base}+{label}{args.stamp}.{args.sha}")


if __name__ == "__main__":
    main()
