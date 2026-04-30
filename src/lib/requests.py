
class Response:
  def __init__(self, f):
    self.raw = f
    self.encoding = "utf-8"
    self._cached = None

  def close(self):
    if self.raw:
      self.raw.close()
      self.raw = None
    self._cached = None

  def save(self, file):
    CHUNK_SIZE = 512 # bytes
    with open(file, 'w') as outfile:
      data = self.raw.read(CHUNK_SIZE)
      while data:
        outfile.write(data)
        data = self.raw.read(CHUNK_SIZE)
      outfile.close()  
    self.close()

  @property
  def content(self):
    if self._cached is None:
      try:
        self._cached = self.raw.read()
      finally:
        self.raw.close()
        self.raw = None
    return self._cached

  @property
  def text(self):
    return str(self.content, self.encoding)

  def json(self):
    import ujson
    return ujson.loads(self.content)


def request(method, url, data=None, json=None, headers=None, stream=None, timeout=5, logger=None):
  import usocket

  if headers is None:
    headers = {}

  log = lambda *args, **kargs: args
  if logger:
    log = logger(append='request')

  try:
    proto, dummy, host, path = url.split("/", 3)
  except ValueError:
    proto, dummy, host = url.split("/", 2)
    path = ""
  if proto == "http:":
    port = 80
  elif proto == "https:":
    import ussl
    port = 443
  else:
    raise ValueError("Unsupported protocol: " + proto)

  if ":" in host:
    host, port = host.split(":", 1)
    port = int(port)

  ai = usocket.getaddrinfo(host, port, 0, usocket.SOCK_STREAM)
  ai = ai[0]

  s = usocket.socket(ai[0], ai[1], ai[2])
  s.settimeout(timeout)
  try:
    log('%s %s %s' % (method, host, path), name='connect')
    s.connect(ai[-1])
    if proto == "https:":
      s = ussl.wrap_socket(s, server_hostname=host)
    request_method = method.encode() if isinstance(method, str) else method
    request_path = path.encode() if isinstance(path, str) else path
    host_header = host.encode() if isinstance(host, str) else host
    s.write(b"%s /%s HTTP/1.0\r\n" % (request_method, request_path))
    if "Host" not in headers:
      s.write(b"Host: %s\r\n" % host_header)
    # Iterate over keys to avoid tuple alloc
    for k in headers:
      value = headers[k]
      if isinstance(k, str):
        k = k.encode()
      if isinstance(value, str):
        value = value.encode()
      s.write(k)
      s.write(b": ")
      s.write(value)
      s.write(b"\r\n")
    s.write(b'User-Agent: MicroPython Client\r\n')
    if json is not None:
      assert data is None
      import ujson
      data = ujson.dumps(json)
      s.write(b"Content-Type: application/json\r\n")
    if isinstance(data, str):
      data = data.encode()
    if data:
      s.write(b"Content-Length: %d\r\n" % len(data))
    s.write(b"\r\n")
    if data:
      s.write(data)

    l = s.readline()
    #print(l)
    l = l.split(None, 2)
    status = int(l[1])
    reason = ""
    if len(l) > 2:
      reason = l[2].rstrip()
    while True:
      l = s.readline()
      if not l or l == b"\r\n":
        break
      #print(l)
      if l.startswith(b"Transfer-Encoding:"):
        if b"chunked" in l:
          raise ValueError("Unsupported " + l)
      elif l.startswith(b"Location:") and not 200 <= status <= 299:
        raise NotImplementedError("Redirects not yet supported")
  except OSError:
    s.close()
    raise

  resp = Response(s)
  resp.status_code = status
  resp.reason = reason
  return resp


def head(url, **kw):
  return request("HEAD", url, **kw)

def get(url, **kw):
  return request("GET", url, **kw)

def post(url, **kw):
  return request("POST", url, **kw)

def put(url, **kw):
  return request("PUT", url, **kw)

def patch(url, **kw):
  return request("PATCH", url, **kw)

def delete(url, **kw):
  return request("DELETE", url, **kw)
