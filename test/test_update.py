import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lib.update import GitHub, IO, OTAUpdater


class Log:
  def __init__(self):
    self.messages = []

  def __call__(self, *args, **kwargs):
    self.messages.append(' '.join(str(part) for part in args))


class GitHubFixture:
  def __init__(self, sha='new-sha', fail=False):
    self.remote_sha = sha
    self.fail = fail
    self.download_base = None

  def sha(self):
    return self.remote_sha

  def download(self, sha, destination, base):
    self.download_base = base
    Path(destination, 'nested').mkdir()
    Path(destination, 'nested', 'application.py').write_text('VALUE = 2\n')
    if self.fail:
      raise OSError('download interrupted')


def updater(tmp_path, monkeypatch, github=None, minimum_free_bytes=0):
  monkeypatch.chdir(tmp_path)
  log = Log()
  io = IO(os=os, log=log)
  return OTAUpdater(
    io=io,
    github=github or GitHubFixture(),
    log=log,
    machine=MagicMock(),
    minimumFreeBytes=minimum_free_bytes,
  )


def write_current(version='old-sha'):
  Path('src').mkdir()
  Path('src/.version').write_text(version)
  Path('src/application.py').write_text('VALUE = 1\n')


def test_update_stages_and_swaps_without_deleting_previous(tmp_path, monkeypatch):
  ota = updater(tmp_path, monkeypatch)
  write_current()

  assert ota.update() is True
  assert Path('src/.version').read_text() == 'new-sha'
  assert Path('src/nested/application.py').read_text() == 'VALUE = 2\n'
  assert Path('src.previous/.version').read_text() == 'old-sha'
  assert Path('.ota-pending').read_text() == 'new-sha'


def test_update_can_download_a_different_remote_directory(tmp_path, monkeypatch):
  github = GitHubFixture()
  ota = updater(tmp_path, monkeypatch, github=github)
  ota.remoteDir = 'application'
  write_current()

  ota.update()

  assert github.download_base == 'application'


def test_confirm_removes_pending_marker_and_previous_copy(tmp_path, monkeypatch):
  ota = updater(tmp_path, monkeypatch)
  write_current()
  ota.update()

  ota.confirm()

  assert not Path('.ota-pending').exists()
  assert not Path('src.previous').exists()
  assert Path('src').exists()


def test_recover_restores_unconfirmed_application(tmp_path, monkeypatch):
  ota = updater(tmp_path, monkeypatch)
  write_current()
  ota.update()

  assert ota.recover() is True
  assert Path('src/.version').read_text() == 'old-sha'
  assert not Path('.ota-pending').exists()
  assert not Path('src.previous').exists()


def test_recover_restores_previous_when_reset_happens_between_renames(tmp_path, monkeypatch):
  ota = updater(tmp_path, monkeypatch)
  Path('src.previous').mkdir()
  Path('src.previous/.version').write_text('old-sha')
  Path('src.next').mkdir()
  Path('.ota-pending').write_text('new-sha')

  assert ota.recover() is True
  assert Path('src/.version').read_text() == 'old-sha'
  assert not Path('src.next').exists()


def test_recover_discards_prepared_stage_before_first_rename(tmp_path, monkeypatch):
  ota = updater(tmp_path, monkeypatch)
  write_current()
  Path('src.next').mkdir()
  Path('.ota-pending').write_text('new-sha')

  assert ota.recover() is False
  assert Path('src/.version').read_text() == 'old-sha'
  assert not Path('src.next').exists()
  assert not Path('.ota-pending').exists()


def test_failed_download_keeps_current_application(tmp_path, monkeypatch):
  ota = updater(tmp_path, monkeypatch, github=GitHubFixture(fail=True))
  write_current()

  with pytest.raises(OSError, match='interrupted'):
    ota.update()

  assert Path('src/.version').read_text() == 'old-sha'
  assert not Path('src.next').exists()
  assert not Path('.ota-pending').exists()


def test_failed_second_rename_restores_current_application(tmp_path, monkeypatch):
  ota = updater(tmp_path, monkeypatch)
  write_current()
  move = ota.io.move

  def fail_install(from_path, to_path):
    if from_path == 'src.next':
      raise OSError('second rename interrupted')
    return move(from_path, to_path)

  ota.io.move = fail_install
  with pytest.raises(OSError, match='second rename interrupted'):
    ota.update()

  assert Path('src/.version').read_text() == 'old-sha'
  assert not Path('src.next').exists()
  assert not Path('.ota-pending').exists()


def test_update_is_noop_when_versions_match(tmp_path, monkeypatch):
  ota = updater(tmp_path, monkeypatch, github=GitHubFixture(sha='same-sha'))
  write_current('same-sha')

  assert ota.update() is False
  assert not Path('src.previous').exists()


def test_switching_source_modes_uses_resolved_sha_as_update_identity(tmp_path, monkeypatch):
  release = GitHubFixture(sha='same-sha')
  release.mode = 'release'
  ota = updater(tmp_path, monkeypatch, github=release)
  write_current('same-sha')

  assert ota.update() is False

  branch = GitHubFixture(sha='branch-sha')
  branch.mode = 'branch'
  ota.github = branch

  assert ota.update() is True
  assert Path('src/.version').read_text() == 'branch-sha'


