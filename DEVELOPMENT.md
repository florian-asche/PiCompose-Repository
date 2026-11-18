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
  debian/                                    sources.yml            which repositories may publish
  .github/workflows/*.yml  --calls-->        package-version.yml    version, changelog, pre-release
        |                                    package-tag-build.yml  build of a tag
        | 1. raise the version, tag          package-build.yml      build of other branches (dev)
        | 2. build in a container            package-pr-check.yml   label check
        | 3. upload the .deb as artifact     publish.yml            check, sign, publish
        | 4. start publish.yml  -----------> 5. download the artifacts of that run
                                             6. check, sign, add to the suite
```

The package repository never sees the signing key. The call only says which repository, channel and workflow run to publish. `publish.yml` downloads the packages itself from the artifacts of that run, and only if the repository is listed in `sources.yml`, the run is a build of a version tag of that repository itself (a pre-release for `trixie-nightly`, a release for `trixie`), the package names are the listed ones and the version is a plain release version. A leaked token can therefore only publish builds of tags that exist already.

**The version belongs to the package.** It is the first entry of `debian/changelog` in the package repository. The channel is the name of the suite the build is published to.

| Started by | Channel | Result | Version |
| --- | --- | --- | --- |
| Push to `main` (a merged pull request), workflow "Version" | trixie-nightly | commit "Version x.y.z", tag `v<version>` as pre-release, suite `trixie-nightly` | the next version, written to `debian/changelog` |
| Pre-release turned into a release in the GitHub UI | trixie | suite `trixie` | the version of the tag |
| Push to any other branch, pull request from a fork | dev | workflow artifact, kept for 14 days | `<version>+dev<timestamp>.<sha>` |

1. **Pull request:** Every pull request needs exactly one of the labels `major`, `minor` and `patch`. It decides how the version is raised when the pull request is merged. The check "Version label" fails until the label is set. The label can be set by hand or by ticking one box under "Version bump" in the pull request description. Pull requests of Dependabot get `patch`. Make the check required in the branch protection of `main`.
2. **Merge to `main`:** The workflow "Version" looks up the commits since the last change of `debian/changelog` with their merged pull requests. The highest label wins, the version is raised accordingly, for example `1.2.3` to `1.3.0` for `minor`. It adds a changelog entry with the titles of the pull requests and commits `debian/changelog` to `main` (the commit "Version 1.3.0"). It fails if a pull request has no or more than one label or a commit has no pull request. Start it by hand with a level to get past that.
3. **Pre-release:** The workflow creates the tag `v1.3.0` on that commit as a pre-release with the release notes GitHub generates for the pull requests since the last tag, and starts the workflow "Build and publish a version" on the tag.
4. **Build:** The tag is built and published to `trixie-nightly`.
5. **Release:** In the GitHub UI, turn the pre-release into a release. That builds the tag again and publishes the same version to `trixie`. The release notes are generated again for all pull requests since the last release. Because the tag is the build, builds are linked to their commit.
6. **Branches:** Changes that are tried before they are merged build as dev. The version installs as an upgrade of the last release and nothing is published.

- `debian/changelog` is part of the package (`/usr/share/doc/<package>/changelog.gz`, shown by `apt changelog`), so the package contains the whole history.
- A suite holds one version per package. A newer version replaces the previous one. The suite `trixie-nightly` takes the newest build even if its version is lower.
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
  package-version.yml   reusable workflow: raise the version, changelog, tag as pre-release
  package-tag-build.yml reusable workflow: build a tag (pre-release: trixie-nightly, release: trixie)
  package-build.yml     reusable workflow: dev builds of other branches (and the previous flow)
  package-release.yml   reusable release workflow of the previous flow, still used by the keyring
  package-pr-check.yml  reusable check that a pull request has a version label
  publish.yml           publish workflow, started by a package repository after a build
  ci.yml                lint of this repository
```

## Adding a Package

1. Create a repository `PiCompose-Package-<Name>` from the template [PiCompose-Package-Software-Hello](https://github.com/florian-asche/PiCompose-Package-Software-Hello) and follow its README.
2. Add the repository and its package names to `sources.yml` in this repository. Publishing is refused until this is merged.
3. Add the secret `HUB_DISPATCH_TOKEN` to the package repository (see "Dispatch token" below).
4. In the branch protection of `main` of the package repository, require the check "Version label". Allow the workflows to push to `main` (or exempt `github-actions[bot]`), because the build commits `debian/changelog` there.
5. Merge a pull request to publish the first build to `trixie-nightly` (the workflow "Version" creates the first pre-release), then add the package to the table in `README.md`.

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
./scripts/build-package.sh ../PiCompose-Package-Software-Hello amd64
```

The `.deb` files end up in `out/`. The script installs the build dependencies in a fresh container, runs `dpkg-buildpackage` and then `lintian`. Errors reported by lintian fail the build. The `debian/changelog` of the repository is used as it is. To build like a dev build, pass `--version <version> --notes-file <file>` to add an entry, see `scripts/build-package.sh`.

Other architectures run through QEMU emulation when your host is not that architecture, which is slow. Register the emulators once with `docker run --privileged --rm tonistiigi/binfmt --install all`.

## Dispatch token

The package repository tells this repository to publish by starting the workflow `publish.yml` (`workflow_dispatch`), which needs a token that may run workflows of this repository. Create a fine-grained personal access token for the owner `florian-asche`, restricted to the repository `PiCompose-Repository` with the permission "Actions: Read and write" and nothing else, so it cannot change any code, and store it as the secret `HUB_DISPATCH_TOKEN` in every package repository:

```bash
gh secret set HUB_DISPATCH_TOKEN --repo florian-asche/PiCompose-Package-Software-Hello
```

The token expires, so put the expiry date in a calendar. A GitHub App installed on the package repositories avoids that and is the better choice once there are many of them. The workflow only needs a token in the secret `hub-token`, so the change does not touch the package repositories except for the step that creates the token.

To publish a build again, start the workflow "Publish to APT repository" by hand and enter the repository, the channel (`trixie` or `trixie-nightly`) and the ID of the workflow run of the package repository.

## Versions of the shared workflows

The package repositories call the reusable workflows of this repository with a version, for example `uses: florian-asche/PiCompose-Repository/.github/workflows/package-version.yml@v1.0.0`, not with `@main`. Dependabot (ecosystem `github-actions`) proposes the newer tags as pull requests in every package repository, so a change of the workflows reaches the packages only through a reviewed pull request.

- Release a new version of the workflows by creating a release with the tag `vMAJOR.MINOR.PATCH` of this repository. Raise the major version when a package repository has to change its caller workflows (new inputs, new permissions or secrets).
- The reusable workflows check out the scripts of this repository at exactly the commit of the called version (they look it up in `referenced_workflows` of the run), so workflows and scripts always match. The caller workflows therefore need the permission `actions: read`.
- Third-party actions are pinned to a commit with the version in a comment (`# v4.4.0`), Dependabot updates both.

## Security

- The signing key exists only in the environment `apt-publish` of this repository. Restrict the environment to the branch `main` and never add workflows that sign anything outside of it.
- `HUB_DISPATCH_TOKEN` can only start workflows of this repository. The only workflow that uses the signing key and accepts input is `publish.yml`, and it publishes only packages of a successful tag build of a listed repository. Do not add a workflow that changes the APT repository without such a check, because everyone with the token could start it.
- Give the token only to the workflow of a package repository that needs it (`tag-build.yml`). `build.yml`, which builds every branch and pull request, has no access to the secret. Whoever can push a branch to a package repository can change its workflows, so keep the number of people with write access small and require pull requests for `main`.
- Shared workflows put values of the event or of inputs into environment variables and never into the script text, and the jobs that build package code have read-only permissions and do not keep the token of the checkout.

## APT Repository

The repository is built with [reprepro](https://wiki.debian.org/DebianRepository/SetupWithReprepro) and served as static files from the `gh-pages` branch. The workflow `publish.yml` adds the new packages to that branch and signs the metadata. Only one publish runs at a time. When several arrive at once, GitHub keeps only the newest waiting run, so start the missed one again by hand if a build does not show up.

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
- **A build does not show up:** Check the run of the package repository (the step "Tell the APT repository to publish" fails when `HUB_DISPATCH_TOKEN` is missing or expired), then the run "Publish to APT repository" here. The publish workflow refuses runs that are not a build of a tag of the repository itself, and `check-debs.py` refuses repositories that are not in `sources.yml`, package names that are not listed and versions that are not plain release versions.
- **The build cannot push `debian/changelog`:** `main` is protected and does not allow the workflow to push. Exempt `github-actions[bot]` or allow it in the ruleset.
- **Reprepro refuses a package:** The same version with different content is already in the repository. Raise the version.
