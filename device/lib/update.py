def _no_log(*parts):
  return None


def _quote_ref(value):
  """Percent-encode a Git ref for use as one API path component."""
  encoded = ''
  for byte in value.encode('utf-8'):
    character = chr(byte)
    if (
      'a' <= character <= 'z'
      or 'A' <= character <= 'Z'
      or '0' <= character <= '9'
      or character in '-._~'
    ):
      encoded += character
    else:
      encoded += '%%%02X' % byte
  return encoded


class IO:
  DIRECTORY_TYPE = 0x4000

  def __init__(self, os=None, log=None):
    self.os = os
    self.log = log or _no_log

  def exists(self, path):
    try:
      self.os.stat(path)
      return True
    except OSError:
      return False

  def rmtree(self, path):
    if not self.exists(path):
      return
    self.log('Removing directory [%s]' % path)
    for entry in self.ilistdir(path):
      child = self.path(path, entry[0])
      if entry[1] == self.DIRECTORY_TYPE:
        self.rmtree(child)
      else:
        self.os.remove(child)
    self.os.rmdir(path)

  def ilistdir(self, path):
    if hasattr(self.os, 'ilistdir'):
      return self.os.ilistdir(path)
    entries = []
    for entry in self.os.scandir(path):
      entry_type = self.DIRECTORY_TYPE if entry.is_dir() else 0x8000
      entries.append((entry.name, entry_type, 0))
    return entries

  def remove(self, path):
    if self.exists(path):
      self.os.remove(path)

  def move(self, from_path, to_path):
    self.log('Moving [%s] to [%s]' % (from_path, to_path))
    self.os.rename(from_path, to_path)

  def mkdir(self, path):
    self.log('Making directory [%s]' % path)
    self.os.mkdir(path)

  def read_file(self, path):
    with open(path) as source:
      return source.read()

  def write_file(self, path, contents):
    self.log('Writing file [%s]' % path)
    with open(path, 'w') as destination:
      destination.write(contents)

  def path(self, *parts):
    return '/'.join(parts).replace('//', '/').lstrip('/').rstrip('/')

  def free_bytes(self, path='.'):
    if not hasattr(self.os, 'statvfs'):
      return None
    stats = self.os.statvfs(path)
    return stats[0] * stats[3]


class OTAUpdater:
  def __init__(
    self,
    mainDir='src',
    remoteDir=None,
    nextDir='src.next',
    previousDir='src.previous',
    versionFile='.version',
    pendingFile='.ota-pending',
    minimumFreeBytes=65536,
    machine=None,
    io=None,
    github=None,
    log=None,
  ):
    self.github = github
    self.mainDir = mainDir
    self.remoteDir = remoteDir or mainDir
    self.nextDir = nextDir
    self.previousDir = previousDir
    self.versionFile = versionFile
    self.pendingFile = pendingFile
    self.minimumFreeBytes = minimumFreeBytes
    self.machine = machine
    self.io = io
    self.log = log or _no_log

  def recover(self):
    """Recover conservatively from a reset during an update swap."""
    if not self.io.exists(self.pendingFile):
      if not self.io.exists(self.mainDir) and self.io.exists(self.previousDir):
        self.io.move(self.previousDir, self.mainDir)
        return True
      if self.io.exists(self.previousDir):
        self.io.rmtree(self.previousDir)
      if self.io.exists(self.nextDir):
        self.io.rmtree(self.nextDir)
      return False

    if self.io.exists(self.previousDir):
      self.log('Unconfirmed update found; restoring previous application')
      if self.io.exists(self.mainDir):
        self.io.rmtree(self.mainDir)
      self.io.move(self.previousDir, self.mainDir)
      if self.io.exists(self.nextDir):
        self.io.rmtree(self.nextDir)
      self.io.remove(self.pendingFile)
      return True

    # This is either an interrupted first install or a prepared update that had
    # not started swapping directories.  Keep an existing main application.
    if self.io.exists(self.nextDir):
      self.io.rmtree(self.nextDir)
    self.io.remove(self.pendingFile)
    return False

  def compare(self):
    self.log('Pulling down remote...')
    local_sha = None
    try:
      local_sha = self.io.read_file('%s/%s' % (self.mainDir, self.versionFile))
    except OSError:
      self.log('No version file found.')
    remote_sha = self.github.sha()
    self.log('Local SHA:', local_sha)
    self.log('Remote SHA:', remote_sha)
    return local_sha, remote_sha

  def checkForUpdate(self):
    local_sha, remote_sha = self.compare()
    if local_sha != remote_sha:
      self.machine.reset()

  def _check_space(self):
    free_bytes = self.io.free_bytes('.')
    if free_bytes is not None and free_bytes < self.minimumFreeBytes:
      raise OSError('Not enough free space for OTA update: %d bytes' % free_bytes)

  def update(self):
    if self.recover():
      return False
    local_sha, remote_sha = self.compare()
    if local_sha == remote_sha:
      return False

    self._check_space()
    self.io.rmtree(self.nextDir)
    self.io.mkdir(self.nextDir)
    try:
      self.github.download(remote_sha, self.nextDir, base=self.remoteDir)
      self.io.write_file(self.io.path(self.nextDir, self.versionFile), remote_sha)
      if self.io.read_file(self.io.path(self.nextDir, self.versionFile)) != remote_sha:
        raise OSError('Staged version marker could not be verified')

      self.io.write_file(self.pendingFile, remote_sha)
      self.io.rmtree(self.previousDir)
      if self.io.exists(self.mainDir):
        self.io.move(self.mainDir, self.previousDir)
      self.io.move(self.nextDir, self.mainDir)
      return True
    except Exception:
      if not self.io.exists(self.mainDir) and self.io.exists(self.previousDir):
        self.io.move(self.previousDir, self.mainDir)
      if self.io.exists(self.nextDir):
        self.io.rmtree(self.nextDir)
      self.io.remove(self.pendingFile)
      raise

  def confirm(self):
    """Confirm that the newly installed application has started successfully."""
    self.io.remove(self.pendingFile)
    self.io.rmtree(self.previousDir)

  def rollback(self):
    if not self.io.exists(self.previousDir):
      return False
    if self.io.exists(self.mainDir):
      self.io.rmtree(self.mainDir)
    self.io.move(self.previousDir, self.mainDir)
    if self.io.exists(self.nextDir):
      self.io.rmtree(self.nextDir)
    self.io.remove(self.pendingFile)
    return True


