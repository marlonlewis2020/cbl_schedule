"""Validation helpers for tenant-scoped shared roster settings."""

import math
import re

SCHEMA = """
CREATE TABLE IF NOT EXISTS roster_configurations (
    tenant_id TEXT PRIMARY KEY,
    revision INTEGER NOT NULL DEFAULT 1,
    locked INTEGER NOT NULL DEFAULT 0 CHECK (locked IN (0, 1)),
    pools_json TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS roster_employee_settings (
    tenant_id TEXT NOT NULL,
    employee_id TEXT NOT NULL,
    settings_json TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tenant_id, employee_id)
);
"""

BASE_FIELDS = frozenset({
    "flex", "reason", "preferred", "proximity", "random", "attendance",
    "days", "shiftAvailability",
})
MANAGER_FIELDS = BASE_FIELDS - {"random", "attendance"}
EMPLOYEE_FIELDS = frozenset({"flex", "reason", "preferred"})
_NUMBER = re.compile(r"(?:\d+(?:\.\d*)?|\.\d+)\Z")


def _number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        result = float(value)
    elif isinstance(value, str) and _NUMBER.fullmatch(value):
        result = float(value)
    else:
        return None
    return result if math.isfinite(result) else None


def _start_key(value):
    return format(value, ".15g")


