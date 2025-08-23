# -*- coding: utf-8 -*-
"""Google Geocoding API implementation.
Uses API key from settings. No fallback to other providers.
Precision derives from result types (first matched in PRIORITY order).
"""
from __future__ import annotations
import json
import time
import urllib.parse
import urllib.request
from typing import Optional, List
from .geocoding_base import GeocodeResult, IGeocoder
from .settings_store import SettingsStore

PRIORITY = [
    'street_address', 'premise', 'subpremise', 'route', 'intersection',
    'plus_code', 'neighborhood', 'sublocality', 'sublocality_level_1',
    'locality', 'administrative_area_level_3', 'administrative_area_level_2',
    'administrative_area_level_1', 'country'
]

class GoogleGeocoder(IGeocoder):
    BASE_URL = 'https://maps.googleapis.com/maps/api/geocode/json'

    def __init__(self, api_key: Optional[str] = None):
        store = SettingsStore()
        self.api_key = api_key if api_key is not None else store.get_api_key()
        self._last_ts = 0.0
        # small courtesy pause to avoid hammering (not official rate control)
        self._min_interval = 0.05  # 20 req/sec max theoretical

    def _throttle(self):
        now = time.monotonic()
        wait = self._last_ts + self._min_interval - now
        if wait > 0:
            time.sleep(wait)
        self._last_ts = time.monotonic()

    def _precision_from_types(self, types: List[str]) -> Optional[str]:
        for p in PRIORITY:
            if p in types:
                return p
        return types[0] if types else None

    def geocode(self, address: str) -> GeocodeResult:  # type: ignore[override]
        addr = address.strip()
        if not addr:
            return GeocodeResult(lon=None, lat=None, status='FAIL', raw={}, error='Empty address')
        if not self.api_key:
            return GeocodeResult(lon=None, lat=None, status='FAIL', raw={}, error='Missing Google API key')
        self._throttle()
        params = {'address': addr, 'key': self.api_key}
        url = self.BASE_URL + '?' + urllib.parse.urlencode(params)
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = resp.read().decode('utf-8', 'replace')
            js = json.loads(data)
        except Exception as e:
            return GeocodeResult(lon=None, lat=None, status='FAIL', raw={}, error=str(e))
        status = js.get('status')
        if status != 'OK':
            # Map common statuses to error message
            msg = status
            if status == 'ZERO_RESULTS':
                msg = 'Zero results'
            elif status == 'OVER_QUERY_LIMIT':
                msg = 'Over query limit'
            elif status == 'REQUEST_DENIED':
                msg = 'Request denied'
            elif status == 'INVALID_REQUEST':
                msg = 'Invalid request'
            return GeocodeResult(lon=None, lat=None, status='FAIL', raw=js, error=msg)
        results = js.get('results') or []
        if not results:
            return GeocodeResult(lon=None, lat=None, status='FAIL', raw=js, error='Empty results')
        r0 = results[0]
        try:
            loc = r0['geometry']['location']
            lat = float(loc['lat'])
            lon = float(loc['lng'])
        except Exception:
            return GeocodeResult(lon=None, lat=None, status='FAIL', raw=r0, error='Parse error')
        precision = self._precision_from_types(r0.get('types', []))
        return GeocodeResult(lon=lon, lat=lat, status='OK', raw=r0, precision=precision)
