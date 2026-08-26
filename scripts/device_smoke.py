"""Hardware smoke test executed from RAM by mpremote."""

import os
import sys

import env
from lib import certificates, requests, update


def no_log(*parts):
  return None


io = update.IO(os=os, log=no_log)
github = update.GitHub(
  requests=requests,
  remote=env.settings['githubRemote'],
  mode=env.settings.get('githubUpdateMode', 'branch'),
  branch=env.settings.get('githubRemoteBranch', 'main'),
  token=env.settings.get('githubToken', ''),
  io=io,
  log=no_log,
  ca_certs=certificates.for_host,
  timeout=env.settings.get('httpTimeout', 10),
)
sha = github.sha()
smoke = update.OTAUpdater(
  mainDir='.smoke-current',
  remoteDir='src',
  nextDir='.smoke-next',
  previousDir='.smoke-previous',
  pendingFile='.smoke-pending',
  minimumFreeBytes=0,
  io=io,
  github=github,
  log=no_log,
)
io.rmtree('.smoke-current')
io.rmtree('.smoke-next')
io.rmtree('.smoke-previous')
io.remove('.smoke-pending')
io.mkdir('.smoke-current')
io.write_file('.smoke-current/.version', 'hardware-smoke-old')
if not smoke.update():
  raise AssertionError('Hardware smoke update was unexpectedly a no-op')
if io.read_file('.smoke-current/.version') != sha:
  raise AssertionError('Hardware smoke installed the wrong SHA')
smoke.confirm()
io.rmtree('.smoke-current')
print('MICROPYTHON_SMOKE_OK', sys.implementation.name, sys.version, sha)