def test_update_checks_available_space(tmp_path, monkeypatch):
  ota = updater(tmp_path, monkeypatch, minimum_free_bytes=10**30)
  write_current()

  with pytest.raises(OSError, match='Not enough free space'):
    ota.update()


def test_io_removes_nested_tree(tmp_path, monkeypatch):
  monkeypatch.chdir(tmp_path)
  Path('tree/child').mkdir(parents=True)
  Path('tree/child/file.bin').write_bytes(b'abc')
  io = IO(os=os, log=Log())

  io.rmtree('tree')

  assert not Path('tree').exists()


def make_github(token='', mode='branch'):
  requests = MagicMock()
  io = MagicMock()
  io.path.side_effect = lambda *parts: '/'.join(parts).strip('/')
  github = GitHub(
    remote='https://github.com/smysnk/ota-test',
    branch='feature/test',
    requests=requests,
    io=io,
    log=Log(),
    mode=mode,
    token=token,
    ca_certs=MagicMock(),
  )
  return github, requests


def test_github_uses_bearer_authentication_and_current_api_headers():
  github, _ = make_github(token='secret')

  assert github.headers['Authorization'] == 'Bearer secret'
  assert github.headers['X-GitHub-Api-Version'] == '2022-11-28'
  assert github.headers['User-Agent'].startswith('micropython-ota-updater/')


def test_github_sha_closes_response_and_passes_tls_configuration():
  github, requests = make_github()
  response = requests.get.return_value
  response.status_code = 200
  response.json.return_value = [{'sha': 'abc123'}]

  assert github.sha() == 'abc123'
  response.close.assert_called_once()
  _, kwargs = requests.get.call_args
  assert kwargs['ca_certs'] is github.ca_certs
  assert kwargs['timeout'] == 10
  assert callable(kwargs['log'])


def test_github_release_mode_resolves_latest_tag_to_commit_sha():
  github, requests = make_github(mode='release')
  release_response = MagicMock(status_code=200)
  release_response.json.return_value = {'tag_name': 'v1.2.3'}
  commit_response = MagicMock(status_code=200)
  commit_response.json.return_value = {'sha': 'release-sha'}
  requests.get.side_effect = [release_response, commit_response]

  assert github.sha() == 'release-sha'
  assert requests.get.call_args_list[0].args[0].endswith('/releases/latest')
  assert requests.get.call_args_list[1].args[0].endswith('/commits/tags%2Fv1.2.3')
  release_response.close.assert_called_once()
  commit_response.close.assert_called_once()


def test_github_release_mode_encodes_tag_names_as_one_path_component():
  github, requests = make_github(mode='release')
  release_response = MagicMock(status_code=200)
  release_response.json.return_value = {'tag_name': 'release/one two'}
  commit_response = MagicMock(status_code=200)
  commit_response.json.return_value = {'sha': 'release-sha'}
  requests.get.side_effect = [release_response, commit_response]

  assert github.sha() == 'release-sha'
  assert requests.get.call_args_list[1].args[0].endswith(
    '/commits/tags%2Frelease%2Fone%20two'
  )


def test_github_release_mode_rejects_missing_tag_and_closes_response():
  github, requests = make_github(mode='release')
  response = requests.get.return_value
  response.status_code = 200
  response.json.return_value = {}

  with pytest.raises(OSError, match='tag_name'):
    github.sha()

  response.close.assert_called_once()


def test_github_release_mode_closes_failed_tag_lookup():
  github, requests = make_github(mode='release')
  release_response = MagicMock(status_code=200)
  release_response.json.return_value = {'tag_name': 'v1.2.3'}
  commit_response = MagicMock(status_code=404, reason=b'not found')
  requests.get.side_effect = [release_response, commit_response]

  with pytest.raises(OSError, match='release tag lookup failed: HTTP 404 not found'):
    github.sha()

  release_response.close.assert_called_once()
  commit_response.close.assert_called_once()


def test_github_release_mode_rejects_tag_without_commit_sha():
  github, requests = make_github(mode='release')
  release_response = MagicMock(status_code=200)
  release_response.json.return_value = {'tag_name': 'v1.2.3'}
  commit_response = MagicMock(status_code=200)
  commit_response.json.return_value = {}
  requests.get.side_effect = [release_response, commit_response]

  with pytest.raises(OSError, match='did not resolve to a commit SHA'):
    github.sha()

  release_response.close.assert_called_once()
  commit_response.close.assert_called_once()


def test_github_rejects_unknown_update_mode_without_request():
  github, requests = make_github(mode='nightly')

  with pytest.raises(ValueError, match='Unsupported GitHub update mode: nightly'):
    github.sha()

  requests.get.assert_not_called()


def test_github_reports_http_error_and_closes_response():
  github, requests = make_github()
  response = requests.get.return_value
  response.status_code = 403
  response.reason = b'rate limited'

  with pytest.raises(OSError, match='HTTP 403 rate limited'):
    github.sha()

  response.close.assert_called_once()


def test_removed_io_compatibility_aliases_are_not_exposed():
  assert not hasattr(IO, 'readFile')
  assert not hasattr(IO, 'writeFile')


def test_manual_rollback_restores_previous_application(tmp_path, monkeypatch):
  ota = updater(tmp_path, monkeypatch)
  write_current()
  ota.update()

  assert ota.rollback() is True
  assert Path('src/.version').read_text() == 'old-sha'
  assert not Path('src.previous').exists()
  assert not Path('.ota-pending').exists()
