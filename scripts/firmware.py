#!/usr/bin/env python3
"""Download and verify pinned MicroPython firmware artifacts."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
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


def artifact_path(board, override=None):
  return Path(override or board['filename'])


def esptool_command(board, operation, port='auto', path=None):
  command = [sys.executable, '-m', 'esptool', '--chip', board['chip']]
  if port != 'auto':
    command.extend(('--port', port))
  if operation == 'erase':
    command.append('erase-flash')
    return command
  if operation == 'flash':
    command.extend((
      '--baud',
      str(board['baud']),
      'write-flash',
      board['flash_address'],
      str(path),
    ))
    return command
  raise ValueError('Unsupported esptool operation %s' % operation)


def run_esptool(command, runner=subprocess.run):
  print('+', ' '.join(command))
  runner(command, check=True)


def flash(path, board, port='auto', runner=subprocess.run):
  download(path, board)
  verify(path, board)
  run_esptool(esptool_command(board, 'flash', port=port, path=path), runner=runner)


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('command', choices=('download', 'verify', 'erase', 'flash'))
  parser.add_argument('--manifest', default='firmware/manifest.json')
  parser.add_argument('--board', default='ESP32_GENERIC')
  parser.add_argument('--port', default='auto')
  source = parser.add_mutually_exclusive_group()
  source.add_argument('--output')
  source.add_argument('--input')
  args = parser.parse_args()
  board = load_board(args.manifest, args.board)
  path = artifact_path(board, args.output or args.input)
  if args.command == 'download':
    download(path, board)
  elif args.command == 'verify':
    verify(path, board)
  elif args.command == 'erase':
    run_esptool(esptool_command(board, 'erase', port=args.port))
  elif args.command == 'flash':
    flash(path, board, port=args.port)


if __name__ == '__main__':
  main()
