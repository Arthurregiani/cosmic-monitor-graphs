# Validation — 2026-10-20

Environment: Pop!_OS / COSMIC, Linux x86_64, Rust/Cargo 1.99.0.

- Cause reproduced: the pre-existing desktop entry referenced the old project location. The source folder had moved; the executable at the new location started successfully.
- Original modified 1.10.0: `cargo build --release --locked` passed. The running dashboard was visually inspected: CPU, memory, disk, network and AMD GPU/VRAM cards, without application/process lists.
- New overlay: ported to upstream `6b160c0356280948943c1ada822d6b916c7488d9`. `python3 monitor.py install` and `python3 monitor.py check --latest` passed using a shared local Cargo target cache. The pinned and latest upstream commits were identical at the time of validation.
- Initial [GitHub Actions run](https://github.com/Arthurregiani/cosmic-monitor-graphs/actions/runs/39483192500) passed all three jobs: installer, pinned release build and latest-upstream release build.
- Four installer integration tests passed, including relocation, paths with spaces, failed patch/build recovery, repeated installs, previous-version switching and desktop-entry backup.
- Generated desktop entry passed `desktop-file-validate`.
- Real installation rollback switched to the original modified build and back to the new build. Metadata and SHA256 matched the selected executables.
- New installed executable started through the stable launcher and remained running. Saved graphs-only preference was retained. The user confirmed that the graphs display was correct after the stable installation. The full dashboard toggle and window-resize interactions were not manually exercised during this validation.
- No changes were made to `/usr/bin/cosmic-monitor` or the distribution desktop entry.

The weekly GitHub workflow is a compilation check. A passing build does not replace visual testing on a COSMIC desktop. Nonfatal locale, Wayland icon-protocol and desktop-entry parsing messages were observed at launch; the original build emitted the same messages.
