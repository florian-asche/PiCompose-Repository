# Contributing to PiCompose-Repository

Everybody is invited and welcome to contribute to PiCompose-Repository. Packaging fixes, hardware reports and packages for new hardware are all appreciated.

- Fork the PiCompose-Repository repository.
- Create a branch and make your change. See [DEVELOPMENT.md](../DEVELOPMENT.md) for the package layout, local builds and the release process.
- Build and lint your package locally (`./scripts/build-package.sh <package> <arch>`).
- Raise the version in `debian/changelog` of every package you changed.
- Create a Pull Request against the `main` branch and tick exactly one box under "Types of changes". CI derives the label from it, and the label decides where the PR appears in the release notes.

## Feature suggestions

If you want to suggest a new package or hardware, please open a discussion on GitHub.

## Issue Tracker

If you want to report a problem with a package, the APT repository or the build, please create an issue and use the template. Problems with the images belong in the [PiCompose](https://github.com/florian-asche/PiCompose/issues) repository, problems inside the voice assistant itself in the [linux-voice-assistant](https://github.com/OHF-Voice/linux-voice-assistant/issues) repository.

## AI Policy

AI tools are allowed, but a human is responsible and must review and understand every change. Autonomous agents and unreviewed AI output will be rejected. See [AI_POLICY.md](AI_POLICY.md).
