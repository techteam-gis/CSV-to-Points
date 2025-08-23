# -*- coding: utf-8 -*-
"""CSV 基本解析 (Phase 1)
- エンコーディング推定 (BOM -> chardet -> fallback)
- 区切り推定 (csv.Sniffer)
- ヘッダ抽出
この段階では外部依存を避け、chardet が無ければスキップ。
"""
from __future__ import annotations
import os
import csv
import codecs
from typing import Dict, List, Optional

try:
    import chardet  # type: ignore
except ImportError:  # pragma: no cover
    chardet = None  # fallback later

BOM_TABLE = [
    (codecs.BOM_UTF8, 'utf-8-sig'),
    (codecs.BOM_UTF16_LE, 'utf-16-le'),
    (codecs.BOM_UTF16_BE, 'utf-16-be'),
]

class CsvBasicMeta(dict):
    """Simple dict subclass for clarity."""
    pass

class CsvInspector:
    SAMPLE_SIZE = 65536

    def detect_encoding(self, path: str) -> str:
        with open(path, 'rb') as f:
            raw = f.read(self.SAMPLE_SIZE)
        for bom, name in BOM_TABLE:
            if raw.startswith(bom):
                return name
        if chardet:
            res = chardet.detect(raw)
            enc = res.get('encoding') or ''
            conf = res.get('confidence') or 0
            if enc and conf >= 0.5:
                return enc
        # heuristic fallback tries
        for cand in ('utf-8', 'cp932'):
            try:
                raw.decode(cand)
                return cand
            except Exception:
                continue
        return 'utf-8'

    def sniff(self, text: str) -> str:
        try:
            dialect = csv.Sniffer().sniff(text)
            return dialect.delimiter
        except Exception:
            return ','

    def inspect(self, path: str) -> CsvBasicMeta:
        enc = self.detect_encoding(path)
        with open(path, 'r', encoding=enc, errors='replace') as f:
            sample = f.read(self.SAMPLE_SIZE)
        delimiter = self.sniff(sample)
        # Re-read first line for header
        with open(path, 'r', encoding=enc, errors='replace', newline='') as f:
            reader = csv.reader(f, delimiter=delimiter)
            header: List[str] = next(reader, [])
        meta = CsvBasicMeta(encoding=enc, delimiter=delimiter, header=header[:50])
        return meta

# Simple manual test when run standalone
if __name__ == '__main__':  # pragma: no cover
    import sys, json
    insp = CsvInspector()
    for p in sys.argv[1:]:
        print(p)
        print(json.dumps(insp.inspect(p), ensure_ascii=False, indent=2))
