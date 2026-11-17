#!/usr/bin/env python3
"""
Compute versions of a package repository from debian/changelog and merged pull requests.

Usage: package-version.py bump --repository <owner/name> --notes-file <file> [--source <dir>]
       package-version.py dev --stamp <timestamp> --sha <sha> [--source <dir>]

The version of the package is the first entry of debian/changelog.

bump: the next version after merges to main. The commits since the last commit that
      changed debian/changelog are looked up with their merged pull requests. The
      highest of the labels major, minor and patch on those pull requests decides
      which part is raised (patch if there is no label or no pull request). The new
      version is printed and the changelog items (pull request titles) are written
      to the notes file. Nothing is printed if there are no new commits.
dev:  <version>+dev<stamp>.<sha> for builds of other branches. It sorts above the
      last release and installs as an upgrade of it.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

LEVELS = ("major", "minor", "patch")


def git(source: Path, *args: str) -> str:
    """
    Run a git command and return its output.
    :param source: Directory of the git repository.
    :param args: Arguments of the git command.
    """
    return subprocess.run(["git", *args], cwd=source, check=True, capture_output=True, text=True).stdout


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


def merged_pull_requests(sha: str, repository: str) -> list[dict]:
    """
    Merged pull requests a commit belongs to.
    :param sha: Commit to look up.
    :param repository: owner/name of the repository.
    """
    result = subprocess.run(["gh", "api", f"repos/{repository}/commits/{sha}/pulls"], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        sys.exit(f"Cannot read the pull requests of {sha}: {result.stderr.strip()}")
    return [pull for pull in json.loads(result.stdout or "[]") if pull.get("merged_at")]


def bump(source: Path, repository: str, notes_file: Path) -> None:
    """
    Print the next version and write the changelog items.
    :param source: Directory of the git repository.
    :param repository: owner/name of the repository.
    :param notes_file: File that receives one changelog item per line.
    """
    last = git(source, "log", "-1", "--format=%H", "--", "debian/changelog").strip()
    commits = git(source, "rev-list", "--reverse", f"{last}..HEAD" if last else "HEAD").split()
    if not commits:
        return

    level = len(LEVELS) - 1
    items: list[str] = []
    seen: set[int] = set()
    for sha in commits:
        pulls = merged_pull_requests(sha, repository)
        for pull in pulls:
            if pull["number"] in seen:
                continue
            seen.add(pull["number"])
            items.append(f"{pull['title']} (#{pull['number']})")
            for label in pull.get("labels", []):
                if label["name"] in LEVELS:
                    level = min(level, LEVELS.index(label["name"]))
        if not pulls:
            subject = git(source, "log", "-1", "--format=%s", sha).strip()
            if subject and not subject.startswith("Merge "):
                items.append(subject)

    major, minor, patch = (int(part) for part in re.match(r"^(\d+)\.(\d+)\.(\d+)", changelog_version(source)).groups())  # type: ignore[union-attr]
    if LEVELS[level] == "major":
        version = f"{major + 1}.0.0"
    elif LEVELS[level] == "minor":
        version = f"{major}.{minor + 1}.0"
    else:
        version = f"{major}.{minor}.{patch + 1}"
    notes_file.write_text("\n".join(items) + "\n", encoding="utf-8")
    print(version)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, default=Path("."))
    sub = parser.add_subparsers(dest="command", required=True)
    bump_parser = sub.add_parser("bump")
    bump_parser.add_argument("--repository", required=True)
    bump_parser.add_argument("--notes-file", type=Path, required=True)
    dev_parser = sub.add_parser("dev")
    dev_parser.add_argument("--stamp", required=True)
    dev_parser.add_argument("--sha", required=True)
    args = parser.parse_args()

    if args.command == "bump":
        bump(args.source, args.repository, args.notes_file)
    else:
        print(f"{changelog_version(args.source)}+dev{args.stamp}.{args.sha}")


if __name__ == "__main__":
    main()
