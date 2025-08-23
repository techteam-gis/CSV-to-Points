"""OpenCage Geocoding API implementation (forward only here)."""
from __future__ import annotations
import json, time, urllib.parse, urllib.request
from typing import Optional
from .geocoding_base import GeocodeResult, IGeocoder
from .settings_store import SettingsStore

class OpenCageGeocoder(IGeocoder):
    BASE_URL = 'https://api.opencagedata.com/geocode/v1/json'

    def __init__(self, api_key: Optional[str] = None):
        store = SettingsStore()
        self.key = api_key if api_key is not None else store.get_opencage_key()
        self._last = 0.0
        self._min_interval = 0.10

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
            return GeocodeResult(None, None, 'FAIL', {}, error='Missing OpenCage key')
        self._throttle()
        params = {'q': q, 'key': self.key, 'limit': 1, 'no_annotations': 1}
        url = self.BASE_URL + '?' + urllib.parse.urlencode(params)
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = resp.read().decode('utf-8','replace')
            js = json.loads(data)
        except Exception as e:
            return GeocodeResult(None, None, 'FAIL', {}, error=str(e))
        results = js.get('results') or []
        if not results:
            return GeocodeResult(None, None, 'FAIL', js, error='Zero results')
        r0 = results[0]
        try:
            geom = r0.get('geometry') or {}
            lat = float(geom.get('lat'))
            lon = float(geom.get('lng'))
        except Exception:
            return GeocodeResult(None, None, 'FAIL', r0, error='Parse error')
        precision = None
        conf = r0.get('confidence')
        if conf is not None:
            precision = f'confidence_{conf}'
        return GeocodeResult(lon, lat, 'OK', r0, precision=precision)
