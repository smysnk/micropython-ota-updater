import hashlib
import json
from pathlib import Path

from lib import certificates


def test_production_firmware_manifest_is_pinned():
  manifest = json.loads(Path('firmware/manifest.json').read_text())
  board = manifest['boards']['ESP32_GENERIC']

  assert manifest['stable'] == 'v1.28.0'
  assert board['version'] == manifest['stable']
  assert board['status'] == 'production'
  assert board['url'].startswith('https://micropython.org/resources/firmware/')
  assert len(board['sha256']) == 64
  int(board['sha256'], 16)


def test_pinned_root_certificates_have_reviewed_fingerprints():
  assert hashlib.sha256(certificates.for_host('api.github.com')).hexdigest() == (
    '4ff460d54b9c86dabfbcfc5712e0400d2bed3fbc4d4fbdaa86e06adcd2a9ad7a'
  )
  assert hashlib.sha256(certificates.for_host('raw.githubusercontent.com')).hexdigest() == (
    '96bcec06264976f37460779acf28c5a7cfe8a3c0aae11a8ffcee05c0bddf08c6'
  )
