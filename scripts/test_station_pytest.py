#!/usr/bin/env python3
"""Run pytest and emit Test Station shell adapter suite-json-v1."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import time
from pathlib import Path


class TestStationPytestPlugin:
  def __init__(self) -> None:
    self.tests = {}
    self.collection_errors = []

  def pytest_runtest_logreport(self, report):
    if report.when not in ('setup', 'call', 'teardown'):
      return

    entry = self.tests.setdefault(report.nodeid, create_test_entry(report))
    entry['durationMs'] += round(report.duration * 1000)
    entry['rawDetails']['phases'].append({
      'phase': report.when,
      'outcome': report.outcome,
      'durationMs': round(report.duration * 1000),
    })

    if report.failed:
      entry['status'] = 'failed'
      entry['failureMessages'].append(longrepr_text(report))
    elif report.skipped and entry['status'] != 'failed':
      entry['status'] = 'skipped'
      entry['failureMessages'].append(longrepr_text(report))
    elif report.when == 'call' and entry['status'] != 'failed':
      entry['status'] = 'passed'

  def pytest_collectreport(self, report):
    if report.failed:
      self.collection_errors.append({
        'name': report.nodeid or 'collection failed',
        'fullName': report.nodeid or 'collection failed',
        'status': 'failed',
        'durationMs': 0,
        'file': report.nodeid or None,
        'line': None,
        'column': None,
        'assertions': ['pytest collected the test suite successfully.'],
        'setup': [],
        'mocks': [],
        'failureMessages': [longrepr_text(report)],
        'rawDetails': {'phase': 'collection'},
        'module': 'tests',
        'theme': 'unit',
        'classificationSource': 'adapter',
      })


def create_test_entry(report):
  file_path, line, description = report.location
  return {
    'name': description or report.nodeid,
    'fullName': report.nodeid,
    'status': 'skipped',
    'durationMs': 0,
    'file': normalize_path(file_path),
    'line': line + 1 if isinstance(line, int) else None,
    'column': None,
    'assertions': ['pytest test item completed.'],
    'setup': [],
    'mocks': [],
    'failureMessages': [],
    'rawDetails': {'phases': []},
    'module': 'tests',
    'theme': 'unit',
    'classificationSource': 'adapter',
  }


def normalize_path(value):
  if not value:
    return None
  return Path(value).as_posix()


def longrepr_text(report):
  longrepr = getattr(report, 'longrepr', None)
  if longrepr is None:
    return ''
  return getattr(report, 'longreprtext', None) or str(longrepr)


def build_import_error_payload(error, duration_ms):
  message = f'Unable to import pytest: {error}'
  return {
    'status': 'failed',
    'durationMs': duration_ms,
    'summary': {'total': 1, 'passed': 0, 'failed': 1, 'skipped': 0},
    'coverage': None,
    'tests': [
      {
        'name': 'pytest import',
        'fullName': 'pytest import',
        'status': 'failed',
        'durationMs': duration_ms,
        'file': None,
        'line': None,
        'column': None,
        'assertions': ['pytest is importable in the active Python environment.'],
        'setup': [],
        'mocks': [],
        'failureMessages': [message],
        'rawDetails': {},
        'module': 'tests',
        'theme': 'unit',
        'classificationSource': 'adapter',
      },
    ],
    'warnings': [],
    'rawArtifacts': [
      {
        'relativePath': 'python-pytest-output.log',
        'content': message + '\n',
      },
    ],
    'performanceStats': [],
  }


def main(argv=None):
  argv = list(argv if argv is not None else sys.argv[1:])
  if not argv:
    argv = ['test']

  started = time.perf_counter()

  try:
    import pytest
  except Exception as error:  # pragma: no cover - defensive CI diagnostics
    duration_ms = round((time.perf_counter() - started) * 1000)
    print(json.dumps(build_import_error_payload(error, duration_ms)))
    return 1

  plugin = TestStationPytestPlugin()
  stdout = io.StringIO()
  stderr = io.StringIO()

  with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
    exit_code = pytest.main(argv, plugins=[plugin])

  duration_ms = round((time.perf_counter() - started) * 1000)
  tests = list(plugin.tests.values()) + plugin.collection_errors
  total = len(tests)
  passed = sum(1 for test in tests if test['status'] == 'passed')
  failed = sum(1 for test in tests if test['status'] == 'failed')
  skipped = sum(1 for test in tests if test['status'] == 'skipped')
  status = 'passed' if int(exit_code) == 0 and failed == 0 else 'failed'
  combined_output = ''.join([
    'STDOUT\n',
    stdout.getvalue(),
    '\nSTDERR\n',
    stderr.getvalue(),
  ])

  payload = {
    'status': status,
    'durationMs': duration_ms,
    'summary': {
      'total': total,
      'passed': passed,
      'failed': failed,
      'skipped': skipped,
    },
    'coverage': None,
    'tests': tests,
    'warnings': [] if total else ['pytest did not report any tests.'],
    'rawArtifacts': [
      {
        'relativePath': 'python-pytest-output.log',
        'content': combined_output,
      },
    ],
    'performanceStats': [],
  }

  print(json.dumps(payload))
  return int(exit_code)


if __name__ == '__main__':
  raise SystemExit(main())
