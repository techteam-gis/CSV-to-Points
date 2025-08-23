"""Settings dialog: provider selection + API keys + custom field detection keywords."""
from __future__ import annotations

import os
from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog
from .settings_store import SettingsStore
from .provider_registry import iter_providers


FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'settings_dialog.ui'))


class SettingsDialog(QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.setWindowTitle(self.tr('CSV to Points 設定'))
        self.store = SettingsStore()

        # プロバイダ一覧をコンボに設定
        self.provider_combo.clear()
        for pid, disp in iter_providers():
            self.provider_combo.addItem(disp, pid)
        current_provider = self.store.get_provider() or 'nominatim'
        idx = next((i for i in range(self.provider_combo.count()) if self.provider_combo.itemData(i)==current_provider), -1)
        if idx < 0:
            idx = next((i for i in range(self.provider_combo.count()) if self.provider_combo.itemData(i)=='nominatim'), 0)
        self.provider_combo.setCurrentIndex(idx)

        # フィールド自動判定の初期値を設定
        from .field_detector import LAT_KEYWORDS, LON_KEYWORDS, ADDR_KEYWORDS, INITIAL_CUSTOM_KEYWORDS
        customs = self.store.get_all_custom_keywords()
        lat_init = customs.get('lat') or INITIAL_CUSTOM_KEYWORDS['lat']
        lon_init = customs.get('lon') or INITIAL_CUSTOM_KEYWORDS['lon']
        addr_init = customs.get('addr') or INITIAL_CUSTOM_KEYWORDS['addr']
        # fdForm は .ui 側で作るが、ここでは値だけ設定
        self.lat_kw_edit.setText(','.join(lat_init))
        self.lat_kw_edit.setPlaceholderText(self.tr('例: geo_latitude_custom'))
        self.lon_kw_edit.setText(','.join(lon_init))
        self.lon_kw_edit.setPlaceholderText(self.tr('例: geo_long_custom'))
        self.addr_kw_edit.setText(','.join(addr_init))
        self.addr_kw_edit.setPlaceholderText(self.tr('例: direccion,주소'))

        # ジオコーディング関連の設定値を読込
        ua_val = self.store.get_user_agent()
        if ua_val == self.store.DEFAULT_USER_AGENT:
            ua_val = ''
        self.user_agent_edit.setText(ua_val)
        self.api_key_edit.setText(self.store.get_api_key())
        self.mapbox_token_edit.setText(self.store.get_mapbox_token())
        self.opencage_key_edit.setText(self.store.get_opencage_key())
        self.here_key_edit.setText(self.store.get_here_apikey())
        self.yahoojp_appid_edit.setText(self.store.get_yahoojp_appid())

        # 同期モードの設定
        self.sync_threshold_spin.setRange(1, 100000)
        self.sync_threshold_spin.setValue(self.store.get_sync_threshold())
        self.sync_all_check.setChecked(self.store.get_sync_all())

        # シグナル接続
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        self._on_provider_changed(self.provider_combo.currentIndex())

        # デフォルトキーワード（フィルタ用のベース）を保持
        self._LAT_KW = list(LAT_KEYWORDS)
        self._LON_KW = list(LON_KEYWORDS)
        self._ADDR_KW = list(ADDR_KEYWORDS)

    # ---------- slots ----------
    def _on_provider_changed(self, index: int):
        """Stacked ページをプロバイダに合わせて切替"""
        pid = self.provider_combo.itemData(index)
        mapping = {
            'nominatim': 0,
            'google': 1,
            'mapbox': 2,
            'opencage': 3,
            'here': 4,
            'yahoojp': 5,
        }
        self.stack.setCurrentIndex(mapping.get(pid, 0))

    # ---------- 保存 ----------
    def accept(self):
        import re
        def _clean(txt: str) -> str:
            if txt is None:
                return ''
            cleaned = re.sub('[\u200B\u200C\u200D\uFEFF]', '', txt.strip())
            if not cleaned or all(ch in '\r\n\t ' for ch in cleaned):
                return ''
            return cleaned
        s = self.store
        current_pid = self.provider_combo.currentData()
        s.set_provider(_clean(current_pid))
        s.set_user_agent(_clean(self.user_agent_edit.text()))
        s.set_api_key(_clean(self.api_key_edit.text()))
        s.set_sync_threshold(self.sync_threshold_spin.value())
        s.set_sync_all(self.sync_all_check.isChecked())
        s.set_mapbox_token(_clean(self.mapbox_token_edit.text()))
        s.set_opencage_key(_clean(self.opencage_key_edit.text()))
        s.set_here_apikey(_clean(self.here_key_edit.text()))
        s.set_yahoojp_appid(_clean(self.yahoojp_appid_edit.text()))
        base_lat = {k.lower(): True for k in self._LAT_KW}
        base_lon = {k.lower(): True for k in self._LON_KW}
        base_addr = {k.lower(): True for k in self._ADDR_KW}
        def _filter_defaults(raw: str, base: dict) -> str:
            out = []
            for seg in (raw or '').split(','):
                w = seg.strip()
                if not w:
                    continue
                if w.lower() in base:
                    continue
                out.append(w)
            return ','.join(out)
        s.set_custom_lat_keywords_raw(_filter_defaults(_clean(self.lat_kw_edit.text()), base_lat))
        s.set_custom_lon_keywords_raw(_filter_defaults(_clean(self.lon_kw_edit.text()), base_lon))
        s.set_custom_addr_keywords_raw(_filter_defaults(_clean(self.addr_kw_edit.text()), base_addr))
        try:
            s.qs.sync()
        except Exception:
            pass
        super().accept()
