import env, lib.requests, lib.logger, lib.timew, time, os, machine
from lib import certificates, update

t = lib.timew.Time(time=time)

# Configure Logger
logger = lib.logger.config(
  enabled=env.settings.get('debug', False),
  include=env.settings.get('logInclude', ['.*']),
  exclude=env.settings.get('logExclude', []),
  time=t,
)
log = logger(append='boot')
log("The current time is %s" % t.human())

loggerOta = logger(append='OTAUpdater')

io = update.IO(os=os, logger=loggerOta)
github = update.GitHub(
  io=io,
  remote=env.settings['githubRemote'],
  branch=env.settings.get('githubRemoteBranch', 'master'),
  logger=loggerOta,
  requests=lib.requests,
  username=env.settings.get('githubUsername', ''),
  token=env.settings.get('githubToken', ''),
  ca_certs=certificates.for_host,
  timeout=env.settings.get('httpTimeout', 10),
)
updater = update.OTAUpdater(
  io=io,
  github=github,
  logger=loggerOta,
  machine=machine,
  minimumFreeBytes=env.settings.get('otaMinimumFreeBytes', 65536),
)

try:
  updater.update()
except Exception as e:
  log('Failed to OTA update:', e)

try:
  import src.main as application_main
  application_main.start(env=env, requests=lib.requests, logger=logger, time=t, updater=updater)
except Exception:
  if updater.rollback():
    machine.reset()
  raise
