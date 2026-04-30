settings = {
  'wifiAP': '',
  'wifiPassword': '',
  'controllerName': 'grow-controller', # Used for DHCP hostname
  'logInclude': ['.*'], # regex supported
  'logExclude': [], # regex supported
  'httpTimeout': 2, # seconds

  # Auto-Updating
  'githubRemote': 'https://github.com/smysnk/my-grow',
  'githubRemoteBranch': 'master',
  'githubUsername': '', # Optional: Without this, you may hit API limits
  'githubToken': '', # Optional: Without this, you may hit API limits
}
