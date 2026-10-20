# Changelog

## 1.1.0 — 2026-10-20

- Added a prebuilt amd64 Debian package for Pop!_OS 24.04/COSMIC, with an independent executable, desktop entry and icons.
- Added a tag-triggered Ubuntu 24.04 release workflow, runtime dependency detection, isolated dpkg install/removal checks and APT dependency simulation.
- Included complete source archives with vendored Cargo dependencies and SHA256 sums, and documented migration from the manual user installation.

## 1.0.0 — 2026-10-20

- Recovered the graphs-only modification after a project-folder move left its desktop shortcut pointing at the old location.
- Ported the overlay to upstream `6b160c0356280948943c1ada822d6b916c7488d9` and preserved the updated Portuguese translations.
- Enabled graphs-only mode by default for new profiles, retaining the menu toggle and saved preferences.
- Added a user installer independent of the checkout path, executable checksums, atomic binary switching, previous-version rollback and shortcut backup.
- Added pinned builds, explicit upstream updates and weekly compatibility builds.
