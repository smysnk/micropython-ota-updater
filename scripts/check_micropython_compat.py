#!/usr/bin/env python3
"""Compile all device modules with the selected MicroPython compiler."""

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('--compiler')
  parser.add_argument('--source', action='append')
  args = parser.parse_args()
  compiler = args.compiler
  if not compiler:
    adjacent = Path(sys.executable).parent / 'mpy-cross'
    compiler = str(adjacent) if adjacent.exists() else 'mpy-cross'
  requested_sources = args.source or [
    'device',
    'scripts/check_ota_state.py',
    'scripts/device_smoke.py',
    'scripts/micropython_unix_smoke.py',
  ]
  sources = []
  for requested in requested_sources:
    path = Path(requested)
    sources.extend(path.rglob('*.py') if path.is_dir() else [path])
  sources = sorted(sources)
  failures = []
  with tempfile.TemporaryDirectory(prefix='micropython-compat-') as output:
    for index, source in enumerate(sources):
      target = Path(output) / ('%03d-%s.mpy' % (index, source.stem))
      result = subprocess.run(
        [compiler, '-o', str(target), str(source)],
        text=True,
        capture_output=True,
        check=False,
      )
      if result.returncode:
        failures.append((source, result.stderr or result.stdout))
  if failures:
    for source, message in failures:
      print('%s:\n%s' % (source, message))
    raise SystemExit('%d MicroPython compatibility check(s) failed' % len(failures))
  print('Compiled %d device modules with %s' % (len(sources), compiler))


if __name__ == '__main__':
  main()
