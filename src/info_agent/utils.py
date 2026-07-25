from __future__ import annotations

from typing import Any


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() not in {"false", "no", "0", "off"}
    return bool(value)
