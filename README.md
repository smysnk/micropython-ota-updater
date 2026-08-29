# MicroPython OTA Updater

https://github.com/user-attachments/assets/9ddcae3f-b544-4854-a867-c9ce3dd92f7a

An application-file updater for MicroPython devices. It follows a configured
GitHub branch or the latest published GitHub Release, downloads a changed `src`
tree into a staging directory, and swaps it into place after the download
succeeds.

This project updates Python application files. Firmware upgrades are performed
from a host with `make flash`; it does not rewrite the MicroPython firmware over
the air.

Read the companion article,
[MicroPython OTA updates with GitHub and ESP32](https://smysnk.com/blog/micropython-ota-updates-github-esp32),
for the design background and a complete walkthrough.

## Quick start

This path installs the updater on one `ESP32_GENERIC` board and starts a minimal
application from GitHub.

### 1. Create the application repository

For this example, use the preconfigured
[`micropython-ota-quickstart`](https://github.com/smysnk/micropython-ota-quickstart)
repository.
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

Before deploying, replace both Wi-Fi placeholders in `device/env.local.py`.
The example already points to the public quickstart application; replace
`githubRemote` when you are ready to deploy your own repository:

```python
'wifiAP': 'YOUR_WIFI_NAME',
'wifiPassword': 'YOUR_WIFI_PASSWORD',
'githubRemote': 'https://github.com/smysnk/micropython-ota-quickstart',
```

Then choose one update mode.

**Track a branch:** install the current commit from the selected branch. This
is the default and the simplest option while developing.

```python
'githubUpdateMode': 'branch',
'githubRemoteBranch': 'main',
```

**Track GitHub Releases:** install the commit tagged by the latest published
non-draft, non-prerelease release.

```python
'githubUpdateMode': 'release',
```

Release mode ignores `githubRemoteBranch`. It resolves the release tag to an
immutable commit SHA and installs `src` from that commit; attached release
assets are not downloaded.

### 4. Flash and deploy

Connect one ESP32 over USB and confirm that `mpremote` lists a USB serial
device:

```sh
python -m mpremote devs
```

On macOS, the device normally looks like `/dev/cu.usbserial-*` or
`/dev/cu.SLAB_USBtoUART`. Do not continue if the list only contains Bluetooth
or debug-console ports.

> **Warning:** `erase` removes the existing firmware and every file on the
> selected device.

Erase the board and install MicroPython:

```sh
make erase flash
```

Then copy the updater and your local configuration to the board:

```sh
make deploy
make repl
```

After the REPL connects, press `Ctrl-D` to restart the device and see the
complete boot sequence. On its first boot, the updater connects to Wi-Fi and
downloads the quickstart application's `src/` directory from GitHub, so the
first startup can take a little longer. It should finish by printing:

```text
ota-controller: OTA application started
ota-controller: heartbeat 1
ota-controller: heartbeat 2
```

> **Tip:** The commands automatically select the connected board. If more than
> one compatible serial device is connected, specify one with, for example,
> `SERIAL_PORT=/dev/cu.usbserial-0001 make deploy`. Run `make help` for the
> other commands that accept this setting.

### 5. Publish an update

In branch mode, edit `src/main.py`, commit it, and push it to the configured
branch. In release mode, also create a GitHub Release whose tag points to the
commit you want to deploy.

Press the board's reset button or enter `Ctrl-D` in the REPL. The updater will
install the selected commit and retain the previous application until the new
version calls `updater.confirm()`.

If you later change modes in `device/env.local.py`, run `make deploy` before
resetting the device. Selecting the same commit causes no reinstall; selecting
a different commit installs it even if it is older.

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
2. Compare `src/.version` with the selected branch or release commit SHA.
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
