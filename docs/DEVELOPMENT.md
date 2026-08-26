# Development

Set up a local development environment from the repository root:

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

Return to the [project README](../README.md).
