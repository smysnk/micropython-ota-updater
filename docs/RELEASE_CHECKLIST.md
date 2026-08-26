# Release checklist

Use this checklist for every MicroPython stable-version update.

## Firmware and tools

- Confirm the release is marked stable on the
  [official board download page](https://micropython.org/download/ESP32_GENERIC/).
- Download the exact board artifact and independently calculate SHA-256.
- Update `manifest.json`, `mpremote`, and `mpy-cross` together. Board,
  artifact, address, chip, and baud metadata belong only in the manifest.
- Run `make firmware verify-firmware` and confirm the flash address against the
  board-specific official instructions.

## Compatibility and security

- Read release notes from the previously supported version through the target.
- Run `make test-python test-mpy`.
- Run `make test-live-tls` and review both bundled CA certificate subjects,
  fingerprints, expiry dates, and the live chains served by GitHub.
- Confirm the RTC/NTP path works before TLS verification.
- Confirm no device source imports deprecated `u`-prefixed modules.
- Review GitHub's REST API version and authentication requirements.

## Failure injection

- Interrupt the download, version-marker write, both directory renames, and
  confirmation; verify that the previous application remains bootable.
- Test no-update, successful update, rollback, rate limiting, bad token, DNS
  failure, Wi-Fi timeout, malformed JSON, and low-storage paths.
- Confirm binary files survive streaming downloads byte-for-byte.

## Hardware

- Run the manual `ESP32 hardware smoke test` workflow on a dedicated board.
- Confirm `sys.implementation.name == 'micropython'` and record `sys.version`.
- Verify GitHub API TLS, raw-content TLS, deployment, hard reset, and REPL.
- Exercise an update from a dedicated fixture repository, call
  `updater.confirm()`, reboot, and verify the installed SHA.
- Leave preview-branch failures non-blocking until a stable release is selected.

## Release

- Update the support matrix and migration notes.
- Review that examples contain no credentials or device-specific secrets.
- Inspect the complete diff and the full Python and MicroPython compiler output.
- Only then create the release commit and tag. Committing, tagging, and pushing
  are deliberately separate operator actions.
