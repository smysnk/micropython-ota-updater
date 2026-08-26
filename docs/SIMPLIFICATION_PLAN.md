# Repository simplification plan

Status: implemented locally; downstream application and ESP32 gates pending

## Implementation outcome

Repository phases 0-5 were implemented on 2026-08-25 as the version 3
boundary. The compatibility audit identified `smysnk/my-grow` as a remote-only
consumer of the removed five-argument application entrypoint; its required
migration is recorded in `docs/UPGRADING.md` and cannot be applied from this
workspace.

Local evidence after implementation:

- `36` CPython tests pass, including repository-contract, manifest-command,
  verified-HTTPS, interruption, confirmation, recovery, and rollback cases.
- `9` modules compile in this working copy with `mpy-cross` (including the
  ignored local environment); the deployable bootstrap fell from 9 modules and
  14,097 compiled bytes to 6 modules and 11,209 compiled bytes.
- Editable installation reports package version `3.0.0`.
- Live verified TLS succeeds for the GitHub API and raw-content hosts.
- The manifest-selected firmware downloads and verifies against its pinned
  SHA-256 checksum.
- Test Station reports all 36 tests passing, and every SVG validates as XML and
  renders successfully.

No physical ESP32 serial device was attached. Erase, flash, deploy, reboot,
interruption, confirmation, and on-device rollback remain release gates; no
destructive hardware command was attempted against an unverified target.

This plan reduces the updater's compatibility, configuration, deployment, and
application-integration surface without weakening verified TLS, firmware
checksums, staged installation, confirmation, or rollback.

The work is intended as a version 3 change. It should use one documented
breaking boundary rather than retaining parallel version 2 and version 3
runtime paths.

## Baseline

Baseline recorded on 2026-08-25:

- `24` CPython tests pass.
- `12` device modules compile with the pinned `mpy-cross`.
- The supported production target is `ESP32_GENERIC` on MicroPython `v1.28.0`.
- The device bootstrap is deployed from repository `src/` into the device
  root, while the separate device `/src/` application directory is replaced by
  OTA updates.
- Live TLS and physical ESP32 behavior remain separate release gates.

Baseline commands:

```sh
.venv/bin/python -m pytest
.venv/bin/python scripts/check_micropython_compat.py
```

## Goals

- Remove unused compatibility modules, names, and command aliases.
- Maintain one device-configuration schema and one local-credential path.
- Make the firmware manifest the only source of board and artifact metadata.
- Distinguish repository bootstrap source from the OTA-managed device `/src/`
  directory.
- Reduce the application entrypoint to the settings and updater contracts it
  actually needs.
- Narrow the embedded HTTP and logging implementations to updater requirements.
- Preserve failure-safe update behavior and security checks.

## Non-goals

- Removing `src.next`, `src.previous`, `.ota-pending`, confirmation, or
  rollback.
- Disabling certificate or hostname verification.
- Removing firmware checksum verification.
- Adding new repository providers, release policies, CircuitPython support, or
  other speculative abstractions.
- Changing the separate Test Station integration; that is outside the scope of
  items 2-6 and can be evaluated independently.

## Phase 0: Freeze the compatibility boundary

Goal: identify every consumer before removing version 2 interfaces.

Implementation:

1. Search known application repositories, deployment scripts, and operator
   documentation for:
   - `githubUsername`
   - `IO.readFile()` and `IO.writeFile()`
   - `start(env, requests, logger, time, updater)`
   - `make image` and `make rsync`
   - imports from `lib.base64`, `lib.logger`, or `lib.timew`
2. Record each downstream repository and its required migration.
3. Declare the simplified interface as version 3.
4. Add migration notes to `docs/UPGRADING.md` before removing interfaces.
5. Do not introduce signature detection, permanent aliases, or dual runtime
   implementations.

Validation:

```sh
rg -n "githubUsername|readFile|writeFile|start\(|make image|make rsync|lib\.(base64|logger|timew)" .
```

Acceptance evidence:

- Known consumers are listed in the migration notes.
- Every removed interface has a replacement.
- The existing test and compiler baseline is recorded before implementation.

## Phase 1: Remove dead compatibility surface

Goal: remove code that has no current OTA responsibility.

Implementation:

1. Delete `src/lib/base64.py`; it has no current callers.
2. Remove `githubUsername` from:
   - `src/env.py`
   - `src/env.example.py`
   - `scripts/configure_env.py`
   - `src/main.py`
   - `GitHub.__init__()` in `src/lib/update.py`
