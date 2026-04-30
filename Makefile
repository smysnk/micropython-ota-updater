PYTHON ?= python3
ROOT ?=
USER ?=
REMOTE_PATH ?= /home/$(USER)/$(ROOT)
IP ?=
PATH_TEST ?= test
ESP_BOARD ?= ESP32_GENERIC
MICROPYTHON_VERSION ?= v1.28.0
MICROPYTHON_RELEASE_DATE ?= 20260406
ESP_IMAGE ?= $(ESP_BOARD)-$(MICROPYTHON_RELEASE_DATE)-$(MICROPYTHON_VERSION).bin
ESP_IMAGE_URL ?= https://micropython.org/resources/firmware/$(ESP_IMAGE)
ESPTOOL ?= $(PYTHON) -m esptool
DOWNLOAD ?= curl -fL -o
export RSHELL_PORT ?= /dev/ttyUSB0

erase:
	$(ESPTOOL) --chip esp32 --port $(RSHELL_PORT) erase_flash

image:
	test -f "$(ESP_IMAGE)" || $(DOWNLOAD) "$(ESP_IMAGE)" "$(ESP_IMAGE_URL)"
	$(ESPTOOL) --chip esp32 --port $(RSHELL_PORT) --baud 460800 write_flash -z 0x1000 "$(ESP_IMAGE)"

rsync: clean
	rshell rsync src /pyboard

repl:
	rshell repl

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

test-ci:
	npm run test:ci

test-dev:
	ptw --poll

.PHONY: erase image rsync repl clean install install-python-dev install-dev test test-python test-ci test-dev
