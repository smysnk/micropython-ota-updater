# Fork integration plan

Status: superseded for version 3 by `docs/SIMPLIFICATION_PLAN.md`

The provider, platform, policy, and hook abstractions below are retained as
research only. They are not part of the version 3 simplification boundary.

This plan turns the useful ideas found in the wider
`rdehuyss/micropython-ota-updater` fork network into changes that can be made
without weakening this repository's MicroPython 1.28 compatibility, verified
TLS, staged installation, or rollback guarantees.

The primary sources reviewed for this plan are:

- [smysnk fork network](https://github.com/smysnk/micropython-ota-updater/network/members)
- [te0006 Gogs fork](https://github.com/te0006/micropython-ota-updater-gogs)
- [te0006 MQTT retain commit](https://github.com/te0006/micropython-ota-updater-gogs/commit/b08310ccfe1ccf950dbdfaace4e0e82faf10511b)
- [msiotprojects CircuitPython fork](https://github.com/msiotprojects/circuitpython-ota-updater)
- [msiotprojects default-branch commit](https://github.com/msiotprojects/circuitpython-ota-updater/commit/7e1579ed6fa95219e6341437edbd3006188dfe36)
- [aruder77 release-channel work](https://github.com/aruder77/micropython-ota-updater/commits/master/)
- [graham768 packaging work](https://github.com/graham768/micropython-ota-updater/commit/1babb98fcc9fc0aa4dac493d4d360c29ce4ef257)

## Findings to carry forward

The Gogs fork contains the most useful provider work: it follows a configurable
branch on a self-hosted Gogs server, downloads content returned inline as
base64, handles custom server ports, separates local configuration from the OTA
application tree, reports OTA state over MQTT, and uses a watchdog to recover
from application failure.

The CircuitPython fork contains a substantial platform port: it uses
`adafruit_requests`, `wifi.radio`, `settings.toml`, `code.py`,
`microcontroller.reset()`, binary downloads, and boot-time ownership of the
`CIRCUITPY` filesystem.

The smaller forks contribute two concepts worth retaining: explicit
stable/preview update channels and automated package publication. Their actual
implementations should not be copied because they use brittle tag conventions
or obsolete release actions.

Neither highlighted commit should be cherry-picked. The Gogs commit only adds
an MQTT `retain` argument, which belongs in application integration code. The
CircuitPython commit stores a branch setting that its own comments say is not
used. This repository already uses `githubRemoteBranch` when constructing its
GitHub provider.

## Current baseline

All phases must preserve these properties:

- MicroPython `v1.28.0` on `ESP32_GENERIC` remains the production target.
- GitHub API and raw-content requests verify certificate chains and hostnames.
- File bodies are streamed in bounded chunks and written in binary mode.
- A failed download leaves the active application untouched.
- A swapped update remains unconfirmed until the application calls
  `updater.confirm()`.
- An interrupted or unconfirmed update restores `src.previous` on the next
  boot.
- Existing configuration names and the public `GitHub`, `IO`, and `OTAUpdater`
  imports remain compatible for one major release.
- Host tests, MicroPython compilation, the Unix-port smoke test, and hardware
  validation remain distinct gates.

## Target architecture

The OTA lifecycle remains in `device/lib/update.py`. Repository access and
platform-specific behavior move behind narrow, duck-typed interfaces; no
`abc`, dataclasses, or other CPython-only machinery is introduced.

### Repository provider

Add `device/lib/remote.py` for shared provider utilities and normalized entry
types. Add `device/lib/github.py` and, later, `device/lib/gogs.py` for provider
implementations. A provider exposes:

```python
revision(policy) -> opaque revision string
list_entries(revision, remote_path) -> iterable of normalized entries
download_file(revision, entry, destination_path) -> None
```

The updater owns recursive traversal, filesystem writes, version-marker
creation, staging, swaps, confirmation, and rollback. Providers own API URLs,
authentication, response parsing, and retrieval of file bytes. This prevents a
provider from bypassing the transactional update lifecycle.

`device/lib/update.py` temporarily re-exports `GitHub` so existing application
imports continue to work.

### Update policy

Policy resolution is independent of file transport. The initial modes are:

- `branch`: follow a branch head; this is the compatible default.
- `release`: follow GitHub's latest stable release.
- `prerelease`: follow the latest prerelease explicitly opted into.
- `tag`: remain pinned to one exact tag.

All modes resolve to an opaque commit identifier and compare identifiers for
equality. The updater must not order version strings lexicographically or infer
stability from tag prefixes.

### Platform services

MicroPython remains the default runtime. A future CircuitPython port supplies
network, reset, directory-enumeration, and writable-storage services without
introducing CircuitPython imports into the MicroPython modules.

### Application health integration

`updater.confirm()` remains the authoritative success boundary. Optional event
and watchdog hooks may report progress or feed a watchdog, but MQTT, broker
availability, LED pins, and reset policy remain application concerns.

## Phase 1: Characterize and freeze the provider contract

Goal: establish tests for current behavior before moving GitHub code.

Implementation:

1. Add provider-contract fixtures for revision lookup, directory listing,
   nested directories, binary files, empty directories, and response closure.
2. Add failure injection for revision lookup, listing, file download, malformed
   JSON, authentication failure, rate limiting, and mid-stream disconnects.
3. Record the expected request headers, branch selection, URL encoding, and
   bounded-memory behavior of the current GitHub implementation.
4. Add a regression test proving that credentials and query parameters are
   redacted from logger output.
5. Document the compatibility surface for current constructors and imports.

Validation:

```sh
make test-python
make test-mpy
make test
```

Acceptance evidence:

- Existing tests still pass.
- New provider-contract tests fail against deliberately malformed fixtures.
- The Test Station report includes the new provider and redaction cases.
- No device source or configuration behavior changes in this phase.

## Phase 2: Extract and harden the GitHub provider

Goal: make GitHub use the provider contract without changing update behavior.

Implementation:

1. Move GitHub URL construction, headers, revision lookup, directory parsing,
   and file download into `device/lib/github.py`.
2. Move URL/path normalization and sensitive-value redaction into
   `device/lib/remote.py`.
3. Make `OTAUpdater` perform recursive traversal through normalized entries.
4. Preserve `GitHub` as a compatibility import from `device/lib/update.py`.
5. Include a non-default port in the HTTP `Host` header while retaining the
   current default-port behavior.
6. Percent-encode repository paths and refs rather than interpolating them
   directly into URLs.
7. Keep Bearer authentication, API version headers, verified TLS, timeouts,
   redirect bounds, response closure, and binary streaming mandatory.

Validation:

```sh
make test-python
make test-mpy
make test-live-tls
make test
```

Acceptance evidence:

- The current GitHub fixture repository installs and confirms on an ESP32.
- Public and private repository tests use the same provider implementation.
- Nested and binary files are byte-identical after installation.
- Existing callers can still import `GitHub` from `lib.update`.
- No access token appears in logs or generated artifacts.

## Phase 3: Add a secure Gogs provider

Goal: support self-hosted Gogs without copying the fork's security and
transactional weaknesses.

Implementation:

1. Add `device/lib/gogs.py` using the provider contract.
2. Parse the documented commit JSON response and extract one immutable commit
   SHA; never treat the complete response body as the version.
3. Support Gogs content responses that contain base64 inline while writing
   decoded data in binary mode and bounded chunks where the runtime permits.
4. Send credentials in an authentication header. Never place a token in a URL,
   exception, or log message.
5. Support HTTPS servers on non-default ports and require hostname and chain
   verification. A private CA must be supplied explicitly for a private Gogs
   deployment.
6. Reject plain HTTP by default. Any development-only override must be explicit
   in configuration, visibly warned about, and excluded from production
   examples.
7. Keep all downloads inside `src.next`; only `OTAUpdater` may perform the
   transactional swap.
8. Document Gogs first. Treat Gitea as a separate compatibility claim that
   requires its own fixtures and live validation.

Validation:

- Run provider-contract tests against recorded Gogs API fixtures.
- Run an integration test against a disposable Gogs instance containing text,
  binary, nested, empty, renamed, and deleted files.
- Exercise invalid token, missing branch, bad base64, rate limiting, TLS
  failure, private CA, non-default port, and interrupted download paths.
- Run `make test-python`, `make test-mpy`, and `make test`.
- Run an ESP32 update against a reachable TLS-enabled Gogs test repository.

Acceptance evidence:

- GitHub and Gogs install the same fixture tree and produce identical hashes.
- Packet/log inspection shows no token in request URLs or output.
- A failed Gogs download leaves the prior application bootable.
- An unconfirmed Gogs update rolls back on reset.
- The supported Gogs version and TLS setup are recorded in the hardware report.

## Phase 4: Add explicit update policies

Goal: support stable, preview, and pinned deployments without relying on
lexicographic version comparisons or naming conventions.

Implementation:

1. Add an `updateMode` setting with `branch` as the compatible default.
2. Keep `githubRemoteBranch` for branch mode; add explicit release,
   prerelease, and pinned-tag settings only as their implementations land.
3. Resolve a selected release or tag to an immutable commit identifier before
   listing content.
4. Store the resolved identifier in `.version`. If source metadata is useful,
   store it separately so legacy `.version` readers continue to work.
5. Define deterministic behavior for no releases, deleted tags, moved branch
   heads, force pushes, and switching modes.
6. Document branch mode as continuous delivery, release mode as stable
   delivery, prerelease mode as opt-in preview, and tag mode as a deployment
   pin.

Validation:

- Test stable releases mixed with drafts and prereleases.
- Test tags whose names do not resemble semantic versions.
- Test switching from branch to release mode and back without reinstall loops.
- Test a force-pushed branch and a deleted pinned tag.
- Repeat rollback and interruption tests for every mode.

Acceptance evidence:

- Selection depends on provider metadata, never string ordering.
- Draft releases are never installed.
- Prereleases are installed only after explicit opt-in.
- A pinned tag does not move silently.
- Documentation contains complete configuration examples for every mode.

## Phase 5: Add optional health and watchdog hooks

Goal: retain the operational value of the Gogs fork's watchdog and status
reporting without coupling OTA correctness to MQTT.

Implementation:

1. Add an optional event callback receiving bounded event names and safe
   metadata for check, download, staged, swapped, confirmed, rollback, and
   failure states.
2. Add an optional watchdog/feed callback invoked only at documented safe
   points during potentially long operations.
3. Keep confirmation application-controlled. A connectivity check, MQTT
   publish, or watchdog feed must never implicitly confirm a release.
4. Provide an application-level MQTT example outside the updater library,
   including retained status if desired.
5. Define callback exception behavior: log safely, preserve OTA state, and do
   not turn telemetry failure into a destructive swap.
6. Add reboot-loop protection guidance and recommend a bounded retry/backoff
   policy in the application.

Validation:

- Inject callback failures at every event.
- Simulate watchdog resets during download, both renames, application import,
  and pre-confirmation startup.
- Simulate an unavailable MQTT broker and verify that update and rollback
  correctness do not depend on it.
- Run the complete failure-injection suite and ESP32 hardware smoke test.

Acceptance evidence:

- Telemetry loss cannot delete or confirm an application.
- Reset before confirmation restores the previous application.
- Event metadata contains no token, Wi-Fi secret, or response body.
- The example application can publish retained OTA state without imports in
  the updater library.

## Phase 6: Build a gated CircuitPython port

Goal: share repository and update-state logic while respecting CircuitPython's
different networking, startup, reset, and USB-filesystem rules.

This phase begins only after Phases 1 and 2 prove that the shared provider
contract does not depend on MicroPython-specific modules.

Implementation:

1. Put CircuitPython entry points and adapters in a separate `ports/circuitpython`
   tree or separately published package. Do not mix `wifi`, `storage`,
   `microcontroller`, or Adafruit imports into the MicroPython source path.
2. Use `adafruit_connection_manager` and `adafruit_requests` behind the same
   provider behavior and error contract.
3. Read configuration from `settings.toml`, using correctly named variables and
   a GitHub `Authorization` header. Commit only a credential-free example.
4. Add a writable-storage preflight. Make any development-button pin a
   board-profile setting rather than hard-coding `board.D2`.
5. Use `code.py` and `microcontroller.reset()` in the CircuitPython entry point.
6. Implement directory detection using CircuitPython-supported APIs and test
   the copy fallback independently of `rename()`.
7. Reproduce pending, previous, confirmation, and rollback semantics before
   claiming parity with the MicroPython port.
8. Publish a CircuitPython-specific README and support matrix; do not reuse
   MicroPython instructions unchanged.

Validation:

- Run host tests with strict CircuitPython service fakes.
- Compile/import the port with the supported CircuitPython bundle and library
  versions.
- Test host-writable and device-writable filesystem modes.
- Test missing board pin, read-only storage, full storage, binary files,
  interrupted swap, reset before confirmation, and private authentication.
- Run the full update lifecycle on at least one named CircuitPython board.

Acceptance evidence:

- The exact board, CircuitPython version, Adafruit library bundle, and storage
  policy are recorded.
- A real board installs, starts, confirms, and retains the update after reboot.
- A second real-board run resets before confirmation and restores the previous
  application.
- No credential-shaped values are committed.
- The MicroPython test, compile, TLS, and hardware gates remain unchanged and
  passing.

## Explicit non-goals

- Do not embed MQTT or a particular broker into the updater library.
- Do not use broker unavailability as an unconditional remote-reset mechanism.
- Do not send credentials in query strings or disable TLS verification by
  default.
- Do not restore delete-then-move installation without a previous-version
  rollback directory.
- Do not infer update order from tag text.
- Do not claim Gitea compatibility from Gogs fixtures alone.
- Do not claim generic CircuitPython support from one hard-coded board.
- Do not add native firmware OTA; this plan updates application files only.
- Do not restore the historical PyPI workflow. Any publication work requires a
  separate design using current trusted publishing and MicroPython package
  distribution conventions.

## Completion gate

The plan is complete only when the implemented phases have repository tests,
MicroPython compiler proof, Test Station artifacts, live provider/TLS evidence,
and named-device evidence appropriate to their scope. A local test pass or a
successful commit is not hardware or deployment proof. Any phase lacking its
live or physical evidence remains explicitly provisional in the support
matrix.
