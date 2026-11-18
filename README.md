# PiCompose-Repository

[![CI](https://github.com/florian-asche/PiCompose-Repository/actions/workflows/build.yml/badge.svg)](https://github.com/florian-asche/PiCompose-Repository/actions/workflows/build.yml) [![GitHub License](https://img.shields.io/github/license/florian-asche/PiCompose-Repository)](https://github.com/florian-asche/PiCompose-Repository/blob/main/LICENSE) [![GitHub last commit](https://img.shields.io/github/last-commit/florian-asche/PiCompose-Repository)](https://github.com/florian-asche/PiCompose-Repository/commits)

Debian packages and the signed APT repository for [PiCompose](https://github.com/florian-asche/PiCompose), the Raspberry Pi image for projects like [linux-voice-assistant](https://github.com/OHF-Voice/linux-voice-assistant).

## Overview

PiCompose installs audio drivers, the audio server configuration, the Docker Compose manager and the voice assistant. Each of these components is a `.deb` package with its own repository, named `PiCompose-Package-<Name>`. This repository is the APT repository they are published to. The PiCompose image then only installs packages from it, and existing devices can update with `apt upgrade`.

- Every package has its own repository with its source, history and releases
- The package repositories build their packages with the reusable workflow of this repository, for Debian `trixie` on `amd64`, `arm64` and `armhf`
- The version belongs to the package: every merged pull request raises it by its label (major, minor or patch) and is published to the suite `trixie-nightly`, a release publishes that version to `trixie`. Other branches are built too, but their packages are only kept as workflow artifacts for 14 days.
- This repository checks, signs and publishes what the listed package repositories release. The signing key exists only here.
- The repository is a set of static files signed with a dedicated GPG key and served by GitHub Pages

## Packages

| Package | Repository | Description |
| --- | --- | --- |
| `picompose-archive-keyring` | [PiCompose-Package-Archive-Keyring](https://github.com/florian-asche/PiCompose-Package-Archive-Keyring) | Signing key and apt source of this repository |
| `picompose-hello` | [PiCompose-Package-Software-Hello](https://github.com/florian-asche/PiCompose-Package-Software-Hello) | Example package and template, tests the pipeline |
| `picompose-core` | [PiCompose-Package-Core](https://github.com/florian-asche/PiCompose-Package-Core) | Docker, compose manager, PipeWire audio and hostname setup (stage 01 of the image) |
| `ha-satellite` | [PiCompose-Package-Software-HA-Satellite](https://github.com/florian-asche/PiCompose-Package-Software-HA-Satellite) | Linux voice assistant and Snapcast compose projects (stage 03) |
| `picompose-driver-2michat-v1` | [PiCompose-Package-Driver-2MicHat-V1](https://github.com/florian-asche/PiCompose-Package-Driver-2MicHat-V1) | ReSpeaker 2-Mics, 4-Mics and 6-Mics Pi HAT (DKMS) |
| `picompose-driver-2michat-v2` | [PiCompose-Package-Driver-2MicHat-V2](https://github.com/florian-asche/PiCompose-Package-Driver-2MicHat-V2) | ReSpeaker 2-Mics Pi HAT V2.0 |
| `picompose-driver-respeaker-lite` | [PiCompose-Package-Driver-ReSpeaker-Lite](https://github.com/florian-asche/PiCompose-Package-Driver-ReSpeaker-Lite) | ReSpeaker Lite |
| `picompose-driver-satellite1` | [PiCompose-Package-Driver-Satellite1](https://github.com/florian-asche/PiCompose-Package-Driver-Satellite1) | Satellite1 |
| `picompose-driver-other` | [PiCompose-Package-Driver-Other](https://github.com/florian-asche/PiCompose-Package-Driver-Other) | Sound cards without a driver |

The packages that may publish are listed in [sources.yml](sources.yml). The packages from `picompose-core` on are prepared and not published yet.

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
sudo apt install picompose-archive-keyring
```

Use the suite `trixie-nightly` instead of `trixie` for builds from `main`.

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for the repository layout, how to add a package, local builds and the release process.

## License

This project is released under the [MIT License](LICENSE).