class GitHub:
  def __init__(
    self,
    requests=None,
    remote=None,
    io=None,
    log=None,
    mode='branch',
    branch='main',
    token='',
    ca_certs=None,
    timeout=10,
  ):
    self.requests = requests
    self.remote = remote.rstrip('/').replace('https://github.com', 'https://api.github.com/repos')
    self.io = io
    self.log = log or _no_log
    self.mode = mode
    self.branch = branch
    self.ca_certs = ca_certs
    self.timeout = timeout
    self.headers = {
      'Accept': 'application/vnd.github+json',
      'User-Agent': 'micropython-ota-updater/3',
      'X-GitHub-Api-Version': '2022-11-28',
    }
    if token:
      self.headers['Authorization'] = 'Bearer %s' % token

  def _get(self, url):
    return self.requests.get(
      url,
      log=self.log,
      headers=self.headers,
      timeout=self.timeout,
      ca_certs=self.ca_certs,
    )

  def _require_success(self, response, operation):
    if 200 <= response.status_code <= 299:
      return
    reason = response.reason
    if isinstance(reason, bytes):
      reason = str(reason, 'utf-8')
    raise OSError('GitHub %s failed: HTTP %d %s' % (operation, response.status_code, reason))

  def _branch_sha(self):
    response = self._get('%s/commits?per_page=1&sha=%s' % (self.remote, self.branch))
    try:
      self._require_success(response, 'commit lookup')
      commits = response.json()
      if not commits:
        raise OSError('GitHub returned no commits for branch %s' % self.branch)
      return commits[0]['sha']
    finally:
      response.close()

  def _release_sha(self):
    response = self._get('%s/releases/latest' % self.remote)
    try:
      self._require_success(response, 'latest release lookup')
      release = response.json()
      tag = release.get('tag_name')
      if not tag:
        raise OSError('GitHub latest release did not include a tag_name')
    finally:
      response.close()

    self.log('Latest GitHub release:', tag)
    reference = _quote_ref('tags/%s' % tag)
    response = self._get('%s/commits/%s' % (self.remote, reference))
    try:
      self._require_success(response, 'release tag lookup')
      commit = response.json()
      sha = commit.get('sha')
      if not sha:
        raise OSError('GitHub release tag %s did not resolve to a commit SHA' % tag)
      return sha
    finally:
      response.close()

  def sha(self):
    if self.mode == 'branch':
      return self._branch_sha()
    if self.mode == 'release':
      return self._release_sha()
    raise ValueError('Unsupported GitHub update mode: %s' % self.mode)

  def download(self, sha=None, destination=None, currentDir='', base=''):
    url = '%s/contents/%s?ref=%s' % (self.remote, self.io.path(base, currentDir), sha)
    response = self._get(url)
    try:
      self._require_success(response, 'directory listing')
      entries = response.json()
    finally:
      response.close()

    for entry in entries:
      destination_path = self.io.path(destination, currentDir, entry['name'])
      if entry['type'] == 'file':
        file_response = self._get(entry['download_url'])
        try:
          self._require_success(file_response, 'file download')
          file_response.save(destination_path)
        finally:
          file_response.close()
      elif entry['type'] == 'dir':
        self.io.mkdir(destination_path)
        self.download(
          sha=sha,
          destination=destination,
          currentDir=self.io.path(currentDir, entry['name']),
          base=base,
        )
