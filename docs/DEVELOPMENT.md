# Development

Set up a local development environment from the repository root:

```sh
python3 -m venv .venv
. .venv/bin/activate
make install-dev
make test
```

`make test` runs the host-side unit and failure-injection tests, then compiles
every device module with the MicroPython 1.28 `mpy-cross` compiler. The focused
targets remain available as `make test-python` and `make test-mpy`.

The network-dependent certificate-chain check is separate:

```sh
make test-live-tls
```

Return to the [project README](../README.md).
