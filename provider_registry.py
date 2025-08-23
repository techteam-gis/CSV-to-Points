"""Central provider registry: internal IDs and display names.
Modify here to reflect across UI (settings dialog, dock widget, etc.)."""
from __future__ import annotations

# Ordered list of (internal_id, display_name)
PROVIDERS = [
    ("nominatim", "Nominatim"),
    ("google", "Google"),
    ("mapbox", "Mapbox"),
    ("opencage", "OpenCage"),
    ("yahoojp", "Yahoo!ジオコーダAPI"),
    # ("here", "HERE")  # 追加再開する場合はコメント解除
]


# Fast lookup dict
_ID_TO_DISPLAY = {pid: disp for pid, disp in PROVIDERS}


def get_display_name(provider_id: str | None) -> str:
    if not provider_id:
        return ""
    return _ID_TO_DISPLAY.get(provider_id, provider_id or "")


def iter_providers():
    """Yield (internal_id, display_name) preserving order."""
    yield from PROVIDERS
