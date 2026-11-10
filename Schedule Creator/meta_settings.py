"""Validation helpers for tenant-scoped META operating settings."""

import math

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta_configurations (
    tenant_id TEXT PRIMARY KEY,
    revision INTEGER NOT NULL DEFAULT 1,
    locked INTEGER NOT NULL DEFAULT 0 CHECK (locked IN (0, 1)),
    locations_json TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def _number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        result = float(value)
    elif isinstance(value, str) and value.strip():
        try:
            result = float(value)
        except ValueError:
            return None
    else:
        return None
    return result if math.isfinite(result) else None


def normalize_locations(value):
    if not isinstance(value, list) or not value or len(value) > 500:
        raise ValueError("Provide the configured META locations.")
    locations, names = [], set()
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("Each META location must be an object.")
        name = item.get("name")
        if not isinstance(name, str) or not name.strip() or len(name) > 240:
            raise ValueError("Each META location requires a valid name.")
        name = name.strip()
        if name.casefold() in names:
            raise ValueError("META location names must be unique.")
        names.add(name.casefold())
        intensity, opened = item.get("intensity"), item.get("open")
        if not isinstance(intensity, list) or len(intensity) != 7:
            raise ValueError(f"{name} must have seven daily intensity values.")
        normalized_intensity = []
        for value in intensity:
            if value is None or value == "":
                normalized_intensity.append(None)
                continue
            number = _number(value)
            if number is None or not 0 <= number <= 1:
                raise ValueError("Daily intensities must be percentages from 0 to 100 or blank.")
            normalized_intensity.append(number)
        if not isinstance(opened, list) or len(opened) != 7 or any(
            day not in (None, 0, 1) or isinstance(day, bool) for day in opened
        ):
            raise ValueError(f"{name} must have seven valid operating-day values.")
        locations.append({
            "name": name,
            "intensity": normalized_intensity,
            "open": opened,
        })
    return locations


def apply_changes(location, changes):
    if not isinstance(changes, list) or not changes or len(changes) > 14:
        raise ValueError("Change at least one META operating setting.")
    updated = {
        "name": location["name"],
        "intensity": list(location["intensity"]),
        "open": list(location["open"]),
    }
    seen = set()
    for change in changes:
        if not isinstance(change, dict):
            raise ValueError("Each META change must be an object.")
        field, day, value = change.get("field"), change.get("day"), change.get("value")
        if field not in {"open", "intensity"}:
            raise ValueError("META changes may only update operating days or intensity.")
        if not isinstance(day, int) or isinstance(day, bool) or not 0 <= day < 7:
            raise ValueError("Choose a valid day of the week.")
        key = (field, day)
        if key in seen:
            raise ValueError("Do not submit the same META setting more than once.")
        seen.add(key)
        if field == "open":
            if value not in (0, 1) or isinstance(value, bool):
                raise ValueError("Operating-day values must be open (1) or closed (0).")
            updated["open"][day] = value
        elif value is None or value == "":
            updated["intensity"][day] = None
        else:
            number = _number(value)
            if number is None or not 0 <= number <= 1:
                raise ValueError("Daily intensity must be a percentage from 0 to 100 or blank.")
            updated["intensity"][day] = number
    return updated
