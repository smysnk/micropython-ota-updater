"""Small, streaming HTTP client for MicroPython."""

import json as json_module
import socket


class Response:
  def __init__(self, raw, status_code, reason=b'', headers=None):
    self.raw = raw
    self.status_code = status_code
    self.reason = reason
    self.headers = headers or {}
    self.encoding = 'utf-8'
    self._cached = None

  def close(self):
    if self.raw:
      self.raw.close()
      self.raw = None

  def save(self, filename):
    try:
      with open(filename, 'wb') as outfile:
        while True:
          data = self.raw.read(512)
          if not data:
            break
          outfile.write(data)
    finally:
      self.close()

  @property
  def content(self):
    if self._cached is None:
      try:
        self._cached = self.raw.read()
      finally:
        self.close()
    return self._cached

  @property
  def text(self):
    return str(self.content, self.encoding)

  def json(self):
    return json_module.loads(self.content)

  def __enter__(self):
    return self

  def __exit__(self, exc_type, exc_value, traceback):
    self.close()


def _tls_module():
  try:
    import tls
    return tls, True
  except ImportError:
    import ssl
    return ssl, False


def _ca_data_for_host(ca_certs, host):
  if callable(ca_certs):
    return ca_certs(host)
  return ca_certs


def _wrap_tls(sock, host, ca_certs, ssl_context=None):
  tls, is_micropython_tls = _tls_module()
  context = ssl_context or tls.SSLContext(tls.PROTOCOL_TLS_CLIENT)
  ca_data = _ca_data_for_host(ca_certs, host)
  if ca_data:
    if is_micropython_tls:
      context.load_verify_locations(ca_data)
    else:
      context.load_verify_locations(cadata=ca_data)
  elif is_micropython_tls:
    raise ValueError('A CA certificate is required for verified TLS to %s' % host)
  context.verify_mode = tls.CERT_REQUIRED
  return context.wrap_socket(sock, server_hostname=host)


def _split_url(url):
  try:
    proto, dummy, host, path = url.split('/', 3)
  except ValueError:
    proto, dummy, host = url.split('/', 2)
    path = ''
  return proto, dummy, host, path


def _redirect_url(url, location):
  if location.startswith('http://') or location.startswith('https://'):
    return location
  proto, _, host, _ = _split_url(url)
  if location.startswith('/'):
    return '%s//%s%s' % (proto, host, location)
  return '%s/%s' % (url.rsplit('/', 1)[0], location)


def get(
  url,
  headers=None,
  timeout=10,
  log=None,
  ca_certs=None,
  ssl_context=None,
  max_redirects=3,
):
  headers = {} if headers is None else headers.copy()
  log = log or (lambda *parts: None)

  proto, _, host, path = _split_url(url)
  if proto != 'https:':
    raise ValueError('Only verified HTTPS requests are supported')
  if ':' in host:
    raise ValueError('Non-default HTTPS ports are not supported')

  address = socket.getaddrinfo(host, 443, 0, socket.SOCK_STREAM)[0]
  sock = socket.socket(address[0], address[1], address[2])
  stream = None
  sock.settimeout(timeout)
  try:
    log('GET %s %s' % (host, path))
    sock.connect(address[-1])
    sock = _wrap_tls(sock, host, ca_certs, ssl_context=ssl_context)
    stream = sock if hasattr(sock, 'readline') else sock.makefile('rwb', buffering=0)

    request_path = path.encode() if isinstance(path, str) else path
    host_header = host.encode() if isinstance(host, str) else host
    stream.write(b'GET /%s HTTP/1.0\r\n' % request_path)
    if 'Host' not in headers:
      stream.write(b'Host: %s\r\n' % host_header)
    if 'User-Agent' not in headers:
      stream.write(b'User-Agent: micropython-ota-updater/3\r\n')

    for key in headers:
      value = headers[key]
      key = key.encode() if isinstance(key, str) else key
      value = value.encode() if isinstance(value, str) else value
      stream.write(key)
      stream.write(b': ')
      stream.write(value)
      stream.write(b'\r\n')
    stream.write(b'Connection: close\r\n\r\n')

    status_line = stream.readline().split(None, 2)
    if len(status_line) < 2:
      raise ValueError('Invalid HTTP status line')
    status = int(status_line[1])
    reason = status_line[2].rstrip() if len(status_line) > 2 else b''
    response_headers = {}
    while True:
      line = stream.readline()
      if not line or line == b'\r\n':
        break
      if b':' not in line:
        continue
      key, value = line.split(b':', 1)
      response_headers[str(key, 'utf-8').lower()] = str(value.strip(), 'utf-8')

    if status in (301, 302, 303, 307, 308):
      location = response_headers.get('location')
      stream.close()
      if stream is not sock:
        sock.close()
      sock = None
      stream = None
      if not location or max_redirects <= 0:
        raise ValueError('Redirect limit reached for %s' % url)
      return get(
        _redirect_url(url, location),
        headers=headers,
        timeout=timeout,
        log=log,
        ca_certs=ca_certs,
        ssl_context=ssl_context,
        max_redirects=max_redirects - 1,
      )

    if response_headers.get('transfer-encoding', '').lower() == 'chunked':
      raise ValueError('Chunked responses are not supported')
    return Response(stream, status, reason=reason, headers=response_headers)
  except Exception:
    if stream and stream is not sock:
      stream.close()
    if sock:
      sock.close()
    raise
