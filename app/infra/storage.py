from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from app.core.config import AppSettings
from app.domain.models import ScriptLine


INVALID_PATH_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
WHITESPACE = re.compile(r"\s+")


class StorageService:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def resolve_path(self, value: str | Path) -> Path:
        candidate = value if isinstance(value, Path) else Path(value)
        if candidate.is_absolute():
            return candidate
        return (self.settings.paths.project_root / candidate).resolve()

    def ensure_parent(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def write_bytes(self, path: Path, payload: bytes) -> Path:
        self.ensure_parent(path)
        path.write_bytes(payload)
        return path

    def to_project_relative(self, path: Path) -> str:
        resolved = path.resolve()
        try:
            return str(resolved.relative_to(self.settings.paths.project_root))
        except ValueError:
            return str(resolved)

    def sanitize_fragment(self, value: str | None, default: str = "item") -> str:
        text = (value or "").strip()
        text = INVALID_PATH_CHARS.sub("_", text)
        text = WHITESPACE.sub("_", text)
        text = text.strip(" ._")
        return text or default

    def sanitize_filename(
        self, value: str | None, default_stem: str = "output", default_suffix: str = ".wav"
    ) -> str:
        candidate = Path(value or "")
        stem = candidate.stem if candidate.suffix else candidate.name
        suffix = candidate.suffix or default_suffix
        safe_stem = self.sanitize_fragment(stem, default=default_stem)
        return f"{safe_stem}{suffix}"

    def generate_line_output_name(self, line: ScriptLine) -> str:
        scene = self.sanitize_fragment(line.scene, default="scene")
        line_id = line.id.zfill(4) if line.id.isdigit() else self.sanitize_fragment(line.id)
        speaker = self.sanitize_fragment(line.speaker, default="speaker")
        return f"{scene}_{line_id}_{speaker}.wav"

    def generate_single_output_name(self, speaker: str) -> str:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"single_{self.sanitize_fragment(speaker, default='speaker')}_{stamp}.wav"

    def resolve_output_path(self, output_dir: Path, output_name: str | None) -> Path:
        sanitized = self.sanitize_filename(output_name)
        return self.ensure_parent(output_dir / sanitized)

    def script_output_dir(self, script_path: Path) -> Path:
        script_stem = self.sanitize_fragment(script_path.stem, default="script")
        output_dir = self.settings.paths.outputs_dir / script_stem
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def write_json(self, path: Path, payload: Any) -> None:
        self.ensure_parent(path)
        serializable = self._make_jsonable(payload)
        temp_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            temp_path.write_text(
                json.dumps(serializable, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            temp_path.replace(path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

    def read_json(self, path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))

    def _make_jsonable(self, payload: Any) -> Any:
        if isinstance(payload, BaseModel):
            return payload.model_dump(mode="json")
        if isinstance(payload, Path):
            return str(payload)
        if isinstance(payload, list):
            return [self._make_jsonable(item) for item in payload]
        if isinstance(payload, dict):
            return {str(key): self._make_jsonable(value) for key, value in payload.items()}
        return payload
