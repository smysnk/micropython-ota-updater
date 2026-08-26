import io

import pytest

from lib import certificates
from lib import requests


class FakeSocket:
  def __init__(self, response):
    self.lines = iter(response['lines'])
    self.body = io.BytesIO(response.get('body', b''))
    self.writes = []
    self.closed = False
    self.timeout = None

  def settimeout(self, timeout):
    self.timeout = timeout

  def connect(self, address):
    self.address = address

  def write(self, data):
    self.writes.append(data)

  def readline(self):
    return next(self.lines, b'')

  def read(self, size=-1):
    return self.body.read(size)

  def close(self):
    self.closed = True


class FakeSocketModule:
  SOCK_STREAM = 1

  def __init__(self, *responses):
    self.responses = iter(responses)
    self.created = []

  def getaddrinfo(self, host, port, family, socket_type):
    return [(2, 1, 6, '', (host, port))]

  def socket(self, family, socket_type, protocol):
    sock = FakeSocket(next(self.responses))
    self.created.append(sock)
    return sock


class FakeTLSModule:
  PROTOCOL_TLS_CLIENT = 1
  CERT_REQUIRED = 2
  CERT_NONE = 0


class FakeTLSContext:
  def __init__(self):
    self.loaded = None
    self.verify_mode = None

  def load_verify_locations(self, *args, **kwargs):
    self.loaded = (args, kwargs)

  def wrap_socket(self, sock, server_hostname=None):
    self.server_hostname = server_hostname
    return sock


class RejectingTLSContext(FakeTLSContext):
  def load_verify_locations(self, *args, **kwargs):
    raise OSError('invalid trust root')


def test_response_saves_binary_data_and_closes(tmp_path):
  raw = FakeSocket({'lines': [], 'body': b'\x00\xffcontent'})
  response = requests.Response(raw, 200)
  output = tmp_path / 'download.bin'

  response.save(output)

  assert output.read_bytes() == b'\x00\xffcontent'
  assert raw.closed is True


def test_micropython_tls_loads_der_anchor_with_native_positional_api(monkeypatch):
  context = FakeTLSContext()
  sock = FakeSocket({'lines': []})
  ca_data = b'der-certificate'
  monkeypatch.setattr(requests, '_tls_module', lambda: (FakeTLSModule, True))

  assert requests._wrap_tls(sock, 'api.github.com', ca_data, context) is sock
  assert context.loaded == ((ca_data,), {})
  assert context.verify_mode == FakeTLSModule.CERT_REQUIRED
  assert context.server_hostname == 'api.github.com'


def test_invalid_trust_root_fails_closed():
  sock = FakeSocket({'lines': []})

  with pytest.raises(OSError, match='invalid trust root'):
    requests._wrap_tls(sock, 'api.github.com', b'invalid', RejectingTLSContext())


def test_https_get_parses_response_and_sends_bytes(monkeypatch):
  sockets = FakeSocketModule({
    'lines': [b'HTTP/1.0 200 OK\r\n', b'Content-Type: application/json\r\n', b'\r\n'],
    'body': b'{"ok": true}',
  })
  monkeypatch.setattr(requests, 'socket', sockets)

  response = requests.get(
    'https://example.test/path',
    headers={'X-Test': 'yes'},
    timeout=7,
    ca_certs=b'der-certificate',
    ssl_context=FakeTLSContext(),
  )

  assert response.status_code == 200
  assert response.json() == {'ok': True}
  assert sockets.created[0].timeout == 7
  assert b'GET /path HTTP/1.0\r\n' in sockets.created[0].writes
  assert b'X-Test' in sockets.created[0].writes


def test_request_rejects_chunked_response_and_closes_socket(monkeypatch):
  sockets = FakeSocketModule({
    'lines': [b'HTTP/1.1 200 OK\r\n', b'Transfer-Encoding: chunked\r\n', b'\r\n'],
  })
  monkeypatch.setattr(requests, 'socket', sockets)

  with pytest.raises(ValueError, match='Chunked'):
    requests.get(
      'https://example.test/',
      ca_certs=b'der-certificate',
      ssl_context=FakeTLSContext(),
    )

  assert sockets.created[0].closed is True


def test_request_follows_bounded_redirect(monkeypatch):
  sockets = FakeSocketModule(
    {
      'lines': [b'HTTP/1.0 302 Found\r\n', b'Location: /final\r\n', b'\r\n'],
    },
    {
      'lines': [b'HTTP/1.0 200 OK\r\n', b'\r\n'],
      'body': b'done',
    },
  )
  monkeypatch.setattr(requests, 'socket', sockets)

  response = requests.get(
    'https://example.test/start',
    ca_certs=b'der-certificate',
    ssl_context=FakeTLSContext(),
  )

  assert response.content == b'done'
  assert b'GET /final HTTP/1.0\r\n' in sockets.created[1].writes
  assert sockets.created[0].closed is True


def test_request_closes_socket_for_malformed_status(monkeypatch):
  sockets = FakeSocketModule({'lines': [b'not-http\r\n']})
  monkeypatch.setattr(requests, 'socket', sockets)

  with pytest.raises(ValueError, match='Invalid HTTP status'):
    requests.get(
      'https://example.test/',
      ca_certs=b'der-certificate',
      ssl_context=FakeTLSContext(),
    )

  assert sockets.created[0].closed is True


def test_certificates_are_available_for_both_github_hosts():
  assert len(certificates.for_host('api.github.com')) > 500
  assert len(certificates.for_host('raw.githubusercontent.com')) > 500
  with pytest.raises(ValueError, match='No pinned CA'):
    certificates.for_host('example.com')


def test_plain_http_and_non_default_ports_are_rejected():
  with pytest.raises(ValueError, match='verified HTTPS'):
    requests.get('http://example.test/')
  with pytest.raises(ValueError, match='Non-default'):
    requests.get('https://example.test:8443/')


def test_redirect_limit_closes_socket(monkeypatch):
  sockets = FakeSocketModule({
    'lines': [b'HTTP/1.0 302 Found\r\n', b'Location: /again\r\n', b'\r\n'],
  })
  monkeypatch.setattr(requests, 'socket', sockets)

  with pytest.raises(ValueError, match='Redirect limit'):
    requests.get(
      'https://example.test/start',
      ca_certs=b'der-certificate',
      ssl_context=FakeTLSContext(),
      max_redirects=0,
    )

  assert sockets.created[0].closed is True


def test_non_get_http_wrappers_are_not_exposed():
  for name in ('request', 'head', 'post', 'put', 'patch', 'delete'):
    assert not hasattr(requests, name)
