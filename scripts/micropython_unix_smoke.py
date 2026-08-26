"""Portable-module smoke test for the MicroPython Unix port."""

import sys

from lib import certificates, update


class FakeIO:
  def read_file(self, path):
    raise OSError('missing')


class FakeGitHub:
  def sha(self):
    return 'remote-sha'


ota = update.OTAUpdater(io=FakeIO(), github=FakeGitHub())
assert ota.compare() == (None, 'remote-sha')
assert len(certificates.for_host('api.github.com')) > 500
assert sys.implementation.name == 'micropython'
print('MICROPYTHON_UNIX_SMOKE_OK', sys.version)
