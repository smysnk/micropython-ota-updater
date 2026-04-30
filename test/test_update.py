import unittest
from unittest.mock import MagicMock, call, ANY
import json

import lib.update
import requests

def setup():
  machine = MagicMock()
  io = MagicMock()
  logger = MagicMock()
  github = MagicMock()

  u = lib.update.OTAUpdater(
    machine=machine,
    io=io,
    logger=logger,
    github=github,
  )

  return {
    'update': u,
    'machine': machine,
    'io': io,
    'logger': logger,
    'github': github,
  }

def setupGithub(*args, **kargs):
  requests = MagicMock(name='requests')
  os = MagicMock(name='os')
  logger = MagicMock(name='logger')
  base64 = MagicMock(name='base64')
  io = lib.update.IO(os=os, logger=logger)
  github = lib.update.GitHub(
    *args, **kargs,
    requests=requests,
    io=io,
    logger=logger,
    base64=base64,
  )

  return {
    'github': github,
    'requests': requests,
    'io': io,
    'logger': logger,
    'os': os,
    'base64': base64,
  }

def test_github_sha_shouldReturnSha():
  mocks = setupGithub(remote='https://github.com/smysnk/ota-test')
  result = MagicMock()
  result.status_code = 200
  result.json.return_value = [{'sha': 'bd446083db139931631cfd0a9dddf869c5b776b2'}]
  mocks['requests'].get.return_value = result
  
  assert mocks['github'].sha() == 'bd446083db139931631cfd0a9dddf869c5b776b2'

def test_github_sha_callCorrectApiEndpoint():
  mocks = setupGithub(remote='https://github.com/smysnk/ota-test', branch='edf')
  result = MagicMock()
  result.status_code = 200
  result.json.return_value = [{'sha': 'bd446083db139931631cfd0a9dddf869c5b776b2'}]
  mocks['requests'].get.return_value = result
    
  mocks['github'].sha()
  mocks['requests'].get.assert_has_calls(
    [
      call.get('https://api.github.com/repos/smysnk/ota-test/commits?per_page=1&sha=edf', logger=ANY, headers=ANY)
    ]
  )

def test_github_authHeader_shouldUseAuthorizationBasic():
  mocks = setupGithub(remote='https://github.com/smysnk/ota-test')
  mocks['base64'].b64encode.return_value = b'dXNlcjp0b2tlbg=='

  github = lib.update.GitHub(
    remote='https://github.com/smysnk/ota-test',
    requests=mocks['requests'],
    io=mocks['io'],
    logger=mocks['logger'],
    base64=mocks['base64'],
    username='user',
    token='token',
  )

  mocks['base64'].b64encode.assert_called_once_with(b'user:token')
  assert github.headers == {'Authorization': 'Basic dXNlcjp0b2tlbg=='}

def test_github_update_shouldHandleValueError():
  mocks = setupGithub(remote='https://github.com/smysnk/ota-test')
  mocks['requests'].get.return_value.json.side_effect = [
    [
      {
        "name":"README.md",
        "download_url":"https://raw.githubusercontent.com/smysnk/ota-test/01f5e563ee8466b33fe7a9dbef2b9c7348b44e6d/README.md",
        "type":"file",
      },
      {
        "name":"README2.md",
        "download_url":"https://raw.githubusercontent.com/smysnk/ota-test/01f5e563ee8466b33fe7a9dbef2b9c7348b44e6d/README2.md",
        "type":"file",
      },
      {
        "name":"sub",
        "download_url":"https://raw.githubusercontent.com/smysnk/ota-test/01f5e563ee8466b33fe7a9dbef2b9c7348b44e6d/sub",
        "type":"dir",
      }
    ],
    [
      {
        "name":"README.md",
        "download_url":"https://raw.githubusercontent.com/smysnk/ota-test/01f5e563ee8466b33fe7a9dbef2b9c7348b44e6d/sub/README.md",
        "type":"file",
      },
    ],
  ];

  mocks['github'].download(sha='abc', destination='123', base='raw')
  # print(mocks['io'].downloadFile.assert_called_with('https://raw.githubusercontent.com/smysnk/ota-test/01f5e563ee8466b33fe7a9dbef2b9c7348b44e6d/README.md', '123/README.md'))
  # print(mocks['requests'].get.mock_calls)
  print(mocks['os'].mock_calls)
  mocks['requests'].get.assert_has_calls(
    [
      call('https://api.github.com/repos/smysnk/ota-test/contents/raw?ref=abc', logger=ANY, headers=ANY),
      call().json(),
      call('https://raw.githubusercontent.com/smysnk/ota-test/01f5e563ee8466b33fe7a9dbef2b9c7348b44e6d/README.md', logger=ANY, headers=ANY),
      call().save('123/README.md'),
      call('https://raw.githubusercontent.com/smysnk/ota-test/01f5e563ee8466b33fe7a9dbef2b9c7348b44e6d/README2.md', logger=ANY, headers=ANY),
      call().save('123/README2.md'),
      call('https://api.github.com/repos/smysnk/ota-test/contents/raw/sub?ref=abc', logger=ANY, headers=ANY),
      call().json(),
      call('https://raw.githubusercontent.com/smysnk/ota-test/01f5e563ee8466b33fe7a9dbef2b9c7348b44e6d/sub/README.md', logger=ANY, headers=ANY),
      call().save('123/sub/README.md')
    ]
  )


# def test_updater_canGetLatestVersion():
#   mocks = setup()
#   # mocks[''].get.return_value.json.return_value = {
#   #   'tag_name': ''
#   # }
#   assert()
#   mocks['update']


# def test_updater_canGetLatestVersionabc():

#   (u, request, io) = setup()
#   request.get.return_value.json.return_value = [{'sha': 'bd446083db139931631cfd0a9dddf869c5b776b2'}]

#   print(u._check_for_new_version())

#   print(request, io)


#   assert False


  # response = self.requests.post("https://api.datadoghq.com/api/v1/series", headers=self.headers, json=data, timeout=self.timeout)
