#!/bin/bash
# Build one package for one architecture inside a clean debian:trixie container.
#
# Usage: scripts/build-package.sh <source-dir> <arch> [--version <version> --notes-file <file> [--date <date>]] [--out <dir>]
#   source-dir    checkout of a package repository (the directory that contains debian/)
#   arch          amd64, arm64 or armhf
#   --version     replace debian/changelog with one entry for this version, made from the
#                 notes file (see make-changelog.py and package-version.py).
#                 Without it the debian/changelog of the repository is used.
#   --notes-file  release or pull request text for the changelog entry
#   --date        date of the changelog entry as RFC 2822 (default: now)
#   --out         directory for the resulting .deb files (default: ./out)
#
# lintian is skipped when the repository contains the file debian/skip-lintian. Use it only for repositories
# that republish packages of others unchanged, because their problems cannot be fixed or overridden here.
set -euo pipefail

if [ $# -lt 2 ]; then
    sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
fi

SOURCE_DIR="$1"
ARCH="$2"
shift 2

VERSION=""
NOTES_FILE=""
ENTRY_DATE=""
OUT_DIR="out"
while [ $# -gt 0 ]; do
    case "$1" in
        --version) VERSION="$2"; shift ;;
        --notes-file) NOTES_FILE="$2"; shift ;;
        --date) ENTRY_DATE="$2"; shift ;;
        --out) OUT_DIR="$2"; shift ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
    shift
done

if [ ! -f "${SOURCE_DIR}/debian/control" ]; then
    echo "No debian/control in ${SOURCE_DIR}" >&2
    exit 1
fi
SOURCE_DIR="$(cd "$SOURCE_DIR" && pwd)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

case "$ARCH" in
    amd64) PLATFORM="linux/amd64" ;;
    arm64) PLATFORM="linux/arm64" ;;
    armhf) PLATFORM="linux/arm/v7" ;;
    *) echo "Unsupported architecture: $ARCH" >&2; exit 1 ;;
esac

mkdir -p "$OUT_DIR"
OUT_DIR="$(cd "$OUT_DIR" && pwd)"

BUILD_DIR="$(mktemp -d)"
trap 'rm -rf "$BUILD_DIR"' EXIT
cp -a "$SOURCE_DIR/." "$BUILD_DIR/"
if [ -n "$VERSION" ]; then
    if [ -z "$NOTES_FILE" ]; then
        echo "--version needs --notes-file" >&2
        exit 1
    fi
    python3 "${SCRIPT_DIR}/make-changelog.py" "$BUILD_DIR" --version "$VERSION" --notes-file "$NOTES_FILE" ${ENTRY_DATE:+--date "$ENTRY_DATE"}
fi

docker run --rm --platform "$PLATFORM" \
    -v "${BUILD_DIR}:/src:ro" \
    -v "${OUT_DIR}:/out" \
    -e "ARCH=${ARCH}" \
    -e "HOST_UID=$(id -u)" \
    -e "HOST_GID=$(id -g)" \
    -e "DEBIAN_FRONTEND=noninteractive" \
    debian:trixie bash -euo pipefail -c '
        apt-get update -qq
        apt-get install -y -qq --no-install-recommends build-essential debhelper devscripts fakeroot lintian >/dev/null

        mkdir /build
        cp -a /src /build/pkg
        cd /build/pkg
        apt-get build-dep -y -qq ./ >/dev/null

        dpkg-buildpackage -us -uc -b
        if [ -f debian/skip-lintian ]; then
            echo "debian/skip-lintian exists, lintian is skipped."
        else
            lintian --fail-on error --display-info ../*.deb
        fi

        # Architecture: all packages are published from the amd64 build only.
        if [ "$ARCH" != amd64 ]; then
            rm -f ../*_all.deb
        fi
        cp ../*.deb /out/
        chown "${HOST_UID}:${HOST_GID}" /out/*.deb
    '
