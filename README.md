# PiCompose-Repository

[![CI](https://github.com/florian-asche/PiCompose-Repository/actions/workflows/build.yml/badge.svg)](https://github.com/florian-asche/PiCompose-Repository/actions/workflows/build.yml) [![GitHub License](https://img.shields.io/github/license/florian-asche/PiCompose-Repository)](https://github.com/florian-asche/PiCompose-Repository/blob/main/LICENSE) [![GitHub last commit](https://img.shields.io/github/last-commit/florian-asche/PiCompose-Repository)](https://github.com/florian-asche/PiCompose-Repository/commits)

Debian packages and the signed APT repository for [PiCompose](https://github.com/florian-asche/PiCompose), the Raspberry Pi image for projects like [linux-voice-assistant](https://github.com/OHF-Voice/linux-voice-assistant).

## Overview

PiCompose installs audio drivers, the audio server configuration, the Docker Compose manager and the voice assistant. This repository builds each of these components as a `.deb` package and publishes them to an APT repository. The PiCompose image then only installs packages from that repository, and existing devices can update with `apt upgrade`.

- One source tree for all packages (drivers and software), one CI for all of them
- Packages are built for Debian `trixie` on `amd64`, `arm64` and `armhf`
- Stable packages come from tags, nightly builds from `main` and test builds from the branch `test`
- The repository is a set of static files signed with a dedicated GPG key and served by GitHub Pages

## Packages

| Package | Description | Status |
| --- | --- | --- |
| `picompose-hello` | Test package for the build and publish pipeline | available |

All packages for PiCompose (audio drivers, `picompose-core`, audio configuration, the voice assistant) are built in this repository. [PiCompose-Package-Hello](https://github.com/florian-asche/PiCompose-Package-Hello) is the same example package as a standalone repository and serves as a template for a package of its own.

## Usage

Add the repository on a Raspberry Pi OS (trixie) system and install a package. See [docs/apt_repository.md](docs/apt_repository.md) for the details.

```sh
sudo curl -fsSL https://florian-asche.github.io/PiCompose-Repository/picompose-archive-keyring.gpg \
  -o /usr/share/keyrings/picompose-archive-keyring.gpg
sudo tee /etc/apt/sources.list.d/picompose.sources >/dev/null <<'EOF'
Types: deb
URIs: https://florian-asche.github.io/PiCompose-Repository/
Suites: trixie
Components: main
Signed-By: /usr/share/keyrings/picompose-archive-keyring.gpg
EOF
sudo apt update
sudo apt install picompose-hello
```

Use the suite `trixie-nightly` instead of `trixie` for builds from `main`, or `trixie-test` for builds from the branch `test`.

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for the repository layout, how to add a package, local builds and the release process.

## License

This project is released under the [MIT License](LICENSE).
