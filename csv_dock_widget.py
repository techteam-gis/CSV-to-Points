# -*- coding: utf-8 -*-
"""
Dockable panel for CSV -> Points (Phase 1 skeleton)
Provides drag & drop area and displays basic auto-detected metadata (encoding, delimiter, header fields).
"""
from qgis.PyQt.QtCore import pyqtSignal, Qt, QEvent
from qgis.PyQt.QtGui import QPalette
from .settings_store import SettingsStore
from .provider_registry import get_display_name
from qgis.PyQt.QtWidgets import QWidget, QComboBox, QButtonGroup, QLabel
from qgis.PyQt import uic
import os


class CsvDropDockWidget(QWidget):
    fileDropped = pyqtSignal(str)
    openSettings = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        ui_path = os.path.join(os.path.dirname(__file__), 'csv_dock_widget.ui')
        uic.loadUi(ui_path, self)
        # 初期状態管理フラグ
        self._ever_loaded = False  # 一度でもCSVを読み込んだか
        # 初期は解析結果ビューを隠し、案内ラベルを最大化
        try:
            self.result_view.setVisible(False)
            # 可能なら sizePolicy を拡張方向に (Designer 既定で十分であれば無視)
            sp = self.info_label.sizePolicy()
            sp.setVerticalStretch(1)
            self.info_label.setSizePolicy(sp)
        except Exception:
            pass
        # UI上の warn_geocode_api_label を使用（初期は非表示）
        try:
            if hasattr(self, 'warn_geocode_api_label') and self.warn_geocode_api_label:
                self.warn_geocode_api_label.setVisible(False)
                self.warn_geocode_api_label.setWordWrap(True)
        except Exception:
            pass
        # プロバイダ一覧初期化
        self._populate_providers()
        # 動的テーマ適用
        self._apply_theme()
        # 設定リンク (QLabel) をクリック可能に
        self._setup_settings_links()
        # コンボボックスのサイズ調整（内容に合わせて自動調整）
        for cb in (self.lat_combo, self.lon_combo, self.addr_combo):
            cb.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        # 排他的ボタングループ
        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self._mode_group.addButton(self.pb_mode_coords)
        self._mode_group.addButton(self.pb_mode_geocode)
        # 初期状態では設定 UI を隠す
        self._set_config_visible(False)
        # esc ヒントラベル: ステータスバー風 (初期は非表示 + 高さ0)
        if hasattr(self, 'esc_hint_label') and self.esc_hint_label:
            try:
                fm = self.esc_hint_label.fontMetrics()
                self._esc_hint_label_bar_h = fm.height() + 6  # 上下各3px
                sp2 = self.esc_hint_label.sizePolicy()
                sp2.setHeightForWidth(False)
                self.esc_hint_label.setSizePolicy(sp2)
                self.esc_hint_label.setVisible(False)
                self.esc_hint_label.setMaximumHeight(0)
            except Exception:
                pass
        # ルートレイアウト間隔を 0 にし、result_view との隙間を除去
        try:
            lay = self.layout()
            if lay is not None:
                lay.setSpacing(0)
        except Exception:
            pass

    # ドラッグ＆ドロップ関連イベント
    def dragEnterEvent(self, event):  # type: ignore
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile().lower()
                if path.endswith(('.csv', '.tsv', '.txt')):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):  # type: ignore
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            lower = path.lower()
            if lower.endswith(('.csv', '.tsv', '.txt')):
                self.fileDropped.emit(path)
                break
        event.acceptProposedAction()

    def _setup_settings_links(self):
        self._settings_link_labels = []
        for name in ('geocode_setting_link', 'coords_setting_link'):
            if hasattr(self, name):
                lbl = getattr(self, name)
                if lbl is None:
                    continue
                try:
                    lbl.setCursor(Qt.PointingHandCursor)
                    lbl.installEventFilter(self)
                    self._settings_link_labels.append(lbl)
                    # 既定テキストが無ければ設定
                    if not lbl.text().strip():
                        lbl.setText(self.tr('設定…'))
                    # アクセシビリティ向上のためツールチップ
                    if not lbl.toolTip():
                        lbl.setToolTip(self.tr('設定パネルを開く'))
                except Exception:
                    pass

    # 自動検出結果の表示
    def showResult(self, meta: dict):
        # 初回表示時に設定セクションを出す
        if not self._ever_loaded:
            self._ever_loaded = True
            self._set_config_visible(True)
            # 初回読み込み時に案内ラベルを隠し結果ビューを表示
            try:
                self.info_label.setVisible(False)
                self.result_view.setVisible(True)
            except Exception:
                pass
        if 'error' in meta and not meta.get('header'):
            self.result_view.setPlainText(self.tr('エラー: {err}').format(err=meta.get('error')))
            return
        order = [
            ('file_name', self.tr('ファイル名')),
            ('record_count', self.tr('件数')),
            ('encoding', self.tr('エンコーディング')),
            ('delimiter', self.tr('区切り文字')),
            ('header', self.tr('フィールド')),
            ('lat_field_auto', self.tr('緯度フィールド（自動判定）')),
            ('lon_field_auto', self.tr('経度フィールド（自動判定）')),
            ('address_field_auto', self.tr('住所フィールド（自動判定）')),
            ('lat_candidates', self.tr('緯度フィールド候補')),
            ('lon_candidates', self.tr('経度フィールド候補')),
            ('address_candidates', self.tr('住所フィールド候補')),
        ]
        lines = []
        for key, label in order:
            if key in meta:
                val = meta.get(key)
                # 文字列化時に改行や制御文字を除去 (単行表示)
                sval = str(val).replace('\r','').replace('\n',' ')
                lines.append(f"- {label}: {sval}")
        # 連続する空行を削除
        cleaned = []
        prev_blank = False
        for ln in lines:
            blank = (ln.strip()=='' )
            if blank and prev_blank:
                continue
            cleaned.append(ln)
            prev_blank = blank
        self.result_view.setPlainText("\n".join(cleaned))
        # Esc ヒントラベルを表示
        if hasattr(self, 'esc_hint_label') and self.esc_hint_label:
            self.esc_hint_label.setText(self.tr('(別ファイルはこのパネルへドロップできます / Escキーで初期化)'))
            try:
                bar_h = getattr(self, '_esc_hint_label_bar_h', None)
                if bar_h is None:
                    fm = self.esc_hint_label.fontMetrics()
                    bar_h = fm.height() + 6
                self.esc_hint_label.setMaximumHeight(bar_h)
                self.esc_hint_label.setVisible(True)
            except Exception:
                pass
        has_latlon = bool(meta.get('lat_field_auto') and meta.get('lon_field_auto'))
        has_address = bool(meta.get('address_field_auto'))
        # 緯度経度だけ/住所だけ等、片方しか無い場合は自動的にモードを選択
        if has_latlon and not has_address:
            self._set_mode(0)
        elif (not has_latlon) and has_address:
            self._set_mode(1)
        else:
            # 両方ある場合は緯度経度優先
            if has_latlon and has_address:
                self._set_mode(0)
            elif self.mode_stack.currentIndex() not in (0,1):
                self._set_mode(0)
        header = meta.get('header') or []

        def refill(combo: QComboBox, items):
            prev = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem('')
            for it in items:
                combo.addItem(it)
            if prev and prev in items:
                combo.setCurrentText(prev)
            combo.blockSignals(False)

        refill(self.lat_combo, header)
        refill(self.lon_combo, header)
        refill(self.addr_combo, header)
        if meta.get('lat_field_auto'):
            self.lat_combo.setCurrentText(meta['lat_field_auto'])
        if meta.get('lon_field_auto'):
            self.lon_combo.setCurrentText(meta['lon_field_auto'])
        if meta.get('address_field_auto'):
            self.addr_combo.setCurrentText(meta['address_field_auto'])
        self._update_mode_enable(has_latlon, has_address)

    def _update_mode_enable(self, has_latlon: bool, has_address: bool):
        coords_active = (self.mode_stack.currentIndex() == 0)
        geocode_active = (self.mode_stack.currentIndex() == 1)
        for w in (self.lat_combo, self.lon_combo):
            w.setEnabled(coords_active)
        self.addr_combo.setEnabled(geocode_active)
        sel_lat = self.selected_lat_field()
        sel_lon = self.selected_lon_field()
        sel_addr = self.selected_address_field()
        ready_coords = bool(coords_active and sel_lat and sel_lon)
        # APIキー(=ready providers)が一つも無い場合は geocode 実行不可
        providers_ready = self._has_any_ready_geocode_provider()
        ready_geocode = bool(geocode_active and sel_addr and providers_ready)
        warn_coords = ''
        warn_geocode = ''
        if coords_active and not ready_coords and (sel_lat is None or sel_lon is None):
            warn_coords = self.tr('緯度/経度列を選択してください。緯度/経度列の自動判定に利用する文字列を設定リンクから登録できます。')
        if geocode_active and not ready_geocode and sel_addr is None:
            warn_geocode = self.tr('住所列を選択してください。住所列の自動判定に利用する文字列を設定リンクから登録できます。')
        self.warn_coords_label.setVisible(bool(warn_coords))
        self.warn_coords_label.setText(warn_coords)
        self.warn_geocode_label.setVisible(bool(warn_geocode))
        self.warn_geocode_label.setText(warn_geocode)
        if ready_coords:
            self.build_btn.setEnabled(True)
            self.build_btn.setText(self.tr('ポイント生成'))
        elif ready_geocode:
            self.build_btn.setEnabled(True)
            # 選択プロバイダ表示 (有効な場合)
            prov_id = self.selected_provider() or ''
            prov_disp = get_display_name(prov_id) if prov_id else ''
            suffix = f' ({prov_disp})' if prov_disp else ''
            self.build_btn.setText(self.tr('ポイント生成')+suffix)
        else:
            self.build_btn.setEnabled(False)
            self.build_btn.setText(self.tr('実行 (条件不足)'))
        self.pb_mode_coords.setChecked(coords_active)
        self.pb_mode_geocode.setChecked(geocode_active)

    def _has_any_ready_geocode_provider(self) -> bool:
        """コンボのデータから、少なくとも1つの ready プロバイダ(APIキー登録済み)があるか判定する"""
        try:
            if not hasattr(self, 'geocode_provider_combo') or self.geocode_provider_combo is None:
                return False
            combo = self.geocode_provider_combo
            for i in range(combo.count()):
                d = combo.itemData(i)
                if d and isinstance(d, dict) and d.get('ready'):
                    return True
        except Exception:
            pass
        return False

    def selected_mode_geocode(self) -> bool:
        return self.mode_stack.currentIndex() == 1

    def _set_mode(self, index: int):  # 0=coords,1=addr
        index = 0 if index not in (0, 1) else index
        self.mode_stack.setCurrentIndex(index)
        self.pb_mode_coords.setChecked(index == 0)
        self.pb_mode_geocode.setChecked(index == 1)
        has_latlon = bool(self.lat_combo.count() > 1 and self.lon_combo.count() > 1)
        has_address = bool(self.addr_combo.count() > 1)
        self._update_mode_enable(has_latlon, has_address)

    def selected_lat_field(self):
        t = self.lat_combo.currentText().strip()
        return t or None

    def selected_lon_field(self):
        t = self.lon_combo.currentText().strip()
        return t or None

    def selected_address_field(self):
        t = self.addr_combo.currentText().strip()
        return t or None

    def selected_provider(self):
        if not hasattr(self, 'geocode_provider_combo'):
            return None
        data = self.geocode_provider_combo.currentData()
        if data and isinstance(data, dict):
            return data.get('id')
        return None

    # ---------- Theme (dark / light) ----------
    def _is_dark_mode(self) -> bool:
        pal = self.palette()
        win = pal.color(QPalette.Window)
        if not win.isValid():
            win = pal.color(QPalette.Base)
        return win.lightness() < 128

    def _apply_theme(self):
        dark = self._is_dark_mode()
        if dark:
            btn_bg = '#1f1f1f'
            btn_border = '#000'
            btn_text = '#808080'
            btn_checked_bg = '#fff'
            btn_checked_text = '#000'
            frame_bg = '#2b2b2b'
            frame_border = '#444'
            warn_color = '#ff6b6b'
            result_bg = '#1e1e1e'
            result_fg = '#dcdcdc'
            placeholder_color = '#888'
            bar_bg = '#2f2f2f'
            bar_text = '#aaaaaa'
            link = '#a6c0ff'
            link_hover = '#c7d6ff'
        else:
            btn_bg = '#efefef'
            btn_border = '#a9a9a9'
            btn_text = '#333333'
            btn_checked_bg = '#111111'
            btn_checked_text = '#fff'
            frame_bg = '#fcfcfc'
            frame_border = '#d0d0d0'
            warn_color = '#c00'
            result_bg = ''  # デフォルトに任せる
            result_fg = ''
            placeholder_color = '#888'
            bar_bg = '#ececec'
            bar_text = '#555'
            link = '#2a6ad6'
            link_hover = '#1e56ad'

        style = (
            f"QPushButton#pb_mode_coords, QPushButton#pb_mode_geocode {{ border:1px solid {btn_border}; padding:4px 10px; background:{btn_bg}; color:{btn_text}; }}\n"
            f"QPushButton#pb_mode_coords {{ border-top-left-radius:4px; border-bottom-left-radius:4px; border-right:none; }}\n"
            f"QPushButton#pb_mode_geocode {{ border-top-right-radius:4px; border-bottom-right-radius:4px; }}\n"
            f"QPushButton#pb_mode_coords:checked, QPushButton#pb_mode_geocode:checked {{ background:{btn_checked_bg}; color:{btn_checked_text}; }}\n"
            f"QFrame#card_coords, QFrame#card_geocode {{ border:1px solid {frame_border}; border-radius:4px; background:{frame_bg}; }}\n"
            f"QLabel#warn_coords_label, QLabel#warn_geocode_label, QLabel#warn_geocode_api_label {{ color:{warn_color}; }}\n"
            f"QLabel#esc_hint_label {{ background:{bar_bg}; color:{bar_text}; font-size:11px; padding:2px 6px; }}\n"
            f"QLabel#geocode_setting_link, QLabel#coords_setting_link {{ color:{link}; text-decoration:underline; }}\n"
            f"QLabel#geocode_setting_link:hover, QLabel#coords_setting_link:hover {{ color:{link_hover}; }}\n"
        )
        if dark:
            style += (
                f"QPlainTextEdit#result_view {{ background:{result_bg}; color:{result_fg}; border:1px solid {frame_border}; }}\n"
                f"QPlainTextEdit#result_view:disabled {{ color:{placeholder_color}; }}\n"
            )
        self.setStyleSheet(style)

    # クリック可能ラベルのイベント処理
    def eventFilter(self, obj, ev):  # type: ignore
        try:
            if ev.type() == QEvent.MouseButtonRelease and getattr(self, '_settings_link_labels', None):
                if obj in self._settings_link_labels and ev.button() == Qt.LeftButton:
                    self.openSettings.emit()
                    return True
        except Exception:
            pass
        return super().eventFilter(obj, ev)

    def _populate_providers(self):
        if not hasattr(self, 'geocode_provider_combo'):
            return
        combo = self.geocode_provider_combo
        combo.clear()
        store = SettingsStore()
        # SettingsStore の実際のメソッド名に合わせて readiness 判定
        providers = [
            ('google', lambda s: bool(s.get_api_key())),
            ('nominatim', lambda s: bool(s.get_user_agent() and s.get_user_agent() != s.DEFAULT_USER_AGENT)),
            ('mapbox', lambda s: bool(s.get_mapbox_token())),
            ('opencage', lambda s: bool(s.get_opencage_key())),
            ('yahoojp', lambda s: bool(s.get_yahoojp_appid())),
        ]
        any_ready = False
        for pid, checker in providers:
            ready = False
            try:
                ready = checker(store)
            except Exception:
                ready = False
            label = get_display_name(pid)
            if not ready:
                label += self.tr(' (未設定)')
            combo.addItem(label, {'id': pid, 'ready': ready})
            idx = combo.count()-1
            if not ready:
                combo.model().item(idx).setEnabled(False)  # type: ignore
            else:
                any_ready = True
        # APIキー未登録時の警告表示（geocodeカード上部に表示）
        try:
            if hasattr(self, 'warn_geocode_api_label') and self.warn_geocode_api_label:
                if not any_ready:
                    self.warn_geocode_api_label.setText(self.tr('APIキーが登録されていません。APIキーは設定リンクから登録できます。'))
                    self.warn_geocode_api_label.setVisible(True)
                else:
                    self.warn_geocode_api_label.clear()
                    self.warn_geocode_api_label.setVisible(False)
        except Exception:
            pass
        # デフォルト選択: 最初の ready / なければ空プレースホルダーを選択
        if any_ready:
            for i in range(combo.count()):
                d = combo.itemData(i)
                if d and d.get('ready'):
                    combo.setCurrentIndex(i)
                    break
        else:
            # 空のダミー項目（選択不可ではなく、"未選択" を表す項目）を先頭に追加
            combo.insertItem(0, '', None)
            combo.setCurrentIndex(0)

    def _connect_mode_signals(self):
        if getattr(self, '_mode_connected', False):
            return
        def _on_click_coords():
            self._set_mode(0)
        def _on_click_geocode():
            self._set_mode(1)
        self.pb_mode_coords.clicked.connect(_on_click_coords)
        self.pb_mode_geocode.clicked.connect(_on_click_geocode)
        self.lat_combo.currentIndexChanged.connect(lambda _: self._update_mode_enable(True, True))
        self.lon_combo.currentIndexChanged.connect(lambda _: self._update_mode_enable(True, True))
        self.addr_combo.currentIndexChanged.connect(lambda _: self._update_mode_enable(True, True))
        # プロバイダ選択変更時にもボタンラベル (住所をジオコーディング (provider)) を更新
        if hasattr(self, 'geocode_provider_combo') and self.geocode_provider_combo is not None:
            try:
                self.geocode_provider_combo.currentIndexChanged.connect(lambda _: self._update_mode_enable(True, True))
            except Exception:
                pass
        self._mode_connected = True

    def showEvent(self, e):  # type: ignore
        super().showEvent(e)
        self._connect_mode_signals()
        # ダーク/ライト切替検出 (macOS でのテーマ変更後再描画時)
        try:
            self._apply_theme()
        except Exception:
            pass

    # 進捗バー関連のヘルパ
    def start_progress(self):
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.cancel_btn.setVisible(True)
        self.cancel_btn.setEnabled(True)

    def update_progress(self, val: float):
        self.progress_bar.setValue(int(val))

    def finish_progress(self):
        self.progress_bar.setValue(100)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.cancel_btn.setVisible(False)

    # Esc キーで初期化
    def keyPressEvent(self, e):  # type: ignore
        try:
            if e.key() == Qt.Key_Escape:
                if self._ever_loaded and not self.progress_bar.isVisible():
                    self.reset()
                    e.accept()
                    return
        except Exception:
            pass
        super().keyPressEvent(e)

    # レイヤ生成後に UI を初期化
    def reset(self):
        self.result_view.clear()
        self.result_view.setPlaceholderText(self.tr('解析結果: まだファイルがドロップされていません'))
        # 初期状態では結果ビュー非表示 / 案内ラベル再表示
        try:
            self.result_view.setVisible(False)
            self.info_label.setVisible(True)
        except Exception:
            pass
        for cb in (self.lat_combo, self.lon_combo, self.addr_combo):
            cb.blockSignals(True)
            cb.clear()
            cb.addItem('')
            cb.blockSignals(False)
        self._set_mode(0)
        self.build_btn.setEnabled(False)
        self.build_btn.setText(self.tr('実行 (条件不足)'))
        self.warn_coords_label.setVisible(False)
        self.warn_geocode_label.setVisible(False)
        # 完全初期状態へ戻す (UI 非表示 & フラグリセット)
        self._ever_loaded = False
        self._set_config_visible(False)
        if hasattr(self, 'esc_hint_label') and self.esc_hint_label:
            try:
                self.esc_hint_label.clear()
                self.esc_hint_label.setVisible(False)
                self.esc_hint_label.setMaximumHeight(0)
            except Exception:
                pass

    # -------- 初期状態用ヘルパ --------
    def _set_config_visible(self, visible: bool):
        # モード行, スタック, 実行ボタンをまとめて表示切替
        for w in [self.wdConfig]:
            try:
                w.setVisible(visible)
            except Exception:
                pass
