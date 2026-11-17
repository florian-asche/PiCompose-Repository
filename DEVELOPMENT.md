# Development Guide

This guide describes the repository layout, how to build packages locally and how packages get into the APT repository.

## Prerequisites

- Git
- Docker (the packages are built in a clean `debian:trixie` container)
- Python 3 with PyYAML (for the checks of the publish workflow)

## How it works

```
package repository                         this repository
PiCompose-Package-<Name>                   PiCompose-Repository
  debian/                                    sources.yml   which repositories may publish
  .github/workflows/build.yml  --calls-->    package-build.yml   reusable build workflow
        |                                    publish.yml         check, sign, publish
        | 1. build in a container            apt/conf/           suites and architectures
        | 2. attach .deb to a release        gh-pages branch     the APT repository
        | 3. repository_dispatch  ---------> 4. download .deb from the release
                                             5. check, sign, add to the suite
```

The package repository never sees the signing key. The dispatch only says which repository, channel and release to publish. `publish.yml` downloads the packages itself from the GitHub release, and only if the repository is listed in `sources.yml` and the package names and versions fit the channel. A leaked dispatch token can therefore only publish what is already in a release of a listed repository.

| Event in the package repository | Channel | Suite | Version |
| --- | --- | --- | --- |
| Tag `v<version>` | stable | `trixie` | `<version>` |
| Push to `main` | nightly | `trixie-nightly` | `<version>~git<timestamp>.<sha>` |
| Push to the branch `test` | test | `trixie-test` | `<version>~test<timestamp>.<sha>` |
| Pull request | none | none | built and linted only |

- The tag has to match the first entry of `debian/changelog`. A tag without the leading `v` is accepted by the build script, but the workflow of the template only starts for `v<version>`.
- Nightly and test builds are attached to a rolling pre-release of the package repository with the tag `nightly` or `test`. Every push replaces it.
- The timestamp has the format `YYYYMMDDHHMMSS`, so a newer push always sorts above an older one. The `~` makes both sort below the release.
- A suite holds one version per package. A newer build replaces the previous one in that suite.
- Packages with `Architecture: all` are built on `amd64` only. Everything else is built for `amd64`, `arm64` and `armhf`.

## Repository Layout

```
sources.yml             package repositories that may publish, with their package names
apt/conf/               reprepro configuration (suites and architectures)
scripts/
  build-package.sh      build one package for one architecture in a container
  arch-matrix.py        print the build matrix (architectures) of a package repository
  check-debs.py         check downloaded .deb files against sources.yml and the channel
  publish-apt.sh        add .deb files to the repository tree and sign it
docs/                   documentation
.github/workflows/
  package-build.yml     reusable build workflow, called by the package repositories
  publish.yml           publish workflow, started by the dispatch of a package repository
  ci.yml                lint of this repository
```

## Adding a Package

1. Create a repository `PiCompose-Package-<Name>` from the template [PiCompose-Package-Hello](https://github.com/florian-asche/PiCompose-Package-Hello) and follow its README.
2. Add the repository and its package names to `sources.yml` in this repository. Publishing is refused until this is merged.
3. Add the secret `HUB_DISPATCH_TOKEN` to the package repository (see "Dispatch token" below).
4. Push to `main` to publish the first nightly build, then add the package to the table in `README.md`.

Conventions:

- Package names start with `picompose-`, except upstream applications.
- Use `3.0 (native)` in `debian/source/format`, so the version has no Debian revision (`1.0.0`, not `1.0.0-1`).
- Use `Architecture: all` for scripts, configuration and device tree overlays, `any` for compiled content.
- Systemd units go to `/usr/lib/systemd/system/` and are enabled through `dh_installsystemd`. Do not call `systemctl` directly in maintainer scripts, because it fails inside chroots such as the pi-gen image build.
- Maintainer scripts must run without prompts and must not fail when the hardware is missing.
- Files that users edit are conffiles below `/etc`. Defaults for user-owned locations like `/compose` are shipped to `/usr/share/picompose/` and copied by `postinst` only if missing.

## Local Build

Check out a package repository and build it with the script of this repository:

```bash
./scripts/build-package.sh ../PiCompose-Package-Hello amd64
```

The `.deb` files end up in `out/`. The script installs the build dependencies in a fresh container, runs `dpkg-buildpackage` and then `lintian`. Errors reported by lintian fail the build. Add `--channel nightly` or `--channel test` to build with a pre-release version.

Other architectures run through QEMU emulation when your host is not that architecture, which is slow. Register the emulators once with `docker run --privileged --rm tonistiigi/binfmt --install all`.

## Dispatch token

The package repository tells this repository to publish with a `repository_dispatch` event, which needs a token with write access to this repository. Create a fine-grained personal access token for the owner `florian-asche`, restricted to the repository `PiCompose-Repository` with the permission "Contents: Read and write", and store it as the secret `HUB_DISPATCH_TOKEN` in every package repository:

```bash
gh secret set HUB_DISPATCH_TOKEN --repo florian-asche/PiCompose-Package-Hello
```

The token expires, so put the expiry date in a calendar. A GitHub App installed on the package repositories avoids that and is the better choice once there are many of them. The workflow only needs a token in the secret `hub-token`, so the change does not touch the package repositories except for the step that creates the token.

To publish a release again without a new build, start the workflow "Publish to APT repository" by hand and enter the repository, channel and release tag.

## APT Repository

The repository is built with [reprepro](https://wiki.debian.org/DebianRepository/SetupWithReprepro) and served as static files from the `gh-pages` branch. The workflow `publish.yml` adds the new packages to that branch and signs the metadata. Only one publish runs at a time. When several arrive at once, GitHub keeps only the newest waiting run, so start the missed one again by hand if a release does not show up.

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
2. In the repository settings (Settings, Environments), create the environment `apt-publish`. Under "Deployment branches and tags" restrict it to the branch `main`, because the publish workflow always runs on the default branch, and require a reviewer if wanted. Without that restriction every branch can use the signing secret.
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

- The signing subkey expires after two years. Extend it with the master key (`gpg --edit-key <FINGERPRINT>`, `key 1`, `expire`), export it again and replace the secret. Devices keep the old public key with the old expiry date, so they need the updated `picompose-archive-keyring.gpg` before the old expiry. This is what the package `picompose-archive-keyring` is for.
- reprepro keeps its database in `db/` inside the repository tree, so it lives on the `gh-pages` branch and is served publicly. It contains only package metadata.
- GitHub Pages has a soft size limit of about 1 GB. Large packages (for example a Python virtual environment for the voice assistant) have to be pruned regularly or the pool has to move to object storage.

## Troubleshooting

- **lintian fails the build:** The container output lists the tags. Fix them or add an override in `debian/<package>.lintian-overrides` with a comment explaining why. The tag `latest-changelog-entry-without-new-date` means the new changelog entry is not newer than the previous one.
- **`apt-get build-dep` fails:** `Build-Depends` in `debian/control` names a package that does not exist in `trixie`.
- **A release does not show up:** Check the run of the package repository (the step "Tell the APT repository to publish" fails when `HUB_DISPATCH_TOKEN` is missing or expired), then the run "Publish to APT repository" here. `check-debs.py` refuses repositories that are not in `sources.yml`, package names that are not listed and versions that do not fit the channel.
- **Reprepro refuses a package:** The same version with different content is already in the repository. Raise the version.
