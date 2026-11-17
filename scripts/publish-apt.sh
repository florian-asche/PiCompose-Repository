#!/bin/bash
# Add .deb files to the APT repository tree and regenerate the signed metadata.
#
# Usage: scripts/publish-apt.sh --suite <trixie|trixie-nightly> --debs <dir> --repo <dir> [--replace]
#   --suite  target suite in apt/conf/distributions
#   --debs   directory with the .deb files to add
#   --repo   checkout of the branch that GitHub Pages serves (the reprepro base directory)
#   --replace remove the packages from the suite first, so the new version wins even if it is lower
#
# Needs reprepro and a GPG secret key without passphrase in the default keyring.
# Set APT_DOMAIN to write a CNAME file for a custom domain.
set -euo pipefail

SUITE=""
DEBS_DIR=""
REPO_DIR=""
REPLACE=false
while [ $# -gt 0 ]; do
    case "$1" in
        --suite) SUITE="$2"; shift ;;
        --debs) DEBS_DIR="$2"; shift ;;
        --repo) REPO_DIR="$2"; shift ;;
        --replace) REPLACE=true ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
    shift
done

if [ -z "$SUITE" ] || [ -z "$DEBS_DIR" ] || [ -z "$REPO_DIR" ]; then
    sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
fi

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

mkdir -p "${REPO_DIR}/conf"
cp "${ROOT_DIR}"/apt/conf/* "${REPO_DIR}/conf/"

shopt -s nullglob
DEBS=("${DEBS_DIR}"/*.deb)
if [ ${#DEBS[@]} -eq 0 ]; then
    echo "No .deb files found in ${DEBS_DIR}" >&2
    exit 1
fi

if [ "$REPLACE" = true ]; then
    for name in $(for deb in "${DEBS[@]}"; do dpkg-deb -f "$deb" Package; done | sort -u); do
        reprepro --basedir "$REPO_DIR" remove "$SUITE" "$name"
    done
fi

for deb in "${DEBS[@]}"; do
    reprepro --basedir "$REPO_DIR" --component main includedeb "$SUITE" "$deb"
done

# Binary keyring file, usable directly as Signed-By.
gpg --batch --yes --export --output "${REPO_DIR}/picompose-archive-keyring.gpg"

touch "${REPO_DIR}/.nojekyll"
if [ -n "${APT_DOMAIN:-}" ]; then
    echo "$APT_DOMAIN" > "${REPO_DIR}/CNAME"
fi
