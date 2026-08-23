#!/usr/bin/env python3
"""Download and verify pinned MicroPython firmware artifacts."""

import argparse
import hashlib
import json
import os
from pathlib import Path
from urllib.request import urlopen


def load_board(manifest_path, board_name):
  with Path(manifest_path).open(encoding='utf-8') as source:
    manifest = json.load(source)
  try:
    return manifest['boards'][board_name]
  except KeyError as error:
    raise SystemExit('Unsupported board %s in %s' % (board_name, manifest_path)) from error


def sha256(path):
  digest = hashlib.sha256()
  with Path(path).open('rb') as source:
    for chunk in iter(lambda: source.read(65536), b''):
      digest.update(chunk)
  return digest.hexdigest()


def verify(path, board):
  actual = sha256(path)
  expected = board['sha256'].lower()
  if actual != expected:
    raise SystemExit('Firmware checksum mismatch: expected %s, got %s' % (expected, actual))
  print('Verified %s (%s)' % (path, actual))


def download(path, board):
  destination = Path(path)
  if destination.exists():
    verify(destination, board)
    return
  temporary = destination.with_suffix(destination.suffix + '.part')
  print('Downloading %s' % board['url'])
  try:
    with urlopen(board['url'], timeout=60) as response, temporary.open('wb') as output:
      while True:
        chunk = response.read(65536)
        if not chunk:
          break
        output.write(chunk)
    verify(temporary, board)
    os.replace(temporary, destination)
  finally:
    if temporary.exists():
      temporary.unlink()


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('command', choices=('download', 'verify'))
  parser.add_argument('--manifest', default='firmware/manifest.json')
  parser.add_argument('--board', default='ESP32_GENERIC')
  source = parser.add_mutually_exclusive_group(required=True)
  source.add_argument('--output')
  source.add_argument('--input')
  args = parser.parse_args()
  board = load_board(args.manifest, args.board)
  if args.command == 'download':
    download(args.output, board)
  else:
    verify(args.input, board)


if __name__ == '__main__':
  main()
