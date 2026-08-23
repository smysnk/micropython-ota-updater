#!/usr/bin/env python3
"""Check that the bundled roots validate the current GitHub certificate chains."""

from lib import certificates, requests


URLS = (
  'https://api.github.com/repos/micropython/micropython',
  'https://raw.githubusercontent.com/micropython/micropython/v1.28.0/README.md',
)


def main():
  for url in URLS:
    response = requests.get(url, ca_certs=certificates.for_host, timeout=15)
    try:
      if response.status_code != 200:
        raise SystemExit('%s returned HTTP %d' % (url, response.status_code))
      # Read the body so TLS and response streaming are both exercised.
      size = len(response.content)
      print('Verified TLS for %s (%d bytes)' % (url, size))
    finally:
      response.close()


if __name__ == '__main__':
  main()
