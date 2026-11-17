#!/usr/bin/env python3
"""
Check .deb files downloaded from a package repository before they are signed and published.

Usage: check-debs.py --repository <owner/name> --channel <stable|nightly> --debs <dir> [--sources <file>]

Fails unless the repository is listed in sources.yml, every package name is one
of the packages listed for it, the architecture is supported and the version
matches the channel and is the same for all architectures of a package: nightly versions contain ~git and
stable versions no ~.
"""
import argparse
import subprocess
import sys
from pathlib import Path

import yaml

ARCHITECTURES = {"amd64", "arm64", "armhf", "all"}
VERSION_MARKERS = {"stable": None, "nightly": "~git"}


def deb_field(deb: Path, field: str) -> str:
    """
    Read one control field of a .deb file.
    :param deb: Path to the .deb file.
    :param field: Name of the control field.
    """
    return subprocess.run(["dpkg-deb", "-f", str(deb), field], check=True, capture_output=True, text=True).stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--channel", required=True, choices=sorted(VERSION_MARKERS))
    parser.add_argument("--debs", required=True, type=Path)
    parser.add_argument("--sources", type=Path, default=Path(__file__).resolve().parent.parent / "sources.yml")
    args = parser.parse_args()

    allowed = (yaml.safe_load(args.sources.read_text(encoding="utf-8")) or {}).get("repositories", {})
    if args.repository not in allowed:
        sys.exit(f"{args.repository} is not listed in sources.yml")
    packages = set(allowed[args.repository].get("packages", []))

    debs = sorted(args.debs.glob("*.deb"))
    if not debs:
        sys.exit(f"No .deb files in {args.debs}")

    errors = []
    versions: dict[str, set[str]] = {}
    marker = VERSION_MARKERS[args.channel]
    for deb in debs:
        name, version, arch = (deb_field(deb, field) for field in ("Package", "Version", "Architecture"))
        if name not in packages:
            errors.append(f"{deb.name}: package {name} is not allowed for {args.repository}")
        if arch not in ARCHITECTURES:
            errors.append(f"{deb.name}: unsupported architecture {arch}")
        if marker is None and "~" in version:
            errors.append(f"{deb.name}: version {version} contains ~, not a stable release")
        if marker is not None and marker not in version:
            errors.append(f"{deb.name}: version {version} does not contain {marker}")
        versions.setdefault(name, set()).add(version)
        print(f"{deb.name}: {name} {version} {arch}")
    for name, found in versions.items():
        if len(found) > 1:
            errors.append(f"{name}: different versions for different architectures: {', '.join(sorted(found))}")
    if errors:
        sys.exit("\n".join(errors))


if __name__ == "__main__":
    main()
