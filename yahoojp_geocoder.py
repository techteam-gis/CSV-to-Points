"""Yahoo! JAPAN 地図 Geocoder API 実装 (シンプル)。"""
from __future__ import annotations
import json, time, urllib.parse, urllib.request
from typing import Optional
from .geocoding_base import GeocodeResult, IGeocoder
from .settings_store import SettingsStore

class YahooJapanGeocoder(IGeocoder):
    BASE_URL = 'https://map.yahooapis.jp/geocode/V1/geoCoder'

    def __init__(self, appid: Optional[str] = None):
        store = SettingsStore()
        self.appid = appid if appid is not None else store.get_yahoojp_appid()
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
        if not self.appid:
            return GeocodeResult(None, None, 'FAIL', {}, error='Missing Yahoo Japan AppID')
        self._throttle()
        params = {'appid': self.appid, 'query': q, 'output': 'json'}
        url = self.BASE_URL + '?' + urllib.parse.urlencode(params)
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = resp.read().decode('utf-8','replace')
            js = json.loads(data)
        except Exception as e:
            return GeocodeResult(None, None, 'FAIL', {}, error=str(e))
        featcoll = (js.get('Feature') or [])
        if not featcoll:
            return GeocodeResult(None, None, 'FAIL', js, error='Zero results')
        f0 = featcoll[0]
        try:
            coord_str = (f0.get('Geometry') or {}).get('Coordinates','')
            lon_s, lat_s = coord_str.split(',')[:2]  # lon,lat order
            lon, lat = float(lon_s), float(lat_s)
        except Exception:
            return GeocodeResult(None, None, 'FAIL', f0, error='Parse error')
        precision = (f0.get('Property') or {}).get('MatchLevel')
        return GeocodeResult(lon, lat, 'OK', f0, precision=precision)
