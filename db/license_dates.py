"""Temporal contract v1. Keep source precision; quarantine invalid observed dates."""
from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Any

DATE_RULE_VERSION = "license-dates-v1"


def parse_date(value: Any, *, as_of: date | None = None, meaning: str = "observed") -> dict:
    as_of = as_of or datetime.now(UTC).date()
    raw = "" if value is None else str(value).strip()
    result = {"raw": value, "value": None, "precision": None, "reason": None}
    if not raw:
        return result
    iso = re.fullmatch(r"(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?", raw)
    dmy = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", raw)
    if iso:
        y, m, d = int(iso[1]), int(iso[2] or 1), int(iso[3] or 1)
        precision = "day" if iso[3] else "month" if iso[2] else "year"
    elif dmy:
        d, m, y = map(int, dmy.groups())
        precision = "day"
    else:
        return {**result, "reason": "unsupported_or_ambiguous_format"}
    if y < 1900 or y > 2100:
        return {**result, "reason": "year_out_of_range"}
    try:
        earliest = date(y, m, d)
    except ValueError:
        return {**result, "reason": "invalid_calendar_date"}
    if meaning != "planned" and earliest > as_of:
        return {**result, "reason": "future_observed_date"}
    canonical = f"{y:04d}" + (f"-{m:02d}" if precision != "year" else "") + (f"-{d:02d}" if precision == "day" else "")
    return {**result, "value": canonical, "precision": precision}


def license_temporal(row: dict, *, as_of: date | None = None) -> dict:
    original = row.get("raw_json") or {}
    if isinstance(original, dict) and original.get("temporal"):
        row = {**row, **{key: field["raw"] for key, field in original["temporal"].get("fields", {}).items()}}
    fields = {key: parse_date(row.get(key), as_of=as_of) for key in ("fecha_concesion", "fecha_alta", "anio_dataset")}
    # An explicit but invalid grant must never become activity dated by registration.
    primary = fields["fecha_concesion"] if row.get("fecha_concesion") else fields["fecha_alta"]
    year_value = primary["value"] or (fields["anio_dataset"]["value"] if not primary["reason"] else None)
    quarantine = [{"field": key, **value} for key, value in fields.items() if value["reason"]]
    return {"ruleVersion": DATE_RULE_VERSION, "fields": fields, "year": int(year_value[:4]) if year_value else None,
            "month": primary["value"][:7] if primary["value"] and primary["precision"] != "year" else None,
            "quarantine": quarantine}
