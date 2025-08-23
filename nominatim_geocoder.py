# -*- coding: utf-8 -*-
"""Nominatim geocoder implementation with simple in-memory cache and rate limiting.
Respect usage policy: one request per second (fixed).
"""
from __future__ import annotations
import time
import json
import urllib.parse
import urllib.request
from typing import Optional, Dict
from .geocoding_base import GeocodeResult, IGeocoder
from .settings_store import SettingsStore

class NominatimGeocoder(IGeocoder):
    BASE_URL = 'https://nominatim.openstreetmap.org/search'

    def __init__(self, rate_limit_per_sec: Optional[float] = None, user_agent: Optional[str] = None):
        # rate_limit_per_sec 引数や設定値は使用せず、常に 1 req/sec に固定
        self.store = SettingsStore()
        self.rate = 1.0
        self.user_agent = user_agent or self.store.get_user_agent()
        self._last_request_ts = 0.0
        self._cache: Dict[str, GeocodeResult] = {}

    def _throttle(self):
        if self.rate <= 0:
            return
        min_interval = 1.0 / self.rate
        now = time.monotonic()
        wait = self._last_request_ts + min_interval - now
        if wait > 0:
            time.sleep(wait)
        self._last_request_ts = time.monotonic()

    def geocode(self, address: str) -> GeocodeResult:
        key = address.strip()
        if not key:
            return GeocodeResult(lon=None, lat=None, status='FAIL', raw={}, error='Empty address')
        if key in self._cache:
            return self._cache[key]
        self._throttle()
        params = {
            'q': key,
            'format': 'jsonv2',
            'limit': 1,
            'addressdetails': 0,
        }
        url = self.BASE_URL + '?' + urllib.parse.urlencode(params)
        headers = {
            'User-Agent': self.user_agent,
            'Accept-Language': 'ja,en;q=0.8'
        }
        # デフォルトUAのままなら Nominatim ポリシー的に拒否される可能性があるので早めに失敗を返す
        if 'set your email' in self.user_agent.lower():
            res = GeocodeResult(lon=None, lat=None, status='FAIL', raw={}, error='User-Agent (email) 未設定')
            self._cache[key] = res
            return res
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read().decode('utf-8', 'replace')
            parsed = json.loads(data)
            if not parsed:
                res = GeocodeResult(lon=None, lat=None, status='FAIL', raw={}, error='No result')
            else:
                item = parsed[0]
                try:
                    lat = float(item['lat'])
                    lon = float(item['lon'])
                except Exception:
                    res = GeocodeResult(lon=None, lat=None, status='FAIL', raw=item, error='Parse error')
                else:
                    # precision は 'type' や 'class' を簡易転用
                    precision = item.get('type')
                    res = GeocodeResult(lon=lon, lat=lat, status='OK', raw=item, precision=precision)
        except Exception as e:
            res = GeocodeResult(lon=None, lat=None, status='FAIL', raw={}, error=str(e))
        self._cache[key] = res
        return res
