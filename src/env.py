settings = {
  'wifiAP': '',
  'wifiPassword': '',
  'controllerName': 'grow-controller', # Used for DHCP hostname
  'wifiConnectTimeout': 30, # seconds
  'debug': False,
  'logInclude': ['.*'], # regex supported
  'logExclude': [], # regex supported
  'httpTimeout': 10, # seconds

  # Auto-Updating
  'githubRemote': 'https://github.com/smysnk/my-grow',
  'githubRemoteBranch': 'master',
  'githubUsername': '', # Optional: Without this, you may hit API limits
  'githubToken': '', # Optional: Without this, you may hit API limits
  'otaMinimumFreeBytes': 65536,
}
