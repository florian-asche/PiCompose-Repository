#!/usr/bin/env python3
"""
Print the version a package build gets.

Usage: package-version.py --channel <stable|nightly|dev> [--tag <tag>] [--stamp <timestamp>] [--sha <sha>]
                          [--source <dir>] [--repository <owner/name>]

The next release version follows from the newest release tag (v<major>.<minor>.<patch>)
before the commit and from the text of every commit since that tag: the commit
message and, if --repository is given, the title and description of its pull
request. The marker #major raises the major version, #minor the minor version
and anything else, including no marker, the patch version. The highest marker wins.

nightly: the next release version followed by ~git<stamp>.<sha>.
dev:     the next patch version followed by ~dev<stamp>.<sha>.
stable:  the version of --tag. It has to be the next release version, so a release
         publishes exactly the version the nightly builds announced.

The ~ sorts a build below the release it leads to.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

TAG_PATTERN = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
MARKER = re.compile(r"(?<![\w#])#(major|minor|patch)\b", re.IGNORECASE)
LEVELS = ("major", "minor", "patch")

Version = tuple[int, int, int]


def git(source: Path, *args: str) -> str:
    """
    Run a git command and return its output.
    :param source: Directory of the git repository.
    :param args: Arguments of the git command.
    """
    return subprocess.run(["git", *args], cwd=source, check=True, capture_output=True, text=True).stdout


def previous_release(source: Path, exclude: str | None) -> tuple[Version, str] | None:
    """
    Newest release tag among the tags that are part of the history of HEAD.
    :param source: Directory of the git repository.
    :param exclude: Tag that is not counted, the tag of the release being built.
    """
    found = []
    for tag in git(source, "tag", "--merged", "HEAD", "--list").split():
        match = TAG_PATTERN.match(tag)
        if match and tag != exclude:
            found.append((tuple(int(part) for part in match.groups()), tag))
    return max(found) if found else None  # type: ignore[return-value]


def commit_text(source: Path, sha: str, repository: str | None) -> str:
    """
    Text that decides the version bump of one commit.
    :param source: Directory of the git repository.
    :param sha: Commit to read.
    :param repository: owner/name to ask for the pull request of the commit, or None.
    """
    text = git(source, "log", "-1", "--format=%B", sha)
    if repository:
        result = subprocess.run(["gh", "api", f"repos/{repository}/commits/{sha}/pulls"], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            for pull in json.loads(result.stdout or "[]")[:1]:
                text += f"\n{pull.get('title') or ''}\n{pull.get('body') or ''}"
    return text


def bump_level(source: Path, base_tag: str | None, repository: str | None) -> str:
    """
    Highest bump marker in the commits since the base tag, patch if there is none.
    :param source: Directory of the git repository.
    :param base_tag: Newest release tag, or None to look at the whole history.
    :param repository: owner/name for pull request texts, or None.
    """
    revisions = f"{base_tag}..HEAD" if base_tag else "HEAD"
    level = len(LEVELS) - 1
    for sha in git(source, "rev-list", revisions).split():
        for marker in MARKER.findall(commit_text(source, sha, repository)):
            level = min(level, LEVELS.index(marker.lower()))
    return LEVELS[level]


def bumped(base: Version, level: str) -> Version:
    """
    Raise one part of a version and reset the parts below it.
    :param base: Version to raise.
    :param level: major, minor or patch.
    """
    major, minor, patch = base
    if level == "major":
        return (major + 1, 0, 0)
    if level == "minor":
        return (major, minor + 1, 0)
    return (major, minor, patch + 1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--channel", required=True, choices=["stable", "nightly", "dev"])
    parser.add_argument("--tag")
    parser.add_argument("--stamp")
    parser.add_argument("--sha")
    parser.add_argument("--source", type=Path, default=Path("."))
    parser.add_argument("--repository")
    args = parser.parse_args()

    previous = previous_release(args.source, args.tag if args.channel == "stable" else None)
    base, base_tag = previous if previous else ((0, 0, 0), None)

    if args.channel == "stable":
        if not args.tag or not TAG_PATTERN.match(args.tag):
            sys.exit(f"Release tag '{args.tag}' is not a version like v1.2.3")
        expected = ".".join(str(part) for part in bumped(base, bump_level(args.source, base_tag, args.repository)))
        if args.tag.removeprefix("v") != expected:
            sys.exit(
                f"Release tag {args.tag} does not match the version {expected} that follows from the commits since "
                f"{base_tag or 'the start'}. Use the tag v{expected}, or put #major or #minor in the text of a commit or pull request."
            )
        print(expected)
        return

    if not args.stamp or not args.sha:
        sys.exit("--stamp and --sha are required for nightly and dev builds")
    level = bump_level(args.source, base_tag, args.repository) if args.channel == "nightly" else "patch"
    label = "git" if args.channel == "nightly" else "dev"
    print(f"{'.'.join(str(part) for part in bumped(base, level))}~{label}{args.stamp}.{args.sha}")


if __name__ == "__main__":
    main()
