# Using the PiCompose APT repository

The repository serves packages for Debian `trixie` (Raspberry Pi OS based on trixie) for `amd64`, `arm64` and `armhf`.

| Suite | Content |
| --- | --- |
| `trixie` | Releases |
| `trixie-nightly` | Builds from `main` |

## Add the repository

1. Download the signing key:
   ```sh
   sudo curl -fsSL https://florian-asche.github.io/PiCompose-Repository/picompose-archive-keyring.gpg \
     -o /usr/share/keyrings/picompose-archive-keyring.gpg
   ```
2. Create `/etc/apt/sources.list.d/picompose.sources`:
   ```
   Types: deb
   URIs: https://florian-asche.github.io/PiCompose-Repository/
   Suites: trixie
   Components: main
   Signed-By: /usr/share/keyrings/picompose-archive-keyring.gpg
   ```
3. Update and install:
   ```sh
   sudo apt update
   sudo apt install picompose-archive-keyring
   ```
   The package `picompose-archive-keyring` takes over the key and the source file from here on, so the key can be renewed with a normal upgrade. dpkg asks whether to replace the source file you created. Answer yes, or use `-o Dpkg::Options::=--force-confnew` in scripts.

Replace `trixie` with `trixie-nightly` to get builds from `main`. Nightly builds can break, so do not use them on devices you rely on. Builds of other branches are not in the repository. They are workflow artifacts of the package repository and are kept for 14 days.

A suite holds one version per package. A newer release or nightly build replaces the previous one in that suite.

## Remove the repository

```sh
sudo rm /etc/apt/sources.list.d/picompose.sources /usr/share/keyrings/picompose-archive-keyring.gpg
sudo apt update
```
