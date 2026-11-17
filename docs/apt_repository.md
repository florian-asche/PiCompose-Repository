# Using the PiCompose APT repository

The repository serves packages for Debian `trixie` (Raspberry Pi OS based on trixie) for `amd64`, `arm64` and `armhf`.

| Suite | Content |
| --- | --- |
| `trixie` | Releases (tags) |
| `trixie-nightly` | Builds from `main` |
| `trixie-test` | Builds from the branch `test`, for trying changes before they are merged |

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
   sudo apt install picompose-hello
   ```

Replace `trixie` with `trixie-nightly` to get builds from `main`, or with `trixie-test` for builds from the branch `test`. Nightly and test builds can break, so do not use them on devices you rely on.

A suite holds one version per package. A newer release, nightly or test build replaces the previous one in that suite.

## Remove the repository

```sh
sudo rm /etc/apt/sources.list.d/picompose.sources /usr/share/keyrings/picompose-archive-keyring.gpg
sudo apt update
```
