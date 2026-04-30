# MicroPython OTA Updater

## Overview

Based off of [rdehuyss's MicroPython OTA Updater](https://github.com/rdehuyss/micropython-ota-updater). This MicroPython Over-The-Air Updater will follow a GitHub branch, checking for updates on boot.  Will update if HEAD is not current (other release strategies may be added later).

> Note: due to a bug in the SSL library of ESP8266 devices, micropython-ota-updater cannot be used on these devices. See https://github.com/rdehuyss/micropython-ota-updater/issues/6 and https://github.com/micropython/micropython/issues/6737

## Getting started

Edit `src/env.py` to fill in WiFi credentials, GitHub remote repository / branch and optional [GitHub credentials](https://github.com/settings/tokens) to increase API limits (60 per hour to 5000). Deploy!

For an example implementation check out the [my-grow project](https://github.com/smysnk/my-grow/blob/master/src/main.py).

## Development

This repo uses standard Python packaging metadata in `pyproject.toml`.

```sh
python3 -m venv .venv
. .venv/bin/activate
make install-dev
make test
```

`make test` runs the pytest suite through Test Station and writes the HTML/JSON report to `artifacts/test-station/`. Use `make test-python` for a direct pytest run without the reporting wrapper.

CI publishes the generated report to Test Station when `TEST_STATION_INGEST_SHARED_KEY` is configured as a GitHub Actions secret. The ingest endpoint defaults to `https://test-station.smysnk.com/api/ingest` and can be overridden with the `TEST_STATION_INGEST_ENDPOINT` repository variable.

## Deployment

`make install` # Install local Python deployment dependencies (`rshell` and `esptool`)

`make erase` # Erase ESP32

`make image` # Install MicroPython on ESP32

`make rsync` # Install `updater` on ESP32

`make repl` # Opens a repl terminal to the ESP32

Power cycle (Ctrl-D) the ESP32, you should see the updater pull down HEAD of the configured branch on boot.

The default firmware target is the generic ESP32 stable build `ESP32_GENERIC-20260406-v1.28.0.bin`. Override the Makefile variables for other boards or release lines:

```sh
make image ESP_BOARD=ESP32_GENERIC_SPIRAM
make image ESP_IMAGE=custom-firmware.bin ESP_IMAGE_URL=https://example.com/custom-firmware.bin
```

If your serial port is not `/dev/ttyUSB0`, set `RSHELL_PORT`:

```sh
make image RSHELL_PORT=/dev/cu.usbserial-0001
```

## Internals

Execution of `src/main.py` calls `updater.update()` checking `.version` file with the SHA of the latest commit.  If they are different it will create a new directory and pull down the `src` sub-directory.  Once complete, the old `src` directory is deleted and the new copy is moved in its place.  After that it will execute `src.main` with the following kargs:
```
import src.main
src.main.start(env=env, requests=lib.requests, logger=logger, time=t, updater=updater)
```

## Secrets

Use `src/env.py` to store secrets that will be passed to `main.start()` so they do not need be stored in the main repository.  This file is not updated via OTA and needs to be replaced manually by flashing.

## Interval Updating

You may want to check for updates a regularly scheduled intervals eg. every hour. Here is an [example implementation](https://github.com/smysnk/my-grow/blob/master/src/sensorloop.py#L216):
```
# Reset the device if an update is available
if state['runtime'][runtime.OTA_AUTO_UPDATE_INTERVAL] and time.time() % state['runtime'][runtime.OTA_AUTO_UPDATE_INTERVAL] == 0:
  try:
    gc.collect()
    updater.checkForUpdate()
  except Exception as e:
    log('Failed to check for OTA update:', e)
```
