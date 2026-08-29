import sys

from scripts import hardware_smoke


def test_hardware_smoke_bounds_reboot_checks_and_leaves_application_running(monkeypatch):
  commands = []
  monkeypatch.setattr(
    hardware_smoke.subprocess,
    'run',
    lambda command, check: commands.append((command, check)),
  )
  sleeps = []
  monkeypatch.setattr(hardware_smoke.time, 'sleep', sleeps.append)
  monkeypatch.setattr(sys, 'argv', ['hardware_smoke.py', '--port', '/dev/device'])

  hardware_smoke.main()

  prefix = ['mpremote', 'connect', '/dev/device']
  assert commands == [
    (prefix + ['run', 'scripts/device_smoke.py'], True),
    (prefix + ['reset', 'disconnect'], True),
    (
      prefix + [
        'exec',
        "import sys; print('MICROPYTHON_REBOOT_OK', sys.implementation.name)",
      ],
      True,
    ),
    (prefix + ['reset', 'disconnect'], True),
  ]
  assert sleeps == [2]
