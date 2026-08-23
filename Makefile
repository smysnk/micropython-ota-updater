PYTHON ?= python3
ESP_BOARD ?= ESP32_GENERIC
MICROPYTHON_VERSION ?= v1.28.0
MICROPYTHON_RELEASE_DATE ?= 20260406
ESP_IMAGE ?= $(ESP_BOARD)-$(MICROPYTHON_RELEASE_DATE)-$(MICROPYTHON_VERSION).bin
FIRMWARE_MANIFEST ?= firmware/manifest.json
ESPTOOL ?= $(PYTHON) -m esptool
MPREMOTE ?= $(PYTHON) -m mpremote
MPREMOTE_PORT ?= auto
ENV_FILE ?= src/env.py
export RSHELL_PORT ?= /dev/ttyUSB0

firmware:
	$(PYTHON) scripts/firmware.py download --manifest "$(FIRMWARE_MANIFEST)" --board "$(ESP_BOARD)" --output "$(ESP_IMAGE)"

verify-firmware:
	$(PYTHON) scripts/firmware.py verify --manifest "$(FIRMWARE_MANIFEST)" --board "$(ESP_BOARD)" --input "$(ESP_IMAGE)"

erase:
	$(ESPTOOL) --chip esp32 --port "$(RSHELL_PORT)" erase_flash

flash: firmware
	$(ESPTOOL) --chip esp32 --port "$(RSHELL_PORT)" --baud 460800 write_flash 0x1000 "$(ESP_IMAGE)"

image: flash

deploy:
	$(MPREMOTE) connect "$(MPREMOTE_PORT)" fs cp src/boot.py :boot.py + fs cp src/main.py :main.py + fs cp "$(ENV_FILE)" :env.py + fs cp -r src/lib : + soft-reset

rsync: deploy

repl:
	$(MPREMOTE) connect "$(MPREMOTE_PORT)" repl

smoke-test:
	$(PYTHON) scripts/hardware_smoke.py --port "$(MPREMOTE_PORT)"

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
	PYTHONPATH=src $(PYTHON) scripts/check_certificates.py

test-ci:
	npm run test:ci
	$(PYTHON) scripts/check_micropython_compat.py

test-dev:
	ptw --poll

.PHONY: firmware verify-firmware erase flash image deploy rsync repl smoke-test clean install install-python-dev install-dev test test-python test-mpy test-live-tls test-ci test-dev
