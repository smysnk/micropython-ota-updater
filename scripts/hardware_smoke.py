#!/usr/bin/env python3
"""Run a bounded compatibility smoke test on a connected MicroPython board."""

import argparse
import subprocess


def run(command):
  print('+', ' '.join(command))
  subprocess.run(command, check=True)


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('--port', default='auto')
  args = parser.parse_args()
  prefix = ['mpremote', 'connect', args.port]
  run(prefix + ['run', 'scripts/device_smoke.py'])
  run(prefix + ['reset', 'sleep', '2', 'exec', "import sys; print('MICROPYTHON_REBOOT_OK', sys.implementation.name)"])


if __name__ == '__main__':
  main()
