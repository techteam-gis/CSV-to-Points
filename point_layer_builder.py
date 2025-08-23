# -*- coding: utf-8 -*-
"""Point layer builder (Phase B minimal)
緯度経度フィールドを使ってメモリレイヤへポイントをロード。
"""
from __future__ import annotations
from qgis.core import QgsFields, QgsField, QgsVectorLayer, QgsFeature, QgsPointXY, QgsGeometry
from qgis.PyQt.QtCore import QVariant, QMetaType
import csv
from .coordinate_parser import parse_lat, parse_lon

class PointLayerBuilder:
    def build_memory_layer(self, csv_path: str, encoding: str, delimiter: str, header: list, lat_field: str, lon_field: str, layer_name: str = 'CSV Points') -> QgsVectorLayer:
        layer = QgsVectorLayer("Point?crs=EPSG:4326", layer_name, "memory")
        pr = layer.dataProvider()
        # 既存属性: CSV の全列
        fields = QgsFields()
        for col in header:
            fields.append(QgsField(col, QMetaType.QString))
        # 補助列 (geocode 予定枠)
        fields.append(QgsField('_parse_error', QMetaType.QString))
        pr.addAttributes(fields)
        layer.updateFields()

        idx_lat = header.index(lat_field) if lat_field in header else -1
        idx_lon = header.index(lon_field) if lon_field in header else -1
        if idx_lat < 0 or idx_lon < 0:
            raise ValueError('Latitude/Longitude field not found in header')

        feats = []
        with open(csv_path, 'r', encoding=encoding, errors='replace', newline='') as f:
            reader = csv.reader(f, delimiter=delimiter)
            # skip header
            next(reader, None)
            for row in reader:
                if not row:
                    continue
                # 行長が短い場合パディング
                if len(row) < len(header):
                    row = row + [''] * (len(header) - len(row))
                lat_raw = row[idx_lat]
                lon_raw = row[idx_lon]
                parse_error = ''
                try:
                    lat = parse_lat(lat_raw)
                    lon = parse_lon(lon_raw)
                except Exception as e:
                    lat = None
                    lon = None
                    parse_error = str(e)
                feat = QgsFeature(layer.fields())
                # 属性設定
                attrs = row[:len(header)] + [parse_error]
                feat.setAttributes(attrs)
                if lat is not None and lon is not None:
                    feat.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(lon, lat)))
                feats.append(feat)
        pr.addFeatures(feats)
        layer.updateExtents()
        return layer
