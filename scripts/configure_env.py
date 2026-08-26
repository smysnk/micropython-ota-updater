#!/usr/bin/env python3
"""Create device configuration from hardware-runner environment variables."""

import argparse
import os
from pathlib import Path


def required(name):
  value = os.environ.get(name)
  if not value:
    raise SystemExit('%s must be set' % name)
  return value


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('--output', default='build/device-env.py')
  args = parser.parse_args()
  settings = {
    'wifiAP': required('OTA_WIFI_AP'),
    'wifiPassword': required('OTA_WIFI_PASSWORD'),
    'controllerName': os.environ.get('OTA_CONTROLLER_NAME', 'ota-smoke-test'),
    'wifiConnectTimeout': 30,
    'debug': True,
    'httpTimeout': 15,
    'githubRemote': required('OTA_GITHUB_REMOTE'),
    'githubUpdateMode': os.environ.get('OTA_GITHUB_UPDATE_MODE') or 'branch',
    'githubRemoteBranch': os.environ.get('OTA_GITHUB_BRANCH') or 'main',
    'githubToken': os.environ.get('OTA_GITHUB_TOKEN', ''),
    'otaMinimumFreeBytes': 65536,
  }
  output = Path(args.output)
  output.parent.mkdir(parents=True, exist_ok=True)
  output.write_text('settings = %r\n' % settings, encoding='utf-8')


if __name__ == '__main__':
  main()
