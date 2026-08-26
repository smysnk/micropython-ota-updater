import env
import network
import ntptime
import time


def connect_wifi(settings):
  station = network.WLAN(network.STA_IF)
  if station.isconnected():
    return station

  print('Connecting to network...')
  station.active(True)
  hostname = settings.get('controllerName')
  if hostname:
    network.hostname(hostname)
  station.connect(settings['wifiAP'], settings['wifiPassword'])

  timeout_ms = settings.get('wifiConnectTimeout', 30) * 1000
  started = time.ticks_ms()
  while not station.isconnected():
    if time.ticks_diff(time.ticks_ms(), started) >= timeout_ms:
      status = station.status() if hasattr(station, 'status') else 'unknown'
      raise OSError('Wi-Fi connection timed out; status=%s' % status)
    time.sleep_ms(100)
  return station


connect_wifi(env.settings)
try:
  ntptime.settime()
except OSError as error:
  # A valid clock is required for verified TLS.  Continue only if the RTC is
  # already plausibly set by a previous boot or by mpremote.
  if time.localtime()[0] < 2024:
    raise OSError('NTP failed and the RTC is not valid: %s' % error)
  print('NTP unavailable; using existing RTC:', error)
