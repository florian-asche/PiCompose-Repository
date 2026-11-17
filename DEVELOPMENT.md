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
        | 3. start publish.yml  -----------> 4. download .deb from the release
                                             5. check, sign, add to the suite
```

The package repository never sees the signing key. The dispatch only says which repository, channel and release to publish. `publish.yml` downloads the packages itself from the GitHub release, and only if the repository is listed in `sources.yml` and the package names and versions fit the channel. A leaked dispatch token can therefore only publish what is already in a release of a listed repository.

| Started by | Channel | Result | Version |
| --- | --- | --- | --- |
| Workflow "Release" with a version | stable | suite `trixie` | the version you enter |
| Push to `main` | nightly | suite `trixie-nightly` | `<last release>+git<timestamp>.<sha>` |
| Push to any other branch, pull request from a fork | dev | workflow artifact, kept for 14 days | `<last release>+dev<timestamp>.<sha>` |

- **`debian/changelog` holds the releases.** It lives in the package repository and ends up in the package (`/usr/share/doc/<package>/changelog.gz`, shown by `apt changelog`), so the package contains the whole history.
- **Release:** You decide the version. Start the workflow "Release" of the package repository (Actions, Release, Run workflow) and enter a version like `1.2.3` that is higher than the last release. The workflow writes the changelog entry from the notes GitHub generates from the pull requests merged since the last release, commits `debian/changelog` to `main`, tags that commit `v<version>`, creates the GitHub release and builds and publishes the packages from the tag. A release created by hand in the GitHub UI is not published.
- **Nightly:** Without a release, the version is the last release with a suffix: `1.2.3+git20261117071500.abc1234`. The `+` sorts it above `1.2.3` and below every later release, and the timestamp makes a newer build sort above an older one. The build adds a changelog entry made from the title and description of the pull request of the commit (or the commit message) to the package only, nothing is committed. Every build overwrites the file of the previous one: the rolling pre-release `nightly` of the package repository and the nightly suite hold only the newest build.
- **Dev:** Branches are for changes that are tried before they are merged, so the version is `<last release>+dev<timestamp>.<sha>`, which installs as an upgrade of the last release. Nothing is published and there is no APT suite for it.
- The package repository only needs a pre-release with the tag `nightly` as carrier for the files of the nightly build. Every push deletes and recreates it.
- A suite holds one version per package. The stable suite takes a newer version, the nightly suite takes the newest build even if its version is lower than the one before.
- Packages with `Architecture: all` are built on `amd64` only. Everything else is built for `amd64`, `arm64` and `armhf`.

## Repository Layout

```
sources.yml             package repositories that may publish, with their package names
apt/conf/               reprepro configuration (suites and architectures)
scripts/
  build-package.sh      build one package for one architecture in a container
  arch-matrix.py        print the build matrix (architectures) of a package repository
  package-version.py    compute the version of a nightly or dev build, check the version of a release
  make-changelog.py     add a changelog entry from release or pull request text
  check-debs.py         check downloaded .deb files against sources.yml and the channel
  publish-apt.sh        add .deb files to the repository tree and sign it
docs/                   documentation
.github/workflows/
  package-build.yml     reusable build workflow (nightly, dev and stable), called by the package repositories
  package-release.yml   reusable release workflow: changelog, tag, release, then a stable build
  publish.yml           publish workflow, started by a package repository after a release
  ci.yml                lint of this repository
```

## Adding a Package

1. Create a repository `PiCompose-Package-<Name>` from the template [PiCompose-Package-Hello](https://github.com/florian-asche/PiCompose-Package-Hello) and follow its README.
2. Add the repository and its package names to `sources.yml` in this repository. Publishing is refused until this is merged.
3. Add the secret `HUB_DISPATCH_TOKEN` to the package repository (see "Dispatch token" below), and allow the Actions of the package repository to write (Settings, Actions, General, Workflow permissions, or the permissions of the workflows are enough). If `main` is protected, the workflow "Release" has to be allowed to push to it, because it commits `debian/changelog`.
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

The `.deb` files end up in `out/`. The script installs the build dependencies in a fresh container, runs `dpkg-buildpackage` and then `lintian`. Errors reported by lintian fail the build. The `debian/changelog` of the repository is used as it is. To build like a nightly, pass `--version <version> --notes-file <file>` to add an entry, see `scripts/build-package.sh`.

Other architectures run through QEMU emulation when your host is not that architecture, which is slow. Register the emulators once with `docker run --privileged --rm tonistiigi/binfmt --install all`.

## Dispatch token

The package repository tells this repository to publish by starting the workflow `publish.yml` (`workflow_dispatch`), which needs a token that may run workflows of this repository. Create a fine-grained personal access token for the owner `florian-asche`, restricted to the repository `PiCompose-Repository` with the permission "Actions: Read and write" and nothing else, so it cannot change any code, and store it as the secret `HUB_DISPATCH_TOKEN` in every package repository:

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

- **lintian fails the build:** The container output lists the tags. Fix them or add an override in `debian/<package>.lintian-overrides` with a comment explaining why.
- **`apt-get build-dep` fails:** `Build-Depends` in `debian/control` names a package that does not exist in `trixie`.
- **A release does not show up:** Check the run of the package repository (the step "Tell the APT repository to publish" fails when `HUB_DISPATCH_TOKEN` is missing or expired), then the run "Publish to APT repository" here. `check-debs.py` refuses repositories that are not in `sources.yml`, package names that are not listed and versions that do not fit the channel.
- **Reprepro refuses a package:** The same version with different content is already in the repository. Raise the version.
