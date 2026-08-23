"""Portable-module smoke test for the MicroPython Unix port."""

import sys

from lib import certificates, logger, timew, update


class FakeTime:
  def localtime(self):
    return (2026, 8, 23, 12, 34, 56, 6, 235)


class FakeIO:
  def read_file(self, path):
    raise OSError('missing')


class FakeGitHub:
  def sha(self):
    return 'remote-sha'


clock = timew.Time(time=FakeTime())
assert clock.dateTimeIso() == '2026-08-23T12:34:56Z'
log = logger.config(time=clock, enabled=True, include=['.*'], exclude=[])
assert log(append='unix')('ok') == '[2026-08-23T12:34:56Z][unix] ok'
ota = update.OTAUpdater(io=FakeIO(), github=FakeGitHub(), logger=log)
assert ota.compare() == (None, 'remote-sha')
assert len(certificates.for_host('api.github.com')) > 500
assert sys.implementation.name == 'micropython'
print('MICROPYTHON_UNIX_SMOKE_OK', sys.version)
