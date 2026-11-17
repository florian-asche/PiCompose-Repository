#!/usr/bin/env python3
"""
Print the GitHub Actions build matrix (package x architecture) as JSON.

Usage: build-matrix.py [--all] [--base <git ref>] [--tag <package>/<version>]

Without arguments every package is built. With --base only packages that changed
since that ref are built, and a change to scripts/ or the build workflow rebuilds
everything. With --tag only the tagged package is built, and its tag version has
to match debian/changelog.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGES_DIR = ROOT / "packages"
ARCHITECTURES = ["amd64", "arm64", "armhf"]
RUNNERS = {"amd64": "ubuntu-24.04", "arm64": "ubuntu-24.04-arm", "armhf": "ubuntu-24.04"}
GLOBAL_PATHS = ("scripts/", ".github/workflows/build.yml")


def list_packages() -> list[str]:
    return sorted(p.parent.parent.name for p in PACKAGES_DIR.glob("*/debian/control"))


def package_architectures(package: str) -> list[str]:
    """
    Architectures a package has to be built for.
    :param package: Directory name below packages/.
    """
    control = (PACKAGES_DIR / package / "debian" / "control").read_text(encoding="utf-8")
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


def changelog_version(package: str) -> str:
    first_line = (PACKAGES_DIR / package / "debian" / "changelog").read_text(encoding="utf-8").splitlines()[0]
    match = re.match(r"^\S+ \((\S+)\)", first_line)
    if not match:
        sys.exit(f"Cannot parse debian/changelog of {package}")
    return match.group(1)


def changed_packages(base: str, packages: list[str]) -> list[str]:
    diff = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    if any(path.startswith(GLOBAL_PATHS) for path in diff):
        return packages
    return [p for p in packages if any(path.startswith(f"packages/{p}/") for path in diff)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--all", action="store_true", help="build every package")
    parser.add_argument("--base", help="only build packages changed since this git ref")
    parser.add_argument("--tag", help="release tag in the form <package>/<version>")
    args = parser.parse_args()

    packages = list_packages()
    if args.tag:
        package, _, version = args.tag.partition("/")
        if package not in packages:
            sys.exit(f"Tag {args.tag}: unknown package '{package}'")
        if changelog_version(package) != version:
            sys.exit(f"Tag {args.tag}: debian/changelog has version {changelog_version(package)}")
        packages = [package]
    elif args.base and not args.all and not re.fullmatch(r"0+", args.base):
        packages = changed_packages(args.base, packages)

    include = [
        {"package": package, "arch": arch, "runner": RUNNERS[arch]}
        for package in packages
        for arch in package_architectures(package)
    ]
    print(json.dumps({"include": include}))


if __name__ == "__main__":
    main()
