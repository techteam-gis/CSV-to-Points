"""Mapbox Geocoding API implementation (forward geocoding).
Requires access token. Minimal single-result usage to reduce quota.
"""
from __future__ import annotations
import json, time, urllib.parse, urllib.request
from typing import Optional
from .geocoding_base import GeocodeResult, IGeocoder
from .settings_store import SettingsStore

class MapboxGeocoder(IGeocoder):
    BASE_URL = 'https://api.mapbox.com/geocoding/v5/mapbox.places'

    def __init__(self, access_token: Optional[str] = None):
        store = SettingsStore()
        self.token = access_token if access_token is not None else store.get_mapbox_token()
        self._last = 0.0
        self._min_interval = 0.05  # light courtesy throttle

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
        if not self.token:
            return GeocodeResult(None, None, 'FAIL', {}, error='Missing Mapbox token')
        self._throttle()
        params = {'access_token': self.token, 'limit': 1}
        url = f"{self.BASE_URL}/{urllib.parse.quote(q)}.json?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = resp.read().decode('utf-8','replace')
            js = json.loads(data)
        except Exception as e:
            return GeocodeResult(None, None, 'FAIL', {}, error=str(e))
        feats = js.get('features') or []
        if not feats:
            return GeocodeResult(None, None, 'FAIL', js, error='Zero results')
        f0 = feats[0]
        try:
            coords = f0.get('geometry',{}).get('coordinates') or []
            lon, lat = float(coords[0]), float(coords[1])
        except Exception:
            return GeocodeResult(None, None, 'FAIL', f0, error='Parse error')
        precision = None
        pt = f0.get('place_type') or []
        if isinstance(pt, list) and pt:
            precision = pt[0]
        return GeocodeResult(lon, lat, 'OK', f0, precision=precision)
