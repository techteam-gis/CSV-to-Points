"""Geocoding task.

以前の版ではバックグラウンドスレッド内で dataProvider().change* を呼んでおり
QGIS のスレッドセーフ要件上反映されない/クラッシュする可能性があった。
本版では run() では結果だけ収集し、finished() (メインスレッド) で一括適用する。
"""
from __future__ import annotations
from typing import Callable, Optional, List, Tuple, Dict, Any
from qgis.core import QgsTask, QgsVectorLayer, QgsGeometry, QgsPointXY


class GeocodeTask(QgsTask):
    def __init__(
        self,
        description: str,
        layer: QgsVectorLayer,
        address_field: str,
        geocode_fn: Callable[[str], object],
        finished_callback: Optional[Callable[[bool, int, int, int], None]] = None,
        ) -> None:
        super().__init__(description, QgsTask.CanCancel)
        self.layer = layer
        self.address_field = address_field
        self.geocode_fn = geocode_fn
        self._finished_callback = finished_callback
        # 統計
        self.added = 0
        self.failed = 0
        self.processed = 0
        # 収集結果
        self._success: List[Tuple[int, float, float, str, Dict[str, Any]]] = []  # fid, lon, lat, precision, raw
        self._fail: List[Tuple[int, str]] = []  # fid, error

    # -------- background thread --------
    def run(self) -> bool:
        idx_addr = self.layer.fields().indexFromName(self.address_field)
        if idx_addr < 0:
            return False
        total = self.layer.featureCount() or 1
        for i, feat in enumerate(self.layer.getFeatures()):
            if self.isCanceled():
                break
            if feat.hasGeometry() and not feat.geometry().isEmpty():
                continue
            addr = str(feat.attribute(idx_addr) or '').strip()
            if not addr:
                continue
            try:
                res = self.geocode_fn(addr)
            except Exception as ex:  # noqa
                class _Tmp:
                    status = 'FAIL'
                    lat = None
                    lon = None
                    precision = ''
                    error = str(ex)
                res = _Tmp()
            if getattr(res, 'status', None) == 'OK' and getattr(res, 'lat', None) is not None and getattr(res, 'lon', None) is not None:
                try:
                    raw = getattr(res, 'raw', {}) or {}
                    # 以前のデバッグ出力は削除 (必要なら再度 print するコメントを追加可能)
                    self._success.append((feat.id(), float(res.lon), float(res.lat), getattr(res, 'precision', '') or '', raw))
                except Exception:
                    self._fail.append((feat.id(), 'cast error'))
                    self.failed += 1
                else:
                    self.added += 1
            else:
                self._fail.append((feat.id(), getattr(res, 'error', '') or ''))
                self.failed += 1
            self.processed += 1
            self.setProgress(min(100.0, (i + 1) / total * 100.0))
        if self.isCanceled():
            return False
        return True

    # -------- main thread --------
    def finished(self, result: bool) -> None:  # noqa
        if result and not self.isCanceled():
            try:
                prov = self.layer.dataProvider()
                # 新: Google 形式 (status, error, location_type, ...)
                # 旧: 汎用 _geocode_* 形式
                idx_status = self.layer.fields().indexFromName('status')
                if idx_status < 0:
                    idx_status = self.layer.fields().indexFromName('_geocode_status')
                idx_err = self.layer.fields().indexFromName('error')
                if idx_err < 0:
                    idx_err = self.layer.fields().indexFromName('_geocode_error')
                # precision は Google では location_type に相当
                idx_prec = self.layer.fields().indexFromName('_geocode_precision')
                idx_loc_type_new = self.layer.fields().indexFromName('location_type')
                geom_changes: Dict[int, QgsGeometry] = {}
                attr_changes: Dict[int, Dict[int, object]] = {}
                # 旧 prefix フィールド (後方互換)
                idx_formatted_old = self.layer.fields().indexFromName('_geocode_formatted')
                idx_place_id_old = self.layer.fields().indexFromName('_geocode_place_id')
                idx_loc_type_old = self.layer.fields().indexFromName('_geocode_location_type')
                idx_types_old = self.layer.fields().indexFromName('_geocode_types')
                idx_country_old = self.layer.fields().indexFromName('_geocode_country')
                idx_admin1_old = self.layer.fields().indexFromName('_geocode_admin1')
                idx_admin2_old = self.layer.fields().indexFromName('_geocode_admin2')
                idx_locality_old = self.layer.fields().indexFromName('_geocode_locality')
                idx_postal_old = self.layer.fields().indexFromName('_geocode_postal_code')
                idx_route_old = self.layer.fields().indexFromName('_geocode_route')
                # 新フィールド
                idx_formatted = self.layer.fields().indexFromName('formatted_address')
                idx_place_id = self.layer.fields().indexFromName('place_id')
                idx_types = self.layer.fields().indexFromName('types')
                idx_country = self.layer.fields().indexFromName('country')  # 旧互換のみ
                idx_admin1 = self.layer.fields().indexFromName('administrative_area_level_1')  # 旧互換
                idx_admin2 = self.layer.fields().indexFromName('administrative_area_level_2')  # 旧互換
                idx_locality = self.layer.fields().indexFromName('locality')  # 旧互換
                idx_postal = self.layer.fields().indexFromName('postal_code')
                idx_route = self.layer.fields().indexFromName('route')  # 旧互換
                idx_lat = self.layer.fields().indexFromName('lat')
                idx_lng = self.layer.fields().indexFromName('lng')
                idx_partial = self.layer.fields().indexFromName('partial_match')

                # provider 判定 (フィールドの存在で推測)
                has_google = self.layer.fields().indexFromName('formatted_address') >= 0 and self.layer.fields().indexFromName('place_id') >= 0 and self.layer.fields().indexFromName('types') >= 0
                has_nominatim = self.layer.fields().indexFromName('display_name') >= 0 and self.layer.fields().indexFromName('place_rank') >= 0
                has_mapbox = self.layer.fields().indexFromName('place_name') >= 0 and self.layer.fields().indexFromName('accuracy') >= 0
                has_opencage = self.layer.fields().indexFromName('formatted') >= 0 and self.layer.fields().indexFromName('confidence') >= 0
                has_here = self.layer.fields().indexFromName('title') >= 0 and self.layer.fields().indexFromName('postalCode') >= 0
                has_yahoo = self.layer.fields().indexFromName('AddressMatchingLevel') >= 0 and self.layer.fields().indexFromName('Uid') >= 0

                # index 取得 (共通/各 provider)
                idx_place_id2 = self.layer.fields().indexFromName('place_id')
                idx_display_name = self.layer.fields().indexFromName('display_name')
                idx_place_rank = self.layer.fields().indexFromName('place_rank')
                idx_n_lat = self.layer.fields().indexFromName('lat')
                idx_n_lon = self.layer.fields().indexFromName('lng')
                idx_nom_place_id = self.layer.fields().indexFromName('place_id') if has_nominatim else -1
                idx_nom_display = idx_display_name
                idx_nom_rank = idx_place_rank
                idx_map_id = self.layer.fields().indexFromName('id') if has_mapbox else -1
                idx_map_place_name = self.layer.fields().indexFromName('place_name')
                idx_map_postcode = self.layer.fields().indexFromName('postcode')
                idx_map_accuracy = self.layer.fields().indexFromName('accuracy')
                idx_oc_formatted = self.layer.fields().indexFromName('formatted')
                idx_oc_postcode = self.layer.fields().indexFromName('postcode') if has_opencage else -1
                idx_oc_conf = self.layer.fields().indexFromName('confidence')
                idx_here_id = self.layer.fields().indexFromName('id') if has_here else -1
                idx_here_title = self.layer.fields().indexFromName('title')
                idx_here_postal = self.layer.fields().indexFromName('postalCode')
                idx_yj_uid = self.layer.fields().indexFromName('Uid')
                idx_yj_name = self.layer.fields().indexFromName('Name')
                idx_yj_lvl = self.layer.fields().indexFromName('AddressMatchingLevel')

                for fid, lon, lat, prec, raw in self._success:
                    geom_changes[fid] = QgsGeometry.fromPointXY(QgsPointXY(lon, lat))
                    ch = {}
                    if idx_status >= 0:
                        ch[idx_status] = 'OK'
                    # precision 保存 (旧) or location_type(新)
                    if idx_loc_type_new >= 0:
                        ch[idx_loc_type_new] = prec
                    elif idx_prec >= 0:
                        ch[idx_prec] = prec
                    # Google 由来の追加属性 (存在する場合のみセット)
                    if isinstance(raw, dict):
                        # 新優先
                        if idx_formatted >= 0:
                            ch[idx_formatted] = raw.get('formatted_address') or ''
                        elif idx_formatted_old >= 0:
                            ch[idx_formatted_old] = raw.get('formatted_address') or ''
                        if idx_place_id >= 0:
                            ch[idx_place_id] = raw.get('place_id') or ''
                        elif idx_place_id_old >= 0:
                            ch[idx_place_id_old] = raw.get('place_id') or ''
                        loc_type_val = (raw.get('geometry') or {}).get('location_type', '')
                        if idx_loc_type_new >= 0:
                            ch[idx_loc_type_new] = loc_type_val
                        elif idx_loc_type_old >= 0:
                            ch[idx_loc_type_old] = loc_type_val
                        tlist = raw.get('types') or []
                        if isinstance(tlist, list):
                            join_val = '|'.join(tlist)
                            if idx_types >= 0:
                                ch[idx_types] = join_val
                            elif idx_types_old >= 0:
                                ch[idx_types_old] = join_val
                        comps = raw.get('address_components') or []
                        if isinstance(comps, list):
                            # マッピング (最初に出たものを採用)
                            type_map = {}
                            for c in comps:
                                try:
                                    tps = c.get('types') or []
                                    for t in tps:
                                        if t not in type_map:
                                            type_map[t] = c.get('long_name') or ''
                                except Exception:
                                    continue
                            # 新優先→旧
                            # postal_code のみ新フィールドで保持, 他は旧互換のみ (新仕様では不要)
                            if idx_postal >= 0:
                                ch[idx_postal] = type_map.get('postal_code','')
                            elif idx_postal_old >= 0:
                                ch[idx_postal_old] = type_map.get('postal_code','')
                        loc = (raw.get('geometry') or {}).get('location') or {}
                        if idx_lat >= 0:
                            ch[idx_lat] = loc.get('lat','')
                        if idx_lng >= 0:
                            ch[idx_lng] = loc.get('lng','')
                        if idx_partial >= 0:
                            ch[idx_partial] = 'true' if raw.get('partial_match') else 'false'
                        # ---- 非 Google provider 用 ----
                        if has_nominatim and idx_nom_display >= 0:
                            # Nominatim
                            if idx_nom_place_id >= 0:
                                ch[idx_nom_place_id] = raw.get('place_id','')
                            ch[idx_nom_display] = raw.get('display_name','')
                            if idx_nom_rank >= 0:
                                ch[idx_nom_rank] = raw.get('place_rank','')
                            if idx_n_lat >= 0:
                                ch[idx_n_lat] = raw.get('lat','') or raw.get('latitude','') or ''
                            if idx_n_lon >= 0:
                                ch[idx_n_lon] = raw.get('lon','') or raw.get('longitude','') or ''
                        if has_mapbox and idx_map_place_name >= 0:
                            ch[idx_map_id] = raw.get('id','') if idx_map_id >= 0 else ''
                            ch[idx_map_place_name] = raw.get('place_name','')
                            # context から postcode 抽出
                            if idx_map_postcode >= 0:
                                pc = ''
                                ctx = raw.get('context') or []
                                if isinstance(ctx,list):
                                    for c in ctx:
                                        try:
                                            cid = c.get('id','')
                                            if cid.startswith('postcode.'):
                                                pc = c.get('text','') or ''
                                                break
                                        except Exception:
                                            pass
                                ch[idx_map_postcode] = pc
                            if idx_map_accuracy >= 0:
                                ch[idx_map_accuracy] = (raw.get('properties') or {}).get('accuracy','')
                            if idx_n_lat >= 0:
                                # geometry coordinates already used -> lon,lat vars; we stored lat/lon earlier; reuse
                                ch[idx_n_lat] = lat
                            if idx_n_lon >= 0:
                                ch[idx_n_lon] = lon
                        if has_opencage and idx_oc_formatted >= 0:
                            ch[idx_oc_formatted] = raw.get('formatted','')
                            if idx_oc_postcode >= 0:
                                comps = raw.get('components') or {}
                                if isinstance(comps, dict):
                                    ch[idx_oc_postcode] = comps.get('postcode','')
                            if idx_oc_conf >= 0:
                                ch[idx_oc_conf] = raw.get('confidence','')
                            if idx_n_lat >= 0:
                                ch[idx_n_lat] = lat
                            if idx_n_lon >= 0:
                                ch[idx_n_lon] = lon
                        if has_here and idx_here_title >= 0:
                            ch[idx_here_id] = raw.get('id','') if idx_here_id >= 0 else ''
                            ch[idx_here_title] = raw.get('title','')
                            if idx_here_postal >= 0:
                                addr = raw.get('address') or {}
                                if isinstance(addr, dict):
                                    ch[idx_here_postal] = addr.get('postalCode','')
                            if idx_n_lat >= 0:
                                ch[idx_n_lat] = lat
                            if idx_n_lon >= 0:
                                ch[idx_n_lon] = lon
                        if has_yahoo and idx_yj_name >= 0:
                            ch[idx_yj_uid] = raw.get('Id','') if idx_yj_uid >= 0 else ''
                            ch[idx_yj_name] = raw.get('Name','')
                            if idx_yj_lvl >= 0:
                                prop = raw.get('Property') or {}
                                if isinstance(prop, dict):
                                    ch[idx_yj_lvl] = prop.get('AddressMatchingLevel','')
                            if idx_n_lat >= 0:
                                ch[idx_n_lat] = lat
                            if idx_n_lon >= 0:
                                ch[idx_n_lon] = lon
                    attr_changes[fid] = ch
                for fid, err in self._fail:
                    ch = {}
                    if idx_status >= 0:
                        ch[idx_status] = 'FAIL'
                    if idx_err >= 0:
                        ch[idx_err] = err
                    attr_changes.setdefault(fid, {}).update(ch)
                if geom_changes:
                    prov.changeGeometryValues(geom_changes)
                if attr_changes:
                    prov.changeAttributeValues(attr_changes)
                if geom_changes:
                    self.layer.updateExtents()
            except Exception:
                pass
        # Callback
        if self._finished_callback:
            try:
                self._finished_callback(result, self.added, self.failed, self.processed)
            except Exception:
                pass

