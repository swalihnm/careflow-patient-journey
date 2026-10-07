"""Generic, dotted-path field redaction applied to FHIR JSON before it leaves specmcp."""

import copy
from typing import Any

REDACTED = "***MASKED***"


def apply_mask(resource: dict[str, Any], hide_fields: list[str]) -> dict[str, Any]:
    masked = copy.deepcopy(resource)
    for field_path in hide_fields:
        _redact(masked, field_path.split("."))
    return masked


def _redact(obj: Any, path: list[str]) -> None:
    if not path or obj is None:
        return
    key = path[0]
    if isinstance(obj, list):
        for item in obj:
            _redact(item, path)
        return
    if not isinstance(obj, dict):
        return
    if key not in obj:
        return
    if len(path) == 1:
        obj[key] = REDACTED
        return
    _redact(obj[key], path[1:])
