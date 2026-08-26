# CI and hardware validation

Normal CI runs CPython tests and compiles with the stable MicroPython compiler.
A scheduled/manual job compiles against MicroPython's development branch and is
non-blocking. The `ESP32 hardware smoke test` workflow is manual and requires a
self-hosted runner labelled `micropython-esp32`; it erases and flashes the
attached board, deploys the updater, verifies GitHub TLS, and tests a reboot.

## Hardware workflow configuration

- Secrets: `OTA_WIFI_AP`, `OTA_WIFI_PASSWORD`, optionally `OTA_GITHUB_TOKEN`.
- Variables: `OTA_GITHUB_REMOTE`, optionally `OTA_GITHUB_UPDATE_MODE` and
  `OTA_GITHUB_BRANCH`. The update mode defaults to `branch`.

Version 3 migration details, including removed interfaces and the known
downstream consumer, are in [UPGRADING.md](UPGRADING.md).

Return to the [project README](../README.md).
