import env, lib.requests, os, machine
from lib import certificates, update


def _no_log(*parts):
  return None


log = print if env.settings.get('debug', False) else _no_log

io = update.IO(os=os, log=log)
github = update.GitHub(
  io=io,
  remote=env.settings['githubRemote'],
  mode=env.settings.get('githubUpdateMode', 'branch'),
  branch=env.settings.get('githubRemoteBranch', 'main'),
  log=log,
  requests=lib.requests,
  token=env.settings.get('githubToken', ''),
  ca_certs=certificates.for_host,
  timeout=env.settings.get('httpTimeout', 10),
)
updater = update.OTAUpdater(
  io=io,
  github=github,
  log=log,
  machine=machine,
  minimumFreeBytes=env.settings.get('otaMinimumFreeBytes', 65536),
)

try:
  updater.update()
except Exception as e:
  log('Failed to OTA update:', e)

try:
  import src.main as application_main
  application_main.start(settings=env.settings, updater=updater)
except Exception:
  if updater.rollback():
    machine.reset()
  raise
