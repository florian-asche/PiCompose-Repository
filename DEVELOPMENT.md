# Development Guide

This guide describes the repository layout, how to build packages locally and how packages get into the APT repository.

## Prerequisites

- Git
- Docker (the packages are built in a clean `debian:trixie` container)
- Python 3 (for the build matrix script)
- Basic knowledge of Debian packaging (`debian/control`, `debian/rules`, `debian/changelog`)

## Project Structure

```
packages/<name>/        one directory per source package
  debian/               control, changelog, rules, copyright, install, maintainer scripts
apt/conf/               reprepro configuration (suites and architectures)
scripts/
  build-package.sh      build one package for one architecture in a container
  build-matrix.py       print the CI build matrix (package x architecture)
  publish-apt.sh        add .deb files to the repository tree and sign it
docs/                   documentation
.github/workflows/      CI: build, publish, PR labels, changelog
```

The directory name below `packages/` is the source package name and has to match `Source:` in `debian/control`.

## Adding a Package

1. Create `packages/<name>/` with a `debian/` directory. Copy `packages/picompose-hello` as a starting point. The same package is also available as the template repository [PiCompose-Package-Hello](https://github.com/florian-asche/PiCompose-Package-Hello).
2. Use `3.0 (native)` in `debian/source/format`, so the version has no Debian revision (`1.0.0`, not `1.0.0-1`).
3. Set `Architecture: all` for scripts, configuration and device tree overlays. Use `any` for compiled content. The CI builds `all` packages on `amd64` only and everything else on `amd64`, `arm64` and `armhf`.
4. Build and lint it locally (see below).
5. Add it to the package table in `README.md`.

Conventions:

- Package names start with `picompose-`, except upstream applications.
- Systemd units go to `/usr/lib/systemd/system/` and are enabled through `dh_installsystemd`. Do not call `systemctl` directly in maintainer scripts, because it fails inside chroots such as the pi-gen image build.
- Maintainer scripts must run without prompts and must not fail when the hardware is missing.
- Files that users edit are conffiles below `/etc`. Defaults for user-owned locations like `/compose` are shipped to `/usr/share/picompose/` and copied by `postinst` only if missing.

## Local Build

```bash
./scripts/build-package.sh picompose-hello amd64
```

The `.deb` files end up in `out/`. The script installs the build dependencies in a fresh container, runs `dpkg-buildpackage` and then `lintian`. Errors reported by lintian fail the build.

Other architectures run through QEMU emulation when your host is not that architecture, which is slow. Register the emulators once with `docker run --privileged --rm tonistiigi/binfmt --install all`.

Print the matrix the CI would build:

```bash
python3 scripts/build-matrix.py --all
python3 scripts/build-matrix.py --base origin/main
```

## Versioning and Releases

- Every change to a package raises the version in `debian/changelog`.
- Pushes to `main` build the changed packages and publish them to the suite `trixie-nightly` with the version `<version>~git<date>.<sha>`. The `~` makes a nightly sort below the release.
- Pushes to the branch `test` publish to the suite `trixie-test` with the version `<version>~test<date>.<sha>`. Use it to try a change on a device before it is merged. Everybody who pushes to `test` shares this suite, and a newer push replaces the previous test version of a package.
- A release is a tag `<package>/<version>`, for example `picompose-hello/0.1.1`. The version has to match the first entry in `debian/changelog`. Only that package is built and published to the suite `trixie`.
- Pull requests build the changed packages and publish nothing.

A change to `scripts/` or `.github/workflows/build.yml` rebuilds every package.

## APT Repository

The repository is built with [reprepro](https://wiki.debian.org/DebianRepository/SetupWithReprepro) and served as static files from the `gh-pages` branch. The `publish` job of the workflow adds the new packages to that branch and signs the metadata.

Suites are defined in `apt/conf/distributions`. Clients only know the repository URL, so the hosting can move later (for example to object storage) without touching any device if a custom domain is used.

### One-time Setup

1. Create a dedicated GPG key (details, renewal and key leak handling: [docs/gpg_signing_key.md](docs/gpg_signing_key.md)): a master key that only certifies and stays offline, and a signing subkey that goes into CI. The key has no passphrase, because CI has to sign unattended. The master key is protected by where you store it (encrypted disk or password manager).
   ```bash
   gpg --quick-generate-key "PiCompose Archive <picompose@florian-asche.de>" ed25519 cert 0
   gpg --list-keys --with-colons | awk -F: '/^fpr/ {print $10; exit}'    # prints the fingerprint
   gpg --quick-add-key <FINGERPRINT> ed25519 sign 2y
   gpg --list-keys --with-colons | awk -F: '/^sub/ {print $5; exit}'     # prints the subkey id
   gpg --armor --export-secret-subkeys '<SUBKEY-ID>!' > signing-subkey.asc
   ```
   Then back up the master key and the revocation certificate offline:
   ```bash
   gpg --armor --export-secret-keys <FINGERPRINT> > picompose-master-secret.asc
   ls ~/.gnupg/openpgp-revocs.d/
   ```
2. In the repository settings (Settings, Environments), create the environment `apt-publish`. Under "Deployment branches and tags" restrict it to the branches `main` and `test` and to tags, and require a reviewer if wanted. Without that restriction every branch can use the signing secret.
3. Add the secret `APT_GPG_PRIVATE_KEY` to that environment. Paste the whole content of `signing-subkey.asc`, including the `BEGIN` and `END` lines. With the GitHub CLI:
   ```bash
   gh api -X PUT repos/florian-asche/PiCompose-Repository/environments/apt-publish
   gh secret set APT_GPG_PRIVATE_KEY --env apt-publish --repo florian-asche/PiCompose-Repository < signing-subkey.asc
   shred -u signing-subkey.asc
   ```
   The public key does not need to be stored anywhere. The publish job exports it to `picompose-archive-keyring.gpg` on every run.
4. After the first publish run, enable GitHub Pages in the repository settings with source "Deploy from a branch", branch `gh-pages`, folder `/ (root)`.
5. Optional: set the environment variable `APT_DOMAIN` to a custom domain. The workflow then writes a `CNAME` file.

Notes:

- The signing subkey expires after two years. Extend it with the master key (`gpg --edit-key <FINGERPRINT>`, `key 1`, `expire`), export it again and replace the secret. Devices keep the old public key with the old expiry date, so they need the updated `picompose-archive-keyring.gpg` before the old expiry. This is what the `picompose-archive-keyring` package is planned for.
- reprepro keeps its database in `db/` inside the repository tree, so it lives on the `gh-pages` branch and is served publicly. It contains only package metadata.
- GitHub Pages has a soft size limit of about 1 GB. Large packages (for example a Python virtual environment for the voice assistant) have to be pruned regularly or the pool has to move to object storage.

## Troubleshooting

- **lintian fails the build:** The container output lists the tags. Fix them or add an override in `debian/<package>.lintian-overrides` with a comment explaining why.
- **`apt-get build-dep` fails:** `Build-Depends` in `debian/control` names a package that does not exist in `trixie`.
- **Publish job is skipped:** It only runs for pushes to `main` and `test` and for tags, and only when at least one package was built.
- **Reprepro refuses a package:** The same version with different content is already in the repository. Raise the version.
