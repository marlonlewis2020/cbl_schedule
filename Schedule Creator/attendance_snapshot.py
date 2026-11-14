"""Self-contained, offline HTML presentation of saved attendance evidence."""

import base64
import hashlib
import json
import re
from pathlib import Path


def render(payload: dict) -> str:
    attendance = payload["attendance"]
    fields = (
        "runId", "employeeId", "name", "location", "role", "date", "shiftStart",
        "shiftEnd", "status", "source", "reason", "clockIn", "clockOut",
        "workedMinutes", "earlyMinutes", "overtimeMinutes",
    )
    data = {
        "version": 1,
        "businessName": payload.get("businessName", "Workforce"),
        "logoDataUrl": payload.get("logoDataUrl", ""),
        "supportingImages": payload.get("supportingImages", []),
        "reportTheme": payload.get("reportTheme", "light")
        if payload.get("reportTheme") in {"light", "dark"} else "light",
        "primaryColor": payload.get("primaryColor", "#176bd5"),
        "accentColor": payload.get("accentColor", "#079998"),
        "cutoff": payload["cutoff"],
        "generatedAt": payload["generatedAt"],
        "refreshError": payload.get("refreshError", ""),
        "lastSyncedAt": attendance.get("lastSyncedAt"),
        "shiftSource": attendance.get("shiftSource", {}).get("selected", "Unavailable"),
        "tolerance": attendance.get("settings", {}).get("latenessToleranceMinutes"),
        "shifts": [{key: row.get(key) for key in fields} for row in attendance["shifts"]],
    }
    # Data remains inert even if an employee name contains HTML/script delimiters.
    encoded = json.dumps(data, ensure_ascii=True, allow_nan=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    template = Path(__file__).with_name("attendance_snapshot.html").read_text(encoding="utf-8")
    hashes = {}
    for kind in ("style", "script"):
        blocks = re.findall(rf"<{kind}>(.*?)</{kind}>", template, re.DOTALL)
        hashes[kind] = " ".join(
            "'sha256-" + base64.b64encode(hashlib.sha256(block.encode()).digest()).decode() + "'"
            for block in blocks
        )
    policy = (
        "default-src 'none'; script-src " + hashes["script"] +
        "; style-src " + hashes["style"] +
        "; img-src data:; base-uri 'none'; form-action 'none'; object-src 'none'"
    )
    return template.replace("__SNAPSHOT_CSP__", policy).replace("__SNAPSHOT_DATA__", encoded)
