# -*- coding: utf-8 -*-
"""Coordinate parsing utilities (Phase A)
DMS / 度分秒 / 方位記号 / 日本語単位混在の正規化を行い 10 進度へ変換。
"""
from __future__ import annotations
import re
from typing import Optional

# 正規表現: 度 分 秒 (任意) + 末尾方位 (N/S/E/W) あるいは東西南北の英字
DMS_RE = re.compile(r"""^\s*
    (?P<deg>[-+]?\d+(?:\.\d+)?)
    (?:[°º度\s]\s*(?P<min>\d+(?:\.\d+)?))?
    (?:['’′分]\s*(?P<sec>\d+(?:\.\d+)?))?
    (?:["”″秒])?
    \s*(?P<hem>[NnSsEeWw])?\s*$
""", re.VERBOSE)

HEM_SIGNS = {
    'N': 1, 'n': 1,
    'E': 1, 'e': 1,
    'S': -1, 's': -1,
    'W': -1, 'w': -1,
}

def parse_dms(text: str) -> float:
    m = DMS_RE.match(text)
    if not m:
        # 単純な float として試行
        try:
            return float(text.strip())
        except Exception as e:
            raise ValueError(f"Cannot parse coordinate: {text}") from e
    deg = float(m.group('deg'))
    minutes = m.group('min')
    seconds = m.group('sec')
    hem = m.group('hem')
    val = abs(deg)
    if minutes is not None:
        val += float(minutes) / 60.0
    if seconds is not None:
        val += float(seconds) / 3600.0
    # 符号: 度に既に符号があればそれを基本とし、方位記号で上書き
    sign = 1 if deg >= 0 else -1
    if hem:
        sign = HEM_SIGNS.get(hem, sign)
    return sign * val


def parse_lat(text: str) -> float:
    v = parse_dms(text)
    if not -90 <= v <= 90:
        raise ValueError("Latitude out of range")
    return v


def parse_lon(text: str) -> float:
    v = parse_dms(text)
    if not -180 <= v <= 180:
        raise ValueError("Longitude out of range")
    return v

if __name__ == '__main__':  # pragma: no cover
    samples = [
        "35°39'29.1\"N", "139°42'30\"E", "35.658083", "139.708333", "35度39分29.1秒N"
    ]
    for s in samples:
        try:
            print(s, '->', parse_dms(s))
        except Exception as e:
            print('ERR', s, e)
