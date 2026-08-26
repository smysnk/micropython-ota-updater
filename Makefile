PYTHON ?= python3
ESP_BOARD ?= ESP32_GENERIC
FIRMWARE_MANIFEST ?= firmware/manifest.json
MPREMOTE ?= $(PYTHON) -m mpremote
DEVICE_SOURCE ?= device
ENV_FILE ?= device/env.local.py
SERIAL_PORT ?= auto

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
	npm install

test:
	npm run test:station

test-python:
	$(PYTHON) -m pytest

test-mpy:
	$(PYTHON) scripts/check_micropython_compat.py

test-live-tls:
	PYTHONPATH=device $(PYTHON) scripts/check_certificates.py

test-ci:
	npm run test:ci
	$(PYTHON) scripts/check_micropython_compat.py

test-dev:
	ptw --poll

.PHONY: firmware verify-firmware erase flash deploy repl smoke-test clean install install-python-dev install-dev test test-python test-mpy test-live-tls test-ci test-dev
