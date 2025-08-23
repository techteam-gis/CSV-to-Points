# -*- coding: utf-8 -*-
"""Geocoding base interfaces (Preparation Phase)
Defines abstract interface and simple result dataclass.
No network calls here; implementation to be provided in later phase.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Protocol

@dataclass
class GeocodeResult:
    lon: Optional[float]
    lat: Optional[float]
    status: str  # OK / FAIL
    raw: dict
    precision: Optional[str] = None
    error: Optional[str] = None

class IGeocoder(Protocol):
    def geocode(self, address: str) -> GeocodeResult: ...

class DummyGeocoder:
    """Placeholder geocoder used in preparation phase.
    Always returns FAIL to avoid unintended network usage.
    """
    def geocode(self, address: str) -> GeocodeResult:
        return GeocodeResult(lon=None, lat=None, status='FAIL', raw={}, error='Not implemented (preparation phase)')
