import pytest

from scripts import check_ota_state


def test_checks_for_confirmed_installation():
  assert check_ota_state.checks_for(['boot.py', 'main.py', 'src']) == (
    ('Active application directory exists', True),
    ('Pending-update marker was cleared', True),
    ('Staging directory was removed', True),
    ('Rollback directory was removed', True),
  )


def test_main_reports_each_failed_condition(capsys):
  with pytest.raises(SystemExit) as raised:
    check_ota_state.main(['src.next', 'src.previous', '.ota-pending'])

  assert raised.value.code == 1
  assert capsys.readouterr().out.splitlines() == [
    '[FAIL] Active application directory exists',
    '[FAIL] Pending-update marker was cleared',
    '[FAIL] Staging directory was removed',
    '[FAIL] Rollback directory was removed',
  ]