def normalize_starts(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 16:
        raise ValueError("Each location-role pool must have 1–16 possible starts.")
    starts = []
    for item in value:
        start = _number(item)
        if start is None or start < 0 or start >= 24 or not math.isclose(start * 4, round(start * 4)):
            raise ValueError("Shift starts must be valid 15-minute times.")
        if start in starts:
            raise ValueError("Shift starts must be unique within each location-role pool.")
        starts.append(start)
    return starts


def normalize_pools(value):
    if not isinstance(value, list) or not value or len(value) > 500:
        raise ValueError("Provide the configured location-role pools.")
    pools, keys = [], set()
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("Each location-role pool must be an object.")
        location, role = item.get("location"), item.get("role")
        if not isinstance(location, str) or not location.strip() or len(location) > 240:
            raise ValueError("Each pool requires a valid location.")
        if not isinstance(role, str) or not role.strip() or len(role) > 240:
            raise ValueError("Each pool requires a valid role.")
        location, role = location.strip(), role.strip()
        key = (location.casefold(), role.casefold())
        if key in keys:
            raise ValueError("Location-role pools must be unique.")
        keys.add(key)
        pools.append({
            "location": location,
            "role": role,
            "starts": normalize_starts(item.get("starts")),
        })
    return pools


def normalize_profile(value):
    if not isinstance(value, dict):
        raise ValueError("Each employee roster profile must be an object.")
    flex = value.get("flex", "")
    reason = value.get("reason", "")
    if flex not in ("", "Yes", "No"):
        raise ValueError("Flexible must be Yes or No.")
    if not isinstance(reason, str) or len(reason) > 240:
        raise ValueError("Reason if no must be 240 characters or fewer.")

    def optional_number(field):
        raw = value.get(field)
        if raw is None or raw == "":
            return None
        number = _number(raw)
        if number is None:
            raise ValueError(f"{field} must be a number or blank.")
        return number

    preferred = optional_number("preferred")
    if preferred is not None and (preferred < 0 or preferred >= 24):
        raise ValueError("Preferred start must be a time within the day.")
    proximity = optional_number("proximity")
    if proximity is not None and proximity not in (1, 2, 3):
        raise ValueError("Proximity must be 1–3 or blank.")
    random = optional_number("random")
    if random is not None and random not in (1, 2, 3):
        raise ValueError("Random 1–3 must be 1–3 or blank.")
    attendance = optional_number("attendance")
    if attendance is not None and not 0 <= attendance <= 100:
        raise ValueError("Attendance 0–100 must be between 0 and 100 or blank.")
    days = value.get("days", [None] * 7)
    if not isinstance(days, list) or len(days) != 7 or any(
        day not in (None, 0, 1) or isinstance(day, bool) for day in days
    ):
        raise ValueError("Daily availability must contain seven 0, 1 or blank values.")
    availability = value.get("shiftAvailability", {})
    if not isinstance(availability, dict):
        raise ValueError("Shift availability must be an object.")
    normalized_availability = {}
    for start, allowed in availability.items():
        number = _number(start)
        if number is None or number < 0 or number >= 24 or allowed not in (None, 0, 1) or isinstance(allowed, bool):
            raise ValueError("Shift availability must contain valid start times and 0, 1 or blank values.")
        normalized_availability[_start_key(number)] = allowed
    return {
        "flex": flex,
        "reason": reason,
        "preferred": preferred,
        "proximity": proximity,
        "random": random,
        "attendance": attendance,
        "days": days,
        "shiftAvailability": normalized_availability,
    }


def normalize_profile_for_starts(value, starts):
    profile = normalize_profile(value)
    configured = {_start_key(start) for start in normalize_starts(starts)}
    if not set(profile["shiftAvailability"]).issubset(configured):
        raise ValueError("Shift availability includes a start that is not configured for this location and role.")
    profile["shiftAvailability"] = {
        start: profile["shiftAvailability"].get(start, 0)
        for start in sorted(configured, key=float)
    }
    return profile


def validate_edit(current, changes, starts, role):
    if not isinstance(changes, dict) or not changes:
        raise ValueError("Change at least one roster setting.")
    allowed_fields = (
        BASE_FIELDS if role == "admin"
        else MANAGER_FIELDS if role == "manager"
        else EMPLOYEE_FIELDS
    )
    updated = normalize_profile(current)
    permitted = set()
    for field, value in changes.items():
        if field in {"flex", "reason", "preferred", "proximity", "random", "attendance", "days", "shiftAvailability"}:
            permitted.add(field)
        elif field.startswith("day") and field[3:].isdigit() and 0 <= int(field[3:]) < 7:
            permitted.add("days")
        elif field.startswith("start:"):
            start = _number(field[6:])
            if start is None or start not in starts:
                raise ValueError("That shift start is not configured for this location and role.")
            permitted.add("shiftAvailability")
        else:
            raise ValueError(f"Unknown roster setting: {field}.")
        if field not in allowed_fields and not (
            field.startswith("day") and "days" in allowed_fields
        ) and not (
            field.startswith("start:") and "shiftAvailability" in allowed_fields
        ):
            raise PermissionError(f"You cannot change {field} in this view.")

        if field == "days":
            permitted_days = (0, 1, None) if role in {"admin", "manager"} else (0, 1)
            if not isinstance(value, list) or len(value) != 7 or any(
                item not in permitted_days or isinstance(item, bool) for item in value
            ):
                raise ValueError("Daily availability must contain seven valid values.")
            updated["days"] = value
        elif field.startswith("day"):
            permitted_days = (0, 1, None) if role in {"admin", "manager"} else (0, 1)
            if value not in permitted_days or isinstance(value, bool):
                raise ValueError("Daily availability must be a valid availability value.")
            updated["days"][int(field[3:])] = value
        elif field == "shiftAvailability":
            if not isinstance(value, dict):
                raise ValueError("Shift availability must be an object.")
            permitted_values = (0, 1, None) if role in {"admin", "manager"} else (0, 1)
            for start_key, allowed in value.items():
                start = _number(start_key)
                if start is None or start not in starts or allowed not in permitted_values or isinstance(allowed, bool):
                    raise ValueError("Choose a configured shift start and set a valid availability value.")
                updated["shiftAvailability"][_start_key(start)] = allowed
        elif field.startswith("start:"):
            start = float(field[6:])
            permitted_values = (0, 1, None) if role in {"admin", "manager"} else (0, 1)
            if value not in permitted_values or isinstance(value, bool):
                raise ValueError("Shift availability must be a valid availability value.")
            updated["shiftAvailability"][_start_key(start)] = value
        else:
            updated[field] = value

    normalized = normalize_profile(updated)
    if "preferred" in changes and normalized["preferred"] is not None and normalized["preferred"] not in starts:
        raise ValueError("Preferred start must be selected from this location-role pool.")
    if role in {"manager", "employee"} and normalized["flex"] == "No":
        if not normalized["reason"].strip():
            raise ValueError("Reason if no is required when Flexible is No.")
        if normalized["preferred"] is not None and (
            normalized["preferred"] not in starts
            or normalized["shiftAvailability"].get(_start_key(normalized["preferred"])) != 1
        ):
            raise ValueError("The fixed preferred start must be configured and available for this employee.")
    return normalized
