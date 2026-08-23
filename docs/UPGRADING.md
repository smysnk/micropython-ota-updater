# Upgrading to the MicroPython 1.28 updater

Version 2 is a breaking upgrade from the original v1.13-era updater. Back up
the device filesystem before erasing or flashing it.

## Host migration

1. Create a fresh virtual environment and run `make install-dev`.
2. Replace `rshell` commands with `mpremote`, or use the compatibility
   `make rsync` and `make repl` aliases temporarily.
3. Copy `src/env.example.py` to the ignored `src/env.local.py` and migrate the
   settings. The new settings are `wifiConnectTimeout`, `httpTimeout`, and
   `otaMinimumFreeBytes`.
4. Run `make test-python test-mpy test-live-tls`.
5. Back up device files with `mpremote cp -r : device-backup/`.
6. Erase and flash the pinned MicroPython 1.28.0 firmware, then deploy with the
   local environment file.

## Application migration

- Use standard module names such as `socket`, `json`, and `ssl`/`tls`; do not
  import `usocket`, `ujson`, or `ussl`.
- Use `network.hostname(name)` instead of `WLAN.config(dhcp_hostname=...)`.
- Ensure the application exports `start(env, requests, logger, time, updater)`.
- Call `updater.confirm()` only after critical startup has succeeded. Without
  confirmation, a later reset intentionally restores the previous application.
- Code that intentionally raises `SystemExit` should be reviewed because modern
  MicroPython performs a soft reset rather than dropping to the REPL.

## Recovery from a failed migration

Connect with `mpremote` and inspect the root tree. If `.ota-pending` and
`src.previous` are present, a normal reboot should restore the old application.
If the bootstrap files themselves are damaged, deploy them again:

```sh
make deploy MPREMOTE_PORT=PORT ENV_FILE=src/env.local.py
```

If MicroPython no longer boots, erase, flash, and restore the backed-up
configuration. Erasing cannot be undone and removes application files.

## Firmware OTA

The `ESP32_GENERIC` download page also offers a firmware variant with native
firmware-OTA partitions. This project does not use those partitions. Adding
remote firmware replacement requires a separately designed signed-image,
partition, boot-confirmation, and recovery mechanism.
