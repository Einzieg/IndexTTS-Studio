from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel


def api_response(*, success: bool, message: str, data: Any | None = None) -> dict[str, Any]:
    return {
        "success": success,
        "message": message,
        "data": _serialize(data),
    }


def _serialize(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    return value
