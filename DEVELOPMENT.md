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
  .github/workflows/*.yml  --calls-->        package-build.yml    build workflow
        |                                    package-release.yml  release workflow
        | 1. build in a container            package-pr-check.yml label check
        | 2. upload the .deb as artifact     publish.yml          check, sign, publish
        | 3. start publish.yml  -----------> 4. download the artifacts of that run
                                             5. check, sign, add to the suite
```

The package repository never sees the signing key. The call only says which repository, channel and workflow run to publish. `publish.yml` downloads the packages itself from the artifacts of that run, and only if the repository is listed in `sources.yml`, the run is a build of `main` of that repository itself (nightly) or a release (stable), the package names are the listed ones and the version is a plain release version. A leaked token can therefore only publish builds of `main` that exist already.

**The version belongs to the package.** It is the first entry of `debian/changelog` in the package repository.

| Started by | Channel | Result | Version |
| --- | --- | --- | --- |
| Push to `main` (a merged pull request) | nightly | suite `trixie-nightly` | the next version, written to `debian/changelog` |
| Workflow "Release" | stable | suite `trixie` and a GitHub release with the tag `v<version>` | the version of `debian/changelog` |
| Push to any other branch, pull request from a fork | dev | workflow artifact, kept for 14 days | `<version>+dev<timestamp>.<sha>` |

1. **Pull request:** Every pull request needs exactly one of the labels `major`, `minor` and `patch`. It decides how the version is raised when the pull request is merged. The check "Version label" fails until the label is set. The label can be set by hand or by ticking one box under "Version bump" in the pull request description. Pull requests of Dependabot get `patch`. Make the check required in the branch protection of `main`.
2. **Merge to `main`:** The workflow looks up the commits since the last change of `debian/changelog` with their merged pull requests. The highest label wins (`patch` if there is none), the version is raised accordingly, for example `1.2.3` to `1.3.0` for `minor`. It adds a changelog entry with the titles of the pull requests, commits `debian/changelog` to `main` (the commit "Version 1.3.0"), builds exactly that version and has it published to `trixie-nightly`. No tag is created. Because it looks at all commits since the last version, a merge whose workflow run was skipped by GitHub is not lost.
3. **Release:** Start the workflow "Release" of the package repository (Actions, Release, Run workflow). It takes the version of `debian/changelog` on `main`, creates the tag `v<version>` on the newest commit with a GitHub release and the notes GitHub generates from the pull requests since the last release, builds the package from the tag and has it published to `trixie`. The tags of a package repository are therefore only releases. A release created by hand in the GitHub UI is not published, and a version that has a tag cannot be released again.
4. **Branches:** Changes that are tried before they are merged build as dev. The version installs as an upgrade of the last release and nothing is published.

- `debian/changelog` is part of the package (`/usr/share/doc/<package>/changelog.gz`, shown by `apt changelog`), so the package contains the whole history.
- A suite holds one version per package. A newer version replaces the previous one. The nightly suite takes the newest build even if its version is lower.
- Packages with `Architecture: all` are built on `amd64` only. Everything else is built for `amd64`, `arm64` and `armhf`.

## Repository Layout

```
sources.yml             package repositories that may publish, with their package names
apt/conf/               reprepro configuration (suites and architectures)
scripts/
  build-package.sh      build one package for one architecture in a container
  arch-matrix.py        print the build matrix (architectures) of a package repository
  package-version.py    raise the version from merged pull request labels, version of dev builds
  make-changelog.py     add a changelog entry to debian/changelog
  check-debs.py         check downloaded .deb files against sources.yml and the channel
  publish-apt.sh        add .deb files to the repository tree and sign it
docs/                   documentation
.github/workflows/
  package-build.yml     reusable build workflow (nightly, dev and stable), called by the package repositories
  package-release.yml   reusable release workflow: tag, release, then a stable build
  package-pr-check.yml  reusable check that a pull request has a version label
  publish.yml           publish workflow, started by a package repository after a release
  ci.yml                lint of this repository
```

## Adding a Package

1. Create a repository `PiCompose-Package-<Name>` from the template [PiCompose-Package-Hello](https://github.com/florian-asche/PiCompose-Package-Hello) and follow its README.
2. Add the repository and its package names to `sources.yml` in this repository. Publishing is refused until this is merged.
3. Add the secret `HUB_DISPATCH_TOKEN` to the package repository (see "Dispatch token" below).
4. In the branch protection of `main` of the package repository, require the check "Version label". Allow the workflows to push to `main` (or exempt `github-actions[bot]`), because the build commits `debian/changelog` there.
5. Merge a pull request to publish the first nightly build, then add the package to the table in `README.md`.

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

The `.deb` files end up in `out/`. The script installs the build dependencies in a fresh container, runs `dpkg-buildpackage` and then `lintian`. Errors reported by lintian fail the build. The `debian/changelog` of the repository is used as it is. To build like a dev build, pass `--version <version> --notes-file <file>` to add an entry, see `scripts/build-package.sh`.

Other architectures run through QEMU emulation when your host is not that architecture, which is slow. Register the emulators once with `docker run --privileged --rm tonistiigi/binfmt --install all`.

## Dispatch token

The package repository tells this repository to publish by starting the workflow `publish.yml` (`workflow_dispatch`), which needs a token that may run workflows of this repository. Create a fine-grained personal access token for the owner `florian-asche`, restricted to the repository `PiCompose-Repository` with the permission "Actions: Read and write" and nothing else, so it cannot change any code, and store it as the secret `HUB_DISPATCH_TOKEN` in every package repository:

```bash
gh secret set HUB_DISPATCH_TOKEN --repo florian-asche/PiCompose-Package-Hello
```

The token expires, so put the expiry date in a calendar. A GitHub App installed on the package repositories avoids that and is the better choice once there are many of them. The workflow only needs a token in the secret `hub-token`, so the change does not touch the package repositories except for the step that creates the token.

To publish a build again, start the workflow "Publish to APT repository" by hand and enter the repository, the channel and the ID of the workflow run of the package repository.

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

- **lintian fails the build:** The container output lists the tags. Fix them or add an override in `debian/<package>.lintian-overrides` with a comment explaining why.
- **`apt-get build-dep` fails:** `Build-Depends` in `debian/control` names a package that does not exist in `trixie`.
- **A build does not show up:** Check the run of the package repository (the step "Tell the APT repository to publish" fails when `HUB_DISPATCH_TOKEN` is missing or expired), then the run "Publish to APT repository" here. The publish workflow refuses runs that are not a build of `main` or a release of the repository itself, and `check-debs.py` refuses repositories that are not in `sources.yml`, package names that are not listed and versions that are not plain release versions.
- **The build cannot push `debian/changelog`:** `main` is protected and does not allow the workflow to push. Exempt `github-actions[bot]` or allow it in the ruleset.
- **Reprepro refuses a package:** The same version with different content is already in the repository. Raise the version.
