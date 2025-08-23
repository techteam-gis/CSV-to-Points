"""HERE Geocoding & Search API (geocode endpoint).
Endpoint is fixed to the default and user-provided overrides are ignored.
"""
from __future__ import annotations
import json, time, urllib.parse, urllib.request
from typing import Optional
from .geocoding_base import GeocodeResult, IGeocoder
from .settings_store import SettingsStore

class HereGeocoder(IGeocoder):
    DEFAULT_URL = 'https://geocode.search.hereapi.com/v1/geocode'

    def __init__(self, api_key: Optional[str] = None, endpoint: Optional[str] = None):
        store = SettingsStore()
        self.key = api_key if api_key is not None else store.get_here_apikey()
        # Endpoint override is not supported: always use default
        self.endpoint = self.DEFAULT_URL
        self._last = 0.0
        self._min_interval = 0.05

    def _throttle(self):
        now = time.monotonic()
        wait = self._last + self._min_interval - now
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()

    def geocode(self, address: str) -> GeocodeResult:  # type: ignore[override]
        q = (address or '').strip()
        if not q:
            return GeocodeResult(None, None, 'FAIL', {}, error='Empty address')
        if not self.key:
            return GeocodeResult(None, None, 'FAIL', {}, error='Missing HERE API key')
        self._throttle()
        params = {'q': q, 'apiKey': self.key, 'limit': 1}
        url = self.endpoint + '?' + urllib.parse.urlencode(params)
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = resp.read().decode('utf-8','replace')
            js = json.loads(data)
        except Exception as e:
            return GeocodeResult(None, None, 'FAIL', {}, error=str(e))
        items = js.get('items') or []
        if not items:
            return GeocodeResult(None, None, 'FAIL', js, error='Zero results')
        it0 = items[0]
        try:
            pos = it0.get('position') or {}
            lat = float(pos.get('lat'))
            lon = float(pos.get('lng'))
        except Exception:
            return GeocodeResult(None, None, 'FAIL', it0, error='Parse error')
        precision = it0.get('resultType')
        return GeocodeResult(lon, lat, 'OK', it0, precision=precision)
