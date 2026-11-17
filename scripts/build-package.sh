#!/bin/bash
# Build one package for one architecture inside a clean debian:trixie container.
#
# Usage: scripts/build-package.sh <package> <arch> [--channel nightly|test] [--out <dir>]
#   package   directory name below packages/
#   arch      amd64, arm64 or armhf
#   --channel build a pre-release: nightly gives <version>~git<date>.<sha>,
#             test gives <version>~test<date>.<sha>. Without it the version is unchanged.
#   --out     directory for the resulting .deb files (default: ./out)
set -euo pipefail

if [ $# -lt 2 ]; then
    sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
fi

PACKAGE="$1"
ARCH="$2"
shift 2

SNAPSHOT_LABEL=""
OUT_DIR="out"
while [ $# -gt 0 ]; do
    case "$1" in
        --channel)
            case "$2" in
                nightly) SNAPSHOT_LABEL="git" ;;
                test) SNAPSHOT_LABEL="test" ;;
                *) echo "Unknown channel: $2" >&2; exit 1 ;;
            esac
            shift ;;
        --out) OUT_DIR="$2"; shift ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
    shift
done

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [ ! -f "${ROOT_DIR}/packages/${PACKAGE}/debian/control" ]; then
    echo "Package not found: packages/${PACKAGE}" >&2
    exit 1
fi

case "$ARCH" in
    amd64) PLATFORM="linux/amd64" ;;
    arm64) PLATFORM="linux/arm64" ;;
    armhf) PLATFORM="linux/arm/v7" ;;
    *) echo "Unsupported architecture: $ARCH" >&2; exit 1 ;;
esac

mkdir -p "$OUT_DIR"
OUT_DIR="$(cd "$OUT_DIR" && pwd)"
SHORT_SHA="$(git -C "$ROOT_DIR" rev-parse --short=7 HEAD 2>/dev/null || echo unknown)"

docker run --rm --platform "$PLATFORM" \
    -v "${ROOT_DIR}/packages/${PACKAGE}:/src:ro" \
    -v "${OUT_DIR}:/out" \
    -e "ARCH=${ARCH}" \
    -e "SNAPSHOT_LABEL=${SNAPSHOT_LABEL}" \
    -e "SHORT_SHA=${SHORT_SHA}" \
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

        if [ -n "$SNAPSHOT_LABEL" ]; then
            BASE_VERSION="$(dpkg-parsechangelog -S Version)"
            DEBFULLNAME="PiCompose CI" DEBEMAIL="github@florian-asche.de" \
                dch --force-bad-version --force-distribution --distribution trixie --newversion \
                "${BASE_VERSION}~${SNAPSHOT_LABEL}$(date -u +%Y%m%d).${SHORT_SHA}" "Pre-release build."
        fi

        dpkg-buildpackage -us -uc -b
        lintian --fail-on error --display-info ../*.deb

        # Architecture: all packages are published from the amd64 build only.
        if [ "$ARCH" != amd64 ]; then
            rm -f ../*_all.deb
        fi
        cp ../*.deb /out/
        chown "${HOST_UID}:${HOST_GID}" /out/*.deb
    '
