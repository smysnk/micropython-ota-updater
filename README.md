# MicroPython OTA Updater

An application-file updater for MicroPython devices. It follows a GitHub
branch, downloads a changed `src` tree into a staging directory, and swaps it
into place after the download succeeds.

This project updates Python application files. Firmware upgrades are performed
from a host with `make flash`; it does not rewrite the MicroPython firmware over
the air.

## Supported platform

| Board profile | MicroPython | Status |
| --- | --- | --- |
| `ESP32_GENERIC` | `v1.28.0` (2026-04-06) | Production |
| MicroPython development branch | Latest preview | Non-blocking weekly compiler check |

Firmware and board instructions are published on the
[official ESP32_GENERIC download page](https://micropython.org/download/ESP32_GENERIC/).

The firmware URL and SHA-256 checksum are pinned in
`firmware/manifest.json`. Other ESP32 variants must be added with their own
firmware filename, flash address, checksum, and hardware validation before they
are described as supported.

## Development

```sh
python3 -m venv .venv
. .venv/bin/activate
make install-dev
make test-python
make test-mpy
```

`make test-python` runs the host-side unit and failure-injection tests.
`make test-mpy` compiles every device module with MicroPython 1.28 `mpy-cross`.
`make test` produces the Test Station report in `artifacts/test-station/`.

The network-dependent certificate-chain check is separate:

```sh
make test-live-tls
```

## Configure a device

Keep local credentials out of the tracked `src/env.py` file:

```sh
cp src/env.example.py src/env.local.py
```

Edit `src/env.local.py`, then deploy it with `ENV_FILE=src/env.local.py`.
A fine-grained GitHub token is optional for public repositories and should have
read-only access to the application repository. Tokens are sent with Bearer
authentication.

The bundled CA roots validate `api.github.com` and
`raw.githubusercontent.com`. They intentionally reject unrecognised HTTPS
hosts. Certificate fingerprints and expiry dates must be reviewed during every
release; see `docs/RELEASE_CHECKLIST.md`.

## Flash and deploy

The commands use `esptool` and the officially supported `mpremote` utility.

```sh
# Destructive: erases firmware and all files on the device.
make erase RSHELL_PORT=/dev/cu.usbserial-0001

# Downloads the pinned artifact, verifies SHA-256, and flashes it.
make flash RSHELL_PORT=/dev/cu.usbserial-0001

# Copies the updater and local configuration, then performs a soft reset.
make deploy MPREMOTE_PORT=/dev/cu.usbserial-0001 ENV_FILE=src/env.local.py

make repl MPREMOTE_PORT=/dev/cu.usbserial-0001
make smoke-test MPREMOTE_PORT=/dev/cu.usbserial-0001
```

`make firmware` downloads without flashing, while `make verify-firmware`
rechecks an existing image. `make image` and `make rsync` remain compatibility
aliases for `make flash` and `make deploy`.

## Application contract

The GitHub application repository must contain a `src` directory with a
`main.py` module exposing `start`:

```python
def start(env, requests, logger, time, updater):
  # Perform enough initialization to know this version can run, then confirm.
  updater.confirm()

  # Enter the application's normal loop.
  while True:
    time.sleep(1)
```

Confirmation is important. Until `updater.confirm()` runs, the previous
application remains in `src.previous` and `.ota-pending` marks the new version
as unconfirmed. If the device resets first, the next boot restores the previous
application. An exception raised while importing or starting the new
application also triggers rollback and reset.

## Update sequence

1. Recover any interrupted or unconfirmed previous update.
2. Compare `src/.version` with the current GitHub branch SHA.
3. Check free filesystem space and download into `src.next`.
4. Write and read back `src.next/.version`.
5. Create `.ota-pending`, rename `src` to `src.previous`, and rename
   `src.next` to `src`.
6. Start the application. The application calls `updater.confirm()` when its
   critical initialization has succeeded.

The updater streams file bodies in 512-byte chunks, closes responses on all
handled failures, verifies TLS hostnames and certificate chains, and leaves the
current application untouched if staging fails.

## Recovery

Automatic recovery is conservative: an update with both `.ota-pending` and
`src.previous` is rolled back at the beginning of the next updater run. For
manual inspection:

```sh
mpremote connect /dev/cu.usbserial-0001 fs tree -sh :
mpremote connect /dev/cu.usbserial-0001 fs cat :.ota-pending
```

Do not remove `src.previous` while `.ota-pending` exists. Full recovery steps
and the migration notes from the earlier release are in `docs/UPGRADING.md`.

## CI and hardware validation

Normal CI runs CPython tests and compiles with the stable MicroPython compiler.
A scheduled/manual job compiles against MicroPython's development branch and is
non-blocking. The `ESP32 hardware smoke test` workflow is manual and requires a
self-hosted runner labelled `micropython-esp32`; it erases and flashes the
attached board, deploys the updater, verifies GitHub TLS, and tests a reboot.

Hardware workflow configuration:

- Secrets: `OTA_WIFI_AP`, `OTA_WIFI_PASSWORD`, optionally `OTA_GITHUB_TOKEN`.
- Variables: `OTA_GITHUB_REMOTE`, optionally `OTA_GITHUB_BRANCH`.
