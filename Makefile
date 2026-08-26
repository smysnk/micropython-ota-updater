PYTHON ?= python3
ESP_BOARD ?= ESP32_GENERIC
FIRMWARE_MANIFEST ?= manifest.json
MPREMOTE ?= $(PYTHON) -m mpremote
DEVICE_SOURCE ?= device
ENV_FILE ?= device/env.local.py
SERIAL_PORT ?= auto

help:
	@printf '%s\n' \
		'Usage: make <target> [SERIAL_PORT=<port>]' \
		'' \
		'Device connection:' \
		'  SERIAL_PORT=auto       Automatically select the connected device (default)' \
		'  SERIAL_PORT=<port>     Use a specific port, for example /dev/cu.usbserial-0001' \
		'' \
		'Common targets:' \
		'  erase                  Erase firmware and all files from the device' \
		'  flash                  Download, verify, and flash the pinned firmware' \
		'  deploy                 Copy the updater and configuration to the device' \
		'  repl                   Open the MicroPython REPL' \
		'  smoke-test             Run the hardware smoke test'

firmware:
	$(PYTHON) scripts/firmware.py download --manifest "$(FIRMWARE_MANIFEST)" --board "$(ESP_BOARD)"

verify-firmware:
	$(PYTHON) scripts/firmware.py verify --manifest "$(FIRMWARE_MANIFEST)" --board "$(ESP_BOARD)"

erase:
	$(PYTHON) scripts/firmware.py erase --manifest "$(FIRMWARE_MANIFEST)" --board "$(ESP_BOARD)" --port "$(SERIAL_PORT)"

flash:
	$(PYTHON) scripts/firmware.py flash --manifest "$(FIRMWARE_MANIFEST)" --board "$(ESP_BOARD)" --port "$(SERIAL_PORT)"

deploy:
	$(MPREMOTE) connect "$(SERIAL_PORT)" fs cp "$(DEVICE_SOURCE)/boot.py" :boot.py + fs cp "$(DEVICE_SOURCE)/main.py" :main.py + fs cp "$(ENV_FILE)" :env.py + fs cp -r "$(DEVICE_SOURCE)/lib" : + soft-reset

repl:
	$(MPREMOTE) connect "$(SERIAL_PORT)" repl

smoke-test:
	$(PYTHON) scripts/hardware_smoke.py --port "$(SERIAL_PORT)"

clean:
	find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name "*.egg-info" -o -name build -o -name dist \) -prune -exec rm -rf {} +

install:
	$(PYTHON) -m pip install -e .

install-python-dev:
	$(PYTHON) -m pip install -e ".[dev]"

install-dev: install-python-dev

test: test-python test-mpy

test-python:
	$(PYTHON) -m pytest

test-mpy:
	$(PYTHON) scripts/check_micropython_compat.py

test-live-tls:
	PYTHONPATH=device $(PYTHON) scripts/check_certificates.py

test-ci: test

test-dev:
	ptw --poll

.PHONY: help firmware verify-firmware erase flash deploy repl smoke-test clean install install-python-dev install-dev test test-python test-mpy test-live-tls test-ci test-dev
