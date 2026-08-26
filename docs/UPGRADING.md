# Upgrading to version 3

Version 3 is a deliberate breaking release. It removes version 2 compatibility
names and separates repository bootstrap source from the OTA-managed device
application. Back up the device filesystem before erasing or flashing it.

## Known consumers

The compatibility audit on 2026-08-25 identified one concrete downstream
application:

- `smysnk/my-grow` is remote-only and is not checked out in this workspace. Its
  `src/main.py` still exposes `start(env, requests, logger, time, updater)` and
  must be migrated before deploying version 3 of the bootstrap.

No signature detection, dual runtime path, or permanent compatibility alias is
provided. Other application repositories should be searched for the removed
names before their bootstrap is upgraded.

## Host and repository migration

1. Create a fresh virtual environment and run `make install-dev`.
2. Change repository bootstrap paths from `src/` to `device/`. Device paths
   `/src`, `/src.next`, and `/src.previous` still refer to the OTA-managed
   application and do not change.
3. Copy `device/env.example.py` to the ignored `device/env.local.py` and migrate
   settings. The generated hardware-CI configuration now lives at
   `build/device-env.py`.
4. Replace `RSHELL_PORT` and `MPREMOTE_PORT` with `SERIAL_PORT`.
5. Replace `make image` with `make flash` and `make rsync` with `make deploy`.
6. Remove `githubUsername`, `logInclude`, and `logExclude` from local settings.
   Private repositories use the optional Bearer `githubToken`.
7. Stop importing `lib.base64`, `lib.logger`, or `lib.timew`; those modules have
   been removed.
8. Stop using `IO.readFile()` and `IO.writeFile()`. The supported methods are
   `read_file()` and `write_file()`.
9. Do not rely on updater-owned `HEAD`, `POST`, `PUT`, `PATCH`, or `DELETE`
   request helpers. The bootstrap transport is verified-HTTPS `GET` only.

`setup.py` and `MANIFEST.in` were removed because this repository does not
publish device modules as a Python source distribution. Host tooling and test
dependencies remain defined in `pyproject.toml`.

## Application migration

Replace:

```python
def start(env, requests, logger, time, updater):
  ...
```

with:

```python
def start(settings, updater):
  ...
```

Applications import standard `time`, networking, and logging facilities for
themselves. Continue calling `updater.confirm()` only after critical startup
has succeeded. Without confirmation, a later reset intentionally restores the
previous application.

An application may arm its own watchdog before critical initialization. If the
watchdog resets the board before `confirm()`, the next boot sees `.ota-pending`
and restores `src.previous`; no updater watchdog hook is needed.

## Validation

Run the local gates:

```sh
make test-python
make test-mpy
make test-live-tls
make firmware
make verify-firmware
```

Then back up the target device and use the single serial-port setting:

```sh
make erase SERIAL_PORT=PORT
make flash SERIAL_PORT=PORT
make deploy SERIAL_PORT=PORT ENV_FILE=device/env.local.py
make smoke-test SERIAL_PORT=PORT
```

## Recovery from a failed migration

Connect with `mpremote` and inspect the root tree. If `.ota-pending` and
`src.previous` are present, a normal reboot should restore the old application.
If the bootstrap files themselves are damaged, deploy them again:

```sh
make deploy SERIAL_PORT=PORT ENV_FILE=device/env.local.py
```

If MicroPython no longer boots, erase, flash, and restore the backed-up
configuration. Erasing cannot be undone and removes application files.

## Firmware OTA

The `ESP32_GENERIC` download page also offers a firmware variant with native
firmware-OTA partitions. This project does not use those partitions. Adding
remote firmware replacement requires a separately designed signed-image,
partition, boot-confirmation, and recovery mechanism.