3. Remove the unused `IO.readFile` and `IO.writeFile` aliases.
4. Delete `setup.py` and `MANIFEST.in` if the repository is confirmed not to
   publish source distributions. Keep `pyproject.toml` as the host dependency
   and test configuration.
5. Remove the `image` and `rsync` Makefile aliases after the downstream audit.
6. Update README and upgrade documentation references.

Validation:

```sh
.venv/bin/python -m pytest
.venv/bin/python scripts/check_micropython_compat.py
rg -n "githubUsername|readFile|writeFile|lib\.base64|make image|make rsync" .
git diff --check
```

Acceptance evidence:

- No removed name remains in tracked source or documentation.
- Editable installation through `pyproject.toml` succeeds.
- All host tests pass.
- Every remaining device module compiles with `mpy-cross`.

## Phase 2: Rename bootstrap source and consolidate configuration

Goal: separate repository bootstrap source from the device's OTA-managed
application directory, and maintain one configuration template.

Target repository layout:

```text
device/
  boot.py
  main.py
  env.example.py
  lib/
    certificates.py
    requests.py
    update.py
    ...
```

The device paths remain:

```text
/boot.py
/main.py
/env.py
/lib/
/src/             # OTA-managed application
/src.next/        # staged application
/src.previous/    # rollback application
/.ota-pending
```

Implementation:

1. Rename repository `src/` to `device/`.
2. Delete the tracked `device/env.py`.
3. Keep only `device/env.example.py` as the schema and example.
4. Ignore `device/env.local.py` and use it as the default local deployment
   configuration.
5. Make `scripts/configure_env.py` write CI configuration to an ignored path,
   such as `build/device-env.py`.
6. Update bootstrap-source references in:
   - `Makefile`
   - `pyproject.toml`
   - `scripts/check_micropython_compat.py`
   - `.github/workflows/ci.yml`
   - `.github/workflows/hardware-smoke.yml`
   - README and upgrade documentation
7. Keep on-device application references such as `mainDir='src'`, `src.next`,
   `src.previous`, and `src/.version` unchanged.
8. Review every remaining `src` reference and classify it explicitly as either
   a repository source path that must change or an on-device application path
   that must remain.

Target deployment variables:

```make
DEVICE_SOURCE ?= device
ENV_FILE ?= device/env.local.py
SERIAL_PORT ?= auto
```

Validation:

```sh
.venv/bin/python -m pytest
.venv/bin/python scripts/check_micropython_compat.py
rg -n "\bsrc/|PYTHONPATH=src|MICROPYPATH: src|ENV_FILE" . .github
make test-live-tls
```

Hardware validation:

1. Deploy `device/boot.py`, `device/main.py`, the selected environment file,
   and `device/lib/`.
2. Inspect the device filesystem.
3. Confirm that the root bootstrap and the separate `/src/` application both
   exist.
4. Reboot and confirm the application starts.

Acceptance evidence:

- Repository bootstrap code lives only under `device/`.
- `/src/` unambiguously means the on-device OTA application in runtime code.
- Only one tracked environment schema exists.
- Local credentials are ignored and hardware-CI credentials are generated in
  an ignored path.
- Deployment and reboot succeed on an ESP32.

## Phase 3: Make the firmware manifest authoritative

Goal: eliminate duplicated board and firmware settings.

Extend each board entry in `manifest.json` to include every value
needed for downloading and flashing:

```json
{
  "chip": "esp32",
  "version": "v1.28.0",
  "release_date": "20260406",
  "filename": "ESP32_GENERIC-20260406-v1.28.0.bin",
  "url": "https://micropython.org/resources/firmware/ESP32_GENERIC-20260406-v1.28.0.bin",
  "sha256": "...",
  "flash_address": "0x1000",
  "baud": 460800,
  "status": "production"
}
```

Implementation:

1. Add `erase` and `flash` subcommands to `scripts/firmware.py`.
2. Have the script invoke `esptool` using manifest values.
3. Keep download-to-temporary-file, checksum verification, and atomic rename.
4. Ensure `flash` verifies the artifact before invoking `esptool`.
5. Remove firmware version, release date, derived filename, flash address,
   chip, and baud from the Makefile.
6. Replace `RSHELL_PORT` and `MPREMOTE_PORT` with one `SERIAL_PORT` variable.
7. Keep the Makefile as a thin interface to `scripts/firmware.py` and
   `mpremote`.
8. Add tests for manifest resolution and the generated `esptool` argument list.

Validation:

```sh
.venv/bin/python -m pytest
make firmware
make verify-firmware
git diff --check
```

Hardware validation:

1. Inspect the fully resolved erase and flash commands.
2. Erase the explicitly selected ESP32.
3. Flash the manifest-selected artifact.
4. Confirm MicroPython boots and reports the expected version.

