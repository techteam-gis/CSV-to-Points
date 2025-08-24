# -*- coding: utf-8 -*-
"""CsvToPoints プラグイン用の設定を扱うラッパークラス。"""
from __future__ import annotations
from qgis.PyQt.QtCore import QSettings

ORG = 'CsvToPointsPlugin'
APP = 'CsvToPoints'

class SettingsStore:
    def __init__(self):
        self.qs = QSettings()

    # 設定キー
    KEY_USER_AGENT = 'geocode/user_agent'
    KEY_API_KEY = 'geocode/api_key'
    KEY_PROVIDER = 'geocode/provider'
    # プロバイダ別の追加キー
    KEY_MAPBOX_TOKEN = 'geocode/mapbox_token'
    KEY_OPENCAGE_KEY = 'geocode/opencage_key'
    KEY_HERE_APIKEY = 'geocode/here_apikey'
    KEY_YAHOO_JP_APPID = 'geocode/yahoojp_appid'
    KEY_SYNC_THRESHOLD = 'geocode/sync_threshold'
    KEY_SYNC_ALL = 'geocode/sync_all'
    # 自動判定のカスタムキーワード
    KEY_CUSTOM_LAT_KW = 'detect/custom_lat_keywords'
    KEY_CUSTOM_LON_KW = 'detect/custom_lon_keywords'
    KEY_CUSTOM_ADDR_KW = 'detect/custom_addr_keywords'

    DEFAULT_USER_AGENT = 'CsvToPointsPlugin/0.1 (set your email)'
    DEFAULT_PROVIDER = 'nominatim'
    DEFAULT_SYNC_THRESHOLD = 10

    def get_user_agent(self) -> str:
        return self.qs.value(self.KEY_USER_AGENT, self.DEFAULT_USER_AGENT, type=str)

    def set_user_agent(self, val: str):
        # 空文字ならキーを削除しデフォルトにフォールバックさせる
        if not val:
            self.qs.remove(self.KEY_USER_AGENT)
        else:
            self.qs.setValue(self.KEY_USER_AGENT, val)

    def get_api_key(self) -> str:
        return self.qs.value(self.KEY_API_KEY, '', type=str)

    def set_api_key(self, val: str):
        if not val:
            self.qs.remove(self.KEY_API_KEY)
        else:
            self.qs.setValue(self.KEY_API_KEY, val)

    def get_provider(self) -> str:
        return self.qs.value(self.KEY_PROVIDER, self.DEFAULT_PROVIDER, type=str)

    def set_provider(self, val: str):
        self.qs.setValue(self.KEY_PROVIDER, val)

    def get_sync_threshold(self) -> int:
        return int(self.qs.value(self.KEY_SYNC_THRESHOLD, self.DEFAULT_SYNC_THRESHOLD))

    def set_sync_threshold(self, val: int):
        self.qs.setValue(self.KEY_SYNC_THRESHOLD, val)

    def get_sync_all(self) -> bool:
        return bool(int(self.qs.value(self.KEY_SYNC_ALL, 0)))

    def set_sync_all(self, flag: bool):
        self.qs.setValue(self.KEY_SYNC_ALL, 1 if flag else 0)

    def export_all(self) -> dict:
        return {
            'user_agent': self.get_user_agent(),
            'api_key': self.get_api_key(),
            'provider': self.get_provider(),
            'sync_threshold': self.get_sync_threshold(),
            'sync_all': self.get_sync_all(),
        }

    # Mapbox
    def get_mapbox_token(self) -> str:
        return self.qs.value(self.KEY_MAPBOX_TOKEN, '', type=str)
    def set_mapbox_token(self, val: str):
        if not val:
            self.qs.remove(self.KEY_MAPBOX_TOKEN)
        else:
            self.qs.setValue(self.KEY_MAPBOX_TOKEN, val)

    # OpenCage
    def get_opencage_key(self) -> str:
        return self.qs.value(self.KEY_OPENCAGE_KEY, '', type=str)
    def set_opencage_key(self, val: str):
        if not val:
            self.qs.remove(self.KEY_OPENCAGE_KEY)
        else:
            self.qs.setValue(self.KEY_OPENCAGE_KEY, val)

    # HERE
    def get_here_apikey(self) -> str:
        return self.qs.value(self.KEY_HERE_APIKEY, '', type=str)
    def set_here_apikey(self, val: str):
        if not val:
            self.qs.remove(self.KEY_HERE_APIKEY)
        else:
            self.qs.setValue(self.KEY_HERE_APIKEY, val)

    # Yahoo! JAPAN
    def get_yahoojp_appid(self) -> str:
        return self.qs.value(self.KEY_YAHOO_JP_APPID, '', type=str)
    def set_yahoojp_appid(self, val: str):
        if not val:
            self.qs.remove(self.KEY_YAHOO_JP_APPID)
        else:
            self.qs.setValue(self.KEY_YAHOO_JP_APPID, val)

    # ---- カスタム検出キーワード ----
    def get_custom_lat_keywords_raw(self) -> str:
        return self.qs.value(self.KEY_CUSTOM_LAT_KW, '', type=str)
    def set_custom_lat_keywords_raw(self, val: str):
        if not val:
            self.qs.remove(self.KEY_CUSTOM_LAT_KW)
        else:
            self.qs.setValue(self.KEY_CUSTOM_LAT_KW, val)
    def get_custom_lon_keywords_raw(self) -> str:
        return self.qs.value(self.KEY_CUSTOM_LON_KW, '', type=str)
    def set_custom_lon_keywords_raw(self, val: str):
        if not val:
            self.qs.remove(self.KEY_CUSTOM_LON_KW)
        else:
            self.qs.setValue(self.KEY_CUSTOM_LON_KW, val)
    def get_custom_addr_keywords_raw(self) -> str:
        return self.qs.value(self.KEY_CUSTOM_ADDR_KW, '', type=str)
    def set_custom_addr_keywords_raw(self, val: str):
        if not val:
            self.qs.remove(self.KEY_CUSTOM_ADDR_KW)
        else:
            self.qs.setValue(self.KEY_CUSTOM_ADDR_KW, val)

    @staticmethod
    def parse_keywords(raw: str) -> list[str]:
        items = []
        for part in raw.split(','):
            p = part.strip()
            if not p:
                continue
            items.append(p)
        return items

    def get_all_custom_keywords(self) -> dict:
        return {
            'lat': self.parse_keywords(self.get_custom_lat_keywords_raw()),
            'lon': self.parse_keywords(self.get_custom_lon_keywords_raw()),
            'addr': self.parse_keywords(self.get_custom_addr_keywords_raw()),
        }
