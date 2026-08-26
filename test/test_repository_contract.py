import ast
from pathlib import Path
import sys

from scripts import configure_env


def test_repository_bootstrap_source_is_device_only():
  assert Path('device/boot.py').is_file()
  assert Path('device/main.py').is_file()
  assert Path('device/env.example.py').is_file()
  assert Path('device/lib/update.py').is_file()
  assert not Path('src').exists()
  assert not Path('device/env.py').exists()


def test_application_start_call_uses_only_v3_contract():
  module = ast.parse(Path('device/main.py').read_text(encoding='utf-8'))
  calls = [
    node for node in ast.walk(module)
    if isinstance(node, ast.Call)
    and isinstance(node.func, ast.Attribute)
    and node.func.attr == 'start'
  ]

  assert len(calls) == 1
  assert calls[0].args == []
  assert [keyword.arg for keyword in calls[0].keywords] == ['settings', 'updater']


def test_github_provider_receives_configured_update_mode():
  module = ast.parse(Path('device/main.py').read_text(encoding='utf-8'))
  calls = [
    node for node in ast.walk(module)
    if isinstance(node, ast.Call)
    and isinstance(node.func, ast.Attribute)
    and node.func.attr == 'GitHub'
  ]

  assert len(calls) == 1
  assert 'mode' in [keyword.arg for keyword in calls[0].keywords]
  assert "'githubUpdateMode': 'branch'" in Path('device/env.example.py').read_text()
  assert "env.settings.get('githubUpdateMode', 'branch')" in Path(
    'scripts/device_smoke.py'
  ).read_text()


def test_removed_device_modules_and_packaging_shims_are_absent():
  for path in (
    'device/lib/base64.py',
    'device/lib/logger.py',
    'device/lib/timew.py',
    'setup.py',
    'MANIFEST.in',
    'test/test_logger.py',
  ):
    assert not Path(path).exists()


def test_ci_configuration_defaults_to_ignored_build_path(tmp_path, monkeypatch):
  monkeypatch.chdir(tmp_path)
  monkeypatch.setenv('OTA_WIFI_AP', 'test-network')
  monkeypatch.setenv('OTA_WIFI_PASSWORD', 'test-password')
  monkeypatch.setenv('OTA_GITHUB_REMOTE', 'https://github.com/example/application')
  monkeypatch.setattr(sys, 'argv', ['configure_env.py'])

  configure_env.main()

  output = Path('build/device-env.py')
  contents = output.read_text(encoding='utf-8')
  assert output.is_file()
  assert "'githubUpdateMode': 'branch'" in contents
  assert "'githubRemoteBranch': 'main'" in contents
  assert 'githubUsername' not in contents
  assert 'logInclude' not in contents


def test_ci_configuration_supports_release_mode(tmp_path, monkeypatch):
  monkeypatch.chdir(tmp_path)
  monkeypatch.setenv('OTA_WIFI_AP', 'test-network')
  monkeypatch.setenv('OTA_WIFI_PASSWORD', 'test-password')
  monkeypatch.setenv('OTA_GITHUB_REMOTE', 'https://github.com/example/application')
  monkeypatch.setenv('OTA_GITHUB_UPDATE_MODE', 'release')
  monkeypatch.setattr(sys, 'argv', ['configure_env.py'])

  configure_env.main()

  contents = Path('build/device-env.py').read_text(encoding='utf-8')
  assert "'githubUpdateMode': 'release'" in contents
