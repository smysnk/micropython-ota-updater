"""Report whether an OTA installation has reached its clean steady state."""

import os


def checks_for(root_entries):
  entries = set(root_entries)
  return (
    ('Active application directory exists', 'src' in entries),
    ('Pending-update marker was cleared', '.ota-pending' not in entries),
    ('Staging directory was removed', 'src.next' not in entries),
    ('Rollback directory was removed', 'src.previous' not in entries),
  )


def main(root_entries=None):
  if root_entries is None:
    root_entries = os.listdir('/')
  failed = False
  for description, passed in checks_for(root_entries):
    print('[%s] %s' % ('PASS' if passed else 'FAIL', description))
    failed = failed or not passed
  if failed:
    raise SystemExit(1)


if __name__ == '__main__':
  main()
