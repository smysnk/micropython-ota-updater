# MicroPython OTA Updater

An application-file updater for MicroPython devices. It follows a GitHub
branch, downloads a changed `src` tree into a staging directory, and swaps it
into place after the download succeeds.

This project updates Python application files. Firmware upgrades are performed
from a host with `make flash`; it does not rewrite the MicroPython firmware over
the air.

## Quick start

This path installs the updater on one `ESP32_GENERIC` board and starts a minimal
application from GitHub.

### 1. Create the application repository

For this example, use the preconfigured
[`micropython-ota-quickstart` repository](https://github.com/smysnk/micropython-ota-quickstart).
[Create your own public repository from this template](https://github.com/smysnk/micropython-ota-quickstart/generate);
it already includes the required `src/main.py` and `start(settings, updater)`
entrypoint.

### 2. Install the host tools

```sh
git clone https://github.com/smysnk/micropython-ota-updater.git
cd micropython-ota-updater

python3 -m venv .venv
. .venv/bin/activate
make install
```

### 3. Configure the device

```sh
cp device/env.example.py device/env.local.py
```

Change these four values in `device/env.local.py`:

```python
'wifiAP': 'YOUR_WIFI_NAME',
'wifiPassword': 'YOUR_WIFI_PASSWORD',
'githubRemote': 'https://github.com/YOUR_NAME/YOUR_APPLICATION',
'githubRemoteBranch': 'main',
```

### 4. Flash and deploy

Connect one ESP32 over USB and confirm that `mpremote` can see it:

```sh
python -m mpremote devs
```

> **Warning:** `erase` removes the existing firmware and every file on the
> selected device.

With one compatible board connected, automatic port detection is usually
enough:

```sh
make erase flash deploy SERIAL_PORT=auto
make repl SERIAL_PORT=auto
```

The REPL should begin printing:

```text
ota-controller: OTA application started
ota-controller: heartbeat 1
ota-controller: heartbeat 2
```

### 5. Publish an update

Edit `src/main.py` in the application repository created from the template,
commit it, and push it to GitHub. Press the board's reset button or enter
`Ctrl-D` in the REPL. The updater will install the new branch commit and retain
the previous application until the new version calls `updater.confirm()`.

The sections below cover the application contract and recovery in more detail.

## Application contract

The GitHub application repository must contain a `src` directory with a
`main.py` module exposing `start`:

```python
import machine
import time


def start(settings, updater):
  # Optional: a reset before confirmation restores src.previous on next boot.
  watchdog = machine.WDT(timeout=60000) if settings.get('watchdog') else None

  # Perform enough initialization to know this version can run, then confirm.
  updater.confirm()

  # Enter the application's normal loop.
  while True:
    if watchdog:
      watchdog.feed()
    time.sleep(1)
```

Confirmation is important. Until `updater.confirm()` runs, the previous
application remains in `src.previous` and `.ota-pending` marks the new version
as unconfirmed. If the device resets first, the next boot restores the previous
application. An exception raised while importing or starting the new
application also triggers rollback and reset.

HTTP, logging, and time are application concerns in version 3. Import the
standard MicroPython modules the application needs instead of expecting the
bootstrap to inject wrappers.

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

![MicroPython OTA Updater startup flow](docs/micropython-ota-updater-startup.svg)

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

## Supported platform

The updater is intended for recent network-capable MicroPython builds with
verified HTTPS support, a writable filesystem with directory and rename
operations, and enough storage for the active application, a staged download,
and a rollback copy. MicroPython 1.23 and newer releases are likely compatible.

The currently validated baseline is `ESP32_GENERIC` with MicroPython 1.28.0,
as pinned in `manifest.json`. CI also compiles against MicroPython's development
branch. Other boards and older releases may work, but should be treated as
unverified until their TLS, filesystem, memory, and reset behaviour are tested
on hardware.

Project guides: [Development](docs/DEVELOPMENT.md) ·
[CI and hardware validation](docs/CI_AND_HARDWARE_VALIDATION.md)