Acceptance evidence:

- Board and artifact metadata are defined only in the manifest.
- No board-specific flash setting is hard-coded in the Makefile.
- A checksum mismatch prevents flashing.
- The selected ESP32 boots the manifest version after flashing.

## Phase 4: Simplify the application contract

Goal: expose only the configuration and update health boundary to the
application.

Replace:

```python
application_main.start(
  env=env,
  requests=lib.requests,
  logger=logger,
  time=t,
  updater=updater,
)
```

with:

```python
application_main.start(settings=env.settings, updater=updater)
```

The application imports its own standard time, networking, and logging modules.
It must still call `updater.confirm()` only after critical startup succeeds.

Implementation:

1. Update the bootstrap call in `device/main.py`.
2. Update the documented application example.
3. Update test and hardware fixture applications.
4. Migrate every known downstream application.
5. Preserve explicit application confirmation; do not infer health from
   `start()` returning.
6. Preserve rollback when import or startup raises before confirmation.

Validation scenarios:

- Application import failure restores `src.previous`.
- Application startup failure restores `src.previous`.
- Reset before `confirm()` restores `src.previous` on the next boot.
- Successful `confirm()` removes `.ota-pending` and `src.previous`.
- A confirmed application remains installed after reboot.

Acceptance evidence:

- The application entrypoint accepts only `settings` and `updater`.
- No application depends on updater-provided HTTP, logging, or time wrappers.
- Confirmation and rollback behavior is unchanged.

## Phase 5: Narrow embedded HTTP and logging

Goal: retain only the runtime services required by the OTA bootstrap.

HTTP behavior to retain:

- `GET`
- JSON response decoding
- binary file streaming
- verified certificate chains and hostnames
- connection timeouts
- bounded redirects
- response and socket closure on success and failure

HTTP behavior to remove after the application-contract migration:

- `HEAD`, `POST`, `PUT`, `PATCH`, and `DELETE` wrappers
- request JSON/body generation
- unused generic request parameters
- application-facing exposure of `lib.requests`

Logging and time implementation:

1. Replace the regex-filtered logger hierarchy with a small debug callable or
   direct bootstrap logging.
2. Change `IO`, `GitHub`, `OTAUpdater`, and the HTTP client to accept a simple
   `log(message)` callable or a no-op.
3. Use MicroPython's `time` module directly.
4. Delete `device/lib/logger.py`, `device/lib/timew.py`, and
   `test/test_logger.py` when their consumers have been migrated.
5. Keep dependency injection for filesystem, GitHub, machine, and HTTP seams;
   these make failure injection possible without adding production behavior.

Validation:

```sh
.venv/bin/python -m pytest
.venv/bin/python scripts/check_micropython_compat.py
make test-live-tls
```

Required HTTP cases:

- verified TLS succeeds for both GitHub hosts
- invalid trust roots fail closed
- redirects are bounded
- binary data is written byte-for-byte
- malformed status lines close sockets
- chunked responses remain explicitly rejected
- GitHub API errors close responses and preserve useful status details

Acceptance evidence:

- The device HTTP surface is GET-only.
- The application receives no updater-owned HTTP, logger, or time service.
- Removed modules have no callers.
- TLS, streaming, redirect, and cleanup tests remain green.
- The compiled device payload is smaller than the phase 0 baseline.

## Final integration gate

Run the complete local sequence:

```sh
make test-python
make test-mpy
make test-live-tls
make firmware
make verify-firmware
git diff --check
```

Then validate on an ESP32:

1. Back up the device filesystem.
2. Erase and flash the manifest-selected firmware.
3. Deploy the root bootstrap and local configuration.
4. Verify a no-update boot.
5. Install a new `/src/` tree and confirm it.
6. Reboot and verify the confirmed SHA remains active.
7. Install an application that fails before confirmation.
8. Verify rollback to `src.previous`.
9. Interrupt an update while `src.next` is being written.
10. Verify the current application remains bootable.

## Definition of done

- The version 3 migration is documented for every known consumer.
- Unused compatibility modules, aliases, and settings are removed.
- Repository device source lives under `device/`.
- Device `/src/` exclusively denotes the OTA-managed application.
- Exactly one tracked environment schema exists.
- Firmware and flashing metadata have one authoritative manifest.
- The application contract accepts only `settings` and `updater`.
- The embedded HTTP client is GET-only.
- Transactional staging, confirmation, rollback, verified TLS, and firmware
  checksum behavior remain intact.
- Host tests, stable MicroPython compilation, live TLS, and physical-device
  evidence all pass.
