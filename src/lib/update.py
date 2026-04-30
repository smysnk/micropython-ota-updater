class IO:
  def __init__(self, os=None, logger=None):
    self.os = os
    self.log = logger(append='io')

  def rmtree(self, path):
    if not self.exists(path):
      return

    self.log('Removing directory [%s]' % path)
    for entry in self.os.ilistdir(path):
      isDir = entry[1] == 0x4000
      if isDir:
        self.rmtree(path + '/' + entry[0])
      else:
        self.os.remove(path + '/' + entry[0])
    self.os.rmdir(path)

  def move(self, fromPath, toPath):
    self.log('Moving [%s] to [%s]' % (fromPath, toPath))
    self.os.rename(fromPath, toPath)

  def copy(self, fromPath, toPath):
    self.log('Copying [%s] to [%s]' % (fromPath, toPath))
    if not self.exists(toPath):
      self.mkdir(toPath)

    for entry in self.os.ilistdir(fromPath):
      self.copy(fromPath + '/' + entry[0], toPath + '/' + entry[0])

    with open(fromPath) as fromFile:
      with open(toPath, 'w') as toFile:
        CHUNK_SIZE = 512 # bytes
        data = fromFile.read(CHUNK_SIZE)
        while data:
          toFile.write(data)
          data = fromFile.read(CHUNK_SIZE)
      toFile.close()
    fromFile.close()

  def exists(self, path) -> bool:
    try:
      self.os.listdir(path)
      return True
    except:
      return False

  def mkdir(self, path):
    self.log('Making directory [%s]' % path)
    self.os.mkdir(path)

  def readFile(self, path):
    with open(path) as f:
      return f.read()

  def writeFile(self, path, contents):
    self.log('Writing file %s' % path)
    with open(path, 'w') as file:
      file.write(contents)
      file.close()

  def path(self, *args):
    return '/'.join(args).replace('//', '/').lstrip('/').rstrip('/')

class OTAUpdater:

  def __init__(
    self,
    mainDir='src',
    nextDir='next',
    versionFile='.version',
    machine=None,
    io=None,
    github=None,
    logger=None,
  ):
    self.github = github
    self.mainDir = mainDir
    self.nextDir = nextDir
    self.versionFile = versionFile
    self.machine = machine
    self.io = io
    self.log = logger

  def compare(self):
    self.log('Pulling down remote... ')
    localSha = None
    try:
      localSha = self.io.readFile('%s/%s' % (self.mainDir, self.versionFile))
    except:
      self.log('No version file found.', name="compare")

    remoteSha = self.github.sha()

    self.log('Local SHA: ', localSha)
    self.log('Remote SHA: ', remoteSha)
    return (localSha, remoteSha)

  def checkForUpdate(self):
    (localSha, remoteSha) = self.compare()
    if localSha != remoteSha:
      # Reset the device so we don't have to worry about the watchdog
      self.machine.reset()

  def update(self):
    (localSha, remoteSha) = self.compare()
    if localSha == remoteSha:
      return

    self.io.rmtree(self.nextDir)
    self.io.mkdir(self.nextDir)
    self.github.download(remoteSha, self.nextDir, base=self.mainDir)
    self.io.writeFile(self.nextDir + '/' + self.versionFile, remoteSha)
    self.io.rmtree(self.mainDir)
    self.io.move(self.nextDir, self.mainDir)

class GitHub:
  def __init__(self, requests=None, remote=None, io=None, logger=None, branch='master', username='', token='', base64=None):
    self.requests = requests
    self.remote = remote.rstrip('/').replace('https://github.com', 'https://api.github.com/repos')
    self.io = io
    self.log = logger(append='github')
    self.branch = branch
    self.logger = logger

    if username and token:
      encoded = base64.b64encode(('%s:%s' % (username, token)).encode())
      if isinstance(encoded, bytes):
        encoded = encoded.decode()
      self.headers = {'Authorization': 'Basic %s' % encoded}
    else:
      self.headers = {}

  def sha(self):    
    result = self.requests.get('%s/commits?per_page=1&sha=%s' % (self.remote, self.branch), logger=self.logger, headers=self.headers)
    if result.status_code == 200:
      sha = result.json()[0]['sha']
    else:
      raise Exception('Unexpected response from GitHub: %d:%s' % (result.status_code, result.reason))
    result.close()
    return sha
    
  def download(self, sha=None, destination=None, currentDir='', base=''):
    fileList = self.requests.get('%s/contents/%s?ref=%s' % (self.remote, self.io.path(base, currentDir), sha), logger=self.logger, headers=self.headers)

    for file in fileList.json():
      if file['type'] == 'file':
        result = self.requests.get(file['download_url'], logger=self.logger, headers=self.headers)
        result.save(self.io.path(destination, currentDir, file['name']))
      elif file['type'] == 'dir':
        self.io.mkdir(self.io.path(destination, currentDir, file['name']))
        self.download(sha=sha, destination=destination, currentDir=self.io.path(currentDir, file['name']), base=base)

    fileList.close()
