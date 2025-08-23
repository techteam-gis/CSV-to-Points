# -*- coding: utf-8 -*-
"""Field detection (Phase 2 skeleton)
検出対象:
- 緯度 (lat) 候補
- 経度 (lon) 候補
- 住所 (address) 候補
スコアリングで最上位をプリセット決定。
"""
from __future__ import annotations
from typing import List, Dict
from .settings_store import SettingsStore
import re

# デフォルト(グローバル) キーワード: 常に利用。ユーザ入力欄には表示しない。
LAT_KEYWORDS = ["lat", "latitude", "y", "fy"]
LON_KEYWORDS = ["lon", "lng", "long", "longitude", "x", "fx"]
ADDR_KEYWORDS = ["address", "addr"]

# 追加の初期 (ローカライズ) キーワード: 設定未保存時はユーザ追加キーワードとして自動投入。
INITIAL_CUSTOM_KEYWORDS = {
    'lat': ["緯度"],
    'lon': ["経度"],
    'addr': ["住所", "所在地"],
}

# 典型的な XY 命名 (fX/fY, X/Y, lon/lat) の補助ヒューリスティック
PAIR_X_NAMES = {"x", "fx", "lon", "lng", "経度"}
PAIR_Y_NAMES = {"y", "fy", "lat", "緯度"}

NORMALIZE_RE = re.compile(r"[\s_]+")


def normalize(name: str) -> str:
    n = name.strip().lower()
    n = NORMALIZE_RE.sub("", n)
    return n


def _score(name: str, keywords: List[str]) -> int:
    norm = normalize(name)
    # 完全一致
    for kw in keywords:
        if norm == kw:
            return 100
    # 部分一致
    for kw in keywords:
        if kw in norm:
            return 70
    # 先頭/接尾 (軽め)
    for kw in keywords:
        if norm.startswith(kw) or norm.endswith(kw):
            return 60
    return 0


def _merged_keywords() -> Dict[str, List[str]]:
    """デフォルト + (ユーザ追加 or 初期日本語) をマージした dict を返す。"""
    store = SettingsStore()
    custom = store.get_all_custom_keywords()  # may be empty lists
    # 初期日本語を適用 (ユーザが一度でも保存し該当カテゴリに何か入れればその内容のみを尊重)
    eff_custom = {
        'lat': custom.get('lat') or INITIAL_CUSTOM_KEYWORDS['lat'],
        'lon': custom.get('lon') or INITIAL_CUSTOM_KEYWORDS['lon'],
        'addr': custom.get('addr') or INITIAL_CUSTOM_KEYWORDS['addr'],
    }
    def merge(base: List[str], extra: List[str]) -> List[str]:
        seen = set()
        merged: List[str] = []
        for src in (base, extra):
            for kw in src:
                k_norm = normalize(kw)
                if not k_norm or k_norm in seen:
                    continue
                seen.add(k_norm)
                merged.append(kw)
        return merged
    return {
        'lat': merge(LAT_KEYWORDS, eff_custom['lat']),
        'lon': merge(LON_KEYWORDS, eff_custom['lon']),
        'addr': merge(ADDR_KEYWORDS, eff_custom['addr']),
    }


def detect(header: List[str]) -> Dict[str, object]:
    kw = _merged_keywords()
    lat_candidates = []  # (field, score)
    lon_candidates = []
    addr_candidates = []

    for f in header:
        s_lat = _score(f, kw['lat'])
        s_lon = _score(f, kw['lon'])
        s_addr = _score(f, kw['addr'])
        if s_lat:
            lat_candidates.append((f, s_lat))
        if s_lon:
            lon_candidates.append((f, s_lon))
        if s_addr:
            addr_candidates.append((f, s_addr))

    # fX / fY の特例: どちらも存在し明確な候補が無いとき補完
    norm_set = {normalize(f): f for f in header}
    if not lat_candidates or not lon_candidates:
        if any(k in norm_set for k in PAIR_X_NAMES) and any(k in norm_set for k in PAIR_Y_NAMES):
            # 既存スコアが弱ければ追加スコア 50
            for k in PAIR_Y_NAMES:
                if k in norm_set and all(normalize(c[0]) != k for c in lat_candidates):
                    lat_candidates.append((norm_set[k], 50))
            for k in PAIR_X_NAMES:
                if k in norm_set and all(normalize(c[0]) != k for c in lon_candidates):
                    lon_candidates.append((norm_set[k], 50))

    # ソート
    lat_candidates.sort(key=lambda x: x[1], reverse=True)
    lon_candidates.sort(key=lambda x: x[1], reverse=True)
    addr_candidates.sort(key=lambda x: x[1], reverse=True)

    chosen_lat = lat_candidates[0][0] if lat_candidates else None
    chosen_lon = lon_candidates[0][0] if lon_candidates else None
    chosen_addr = addr_candidates[0][0] if addr_candidates else None

    return {
        "lat_candidates": [f for f, _ in lat_candidates],
        "lon_candidates": [f for f, _ in lon_candidates],
        "address_candidates": [f for f, _ in addr_candidates],
        "chosen_lat": chosen_lat,
        "chosen_lon": chosen_lon,
        "chosen_address": chosen_addr,
    }


class FieldDetector:
    def detect(self, header: List[str]) -> Dict[str, object]:
        return detect(header)


if __name__ == "__main__":  # pragma: no cover
    sample = ["fid", "住所", "fX", "fY", "備考"]
    print(detect(sample))
