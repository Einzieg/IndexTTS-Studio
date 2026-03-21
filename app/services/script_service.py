from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from app.core.exceptions import MissingFileError, ScriptValidationError
from app.domain.models import GenerationOptions, ScriptLine
from app.infra.storage import StorageService


SRT_TIMECODE_RE = re.compile(
    r"^(?P<start>\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*"
    r"(?P<end>\d{2}:\d{2}:\d{2}[,.]\d{3})$"
)
LINE_OVERRIDE_FIELDS = set(GenerationOptions.model_fields)


class ScriptService:
    def __init__(self, storage: StorageService) -> None:
        self.storage = storage

    def load_script(self, script_path: str | Path) -> list[ScriptLine]:
        path = self.storage.resolve_path(script_path)
        if not path.exists():
            raise MissingFileError(f"Script file not found: {path}")

        if path.suffix.lower() == ".csv":
            rows = self._load_csv(path)
        elif path.suffix.lower() == ".json":
            rows = self._load_json(path)
        elif path.suffix.lower() == ".srt":
            rows = self._load_srt(path)
        else:
            raise ScriptValidationError(
                "Unsupported script format. Use `.csv`, `.json`, or `.srt`."
            )

        return self.build_lines(rows, source=path)

    def get_line(self, script_path: str | Path, line_id: str) -> ScriptLine:
        for line in self.load_script(script_path):
            if line.id == str(line_id):
                return line
        raise ScriptValidationError(f"Line `{line_id}` was not found in the script.")

    def build_lines(
        self,
        rows: list[dict[str, Any]],
        *,
        source: Path | None = None,
        auto_assign_ids: bool = False,
    ) -> list[ScriptLine]:
        lines: list[ScriptLine] = []
        for index, row in enumerate(rows, start=1):
            candidate = dict(row)
            if auto_assign_ids and not self._normalize_value(candidate.get("id")):
                candidate["id"] = str(index)
            lines.append(self._build_line(candidate))
        self._validate_unique_ids(lines, source or Path("<inline>"))
        return lines

    def save_inline_script(
        self,
        *,
        title: str | None,
        lines: list[ScriptLine],
        base_dir: Path | None = None,
    ) -> Path:
        safe_title = self.storage.sanitize_fragment(title, default="web_script")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_dir = base_dir or (self.storage.settings.paths.scripts_dir / "drafts")
        script_path = target_dir / f"{safe_title}_{timestamp}.json"
        payload = {
            "lines": [line.model_dump(mode="json", exclude_none=True) for line in lines],
        }
        self.storage.write_json(script_path, payload)
        return script_path

    def _load_csv(self, path: Path) -> list[dict[str, Any]]:
        with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            return [dict(row) for row in reader]

    def _load_json(self, path: Path) -> list[dict[str, Any]]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            items = payload.get("items") or payload.get("lines")
            if isinstance(items, list):
                return items
        raise ScriptValidationError("JSON scripts must be a list, or an object with `items`.")

    def _load_srt(self, path: Path) -> list[dict[str, Any]]:
        content = path.read_text(encoding="utf-8-sig")
        normalized = content.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            return []

        blocks = re.split(r"\n\s*\n", normalized)
        rows: list[dict[str, Any]] = []
        for position, block in enumerate(blocks, start=1):
            rows.append(self._parse_srt_block(block, position))
        return rows

    def _build_line(self, row: dict[str, Any]) -> ScriptLine:
        normalized = {key: self._normalize_value(value) for key, value in row.items()}
        override = self._extract_line_override(normalized)
        line = ScriptLine.model_validate(
            {
                "id": normalized.get("id"),
                "scene": normalized.get("scene"),
                "speaker": normalized.get("speaker"),
                "text": normalized.get("text"),
                "output_name": normalized.get("output_name"),
                "override": override,
                "start_ms": normalized.get("start_ms"),
                "end_ms": normalized.get("end_ms"),
            }
        )
        if not line.id:
            raise ScriptValidationError("Every script row must provide a non-empty `id`.")
        if not line.speaker:
            raise ScriptValidationError(
                f"Script line `{line.id}` must provide a non-empty `speaker`."
            )
        if not line.text:
            raise ScriptValidationError(
                f"Script line `{line.id}` must provide a non-empty `text`."
            )
        return line

    def _validate_unique_ids(self, lines: list[ScriptLine], path: Path) -> None:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for line in lines:
            if line.id in seen:
                duplicates.add(line.id)
            seen.add(line.id)
        if duplicates:
            duplicate_ids = ", ".join(sorted(duplicates))
            raise ScriptValidationError(
                f"Script `{path.name}` contains duplicate line ids: {duplicate_ids}"
            )

    @staticmethod
    def _normalize_value(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    def _extract_line_override(self, row: dict[str, Any]) -> dict[str, Any]:
        candidate: dict[str, Any] = {}

        if row.get("override") is not None:
            parsed_override = self._parse_override_payload(row["override"])
            candidate.update(parsed_override)

        for key in LINE_OVERRIDE_FIELDS:
            if row.get(key) is None:
                continue
            candidate[key] = self._coerce_override_value(key, row[key])

        if not candidate:
            return {}

        try:
            return GenerationOptions.model_validate(candidate).as_infer_kwargs()
        except PydanticValidationError as exc:
            raise ScriptValidationError(
                f"Invalid line override parameters: {exc.errors(include_url=False)}"
            ) from exc

    def _parse_srt_block(self, block: str, position: int) -> dict[str, Any]:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if len(lines) < 2:
            raise ScriptValidationError(
                f"SRT block #{position} is incomplete. Each block must contain an id, "
                "time range, and spoken content."
            )

        if lines[0].isdigit():
            line_id = lines[0]
            timecode_line = lines[1]
            content_lines = lines[2:]
        else:
            line_id = str(position)
            timecode_line = lines[0]
            content_lines = lines[1:]

        if not content_lines:
            raise ScriptValidationError(
                f"SRT block `{line_id}` does not contain spoken content."
            )

        match = SRT_TIMECODE_RE.match(timecode_line)
        if match is None:
            raise ScriptValidationError(
                f"SRT block `{line_id}` contains an invalid time range: {timecode_line}"
            )

        speaker, text = self._extract_srt_dialogue(line_id, content_lines)
        return {
            "id": line_id,
            "scene": "srt",
            "speaker": speaker,
            "text": text,
            "start_ms": self._parse_srt_timestamp(match.group("start")),
            "end_ms": self._parse_srt_timestamp(match.group("end")),
        }

    def _extract_srt_dialogue(self, line_id: str, content_lines: list[str]) -> tuple[str, str]:
        first_line = content_lines[0]
        remaining_lines = content_lines[1:]

        bracket_match = re.fullmatch(r"\[(.+?)\]", first_line)
        if bracket_match is not None:
            speaker = bracket_match.group(1).strip()
            text = " ".join(line.strip() for line in remaining_lines if line.strip())
            if text:
                return speaker, text

        for separator in (":", "："):
            if separator in first_line:
                speaker_part, text_part = first_line.split(separator, 1)
                speaker = speaker_part.strip()
                text_segments = [text_part.strip(), *[line.strip() for line in remaining_lines]]
                text = " ".join(segment for segment in text_segments if segment)
                if speaker and text:
                    return speaker, text

        raise ScriptValidationError(
            f"SRT block `{line_id}` must declare a speaker using `[speaker]` on the first "
            "line or `speaker: dialogue`."
        )

    @staticmethod
    def _parse_srt_timestamp(value: str) -> int:
        hours, minutes, seconds_and_ms = value.replace(",", ".").split(":", 2)
        seconds, milliseconds = seconds_and_ms.split(".", 1)
        total_ms = (
            int(hours) * 3_600_000
            + int(minutes) * 60_000
            + int(seconds) * 1_000
            + int(milliseconds)
        )
        return total_ms

    def _parse_override_payload(self, payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            return payload
        if isinstance(payload, str):
            try:
                decoded = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise ScriptValidationError(
                    "Script line `override` must be a JSON object when provided as text."
                ) from exc
            if isinstance(decoded, dict):
                return decoded
        raise ScriptValidationError("Script line `override` must be an object.")

    def _coerce_override_value(self, key: str, value: Any) -> Any:
        if key != "emo_vector" or not isinstance(value, str):
            return value

        stripped = value.strip()
        if not stripped:
            return None
        if stripped.startswith("["):
            try:
                decoded = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ScriptValidationError(
                    "Line override `emo_vector` must be a JSON array or comma-separated list."
                ) from exc
            if isinstance(decoded, list):
                return decoded
            raise ScriptValidationError(
                "Line override `emo_vector` must decode to a JSON array."
            )

        try:
            return [float(item.strip()) for item in stripped.split(",") if item.strip()]
        except ValueError as exc:
            raise ScriptValidationError(
                "Line override `emo_vector` must be a JSON array or comma-separated list."
            ) from exc
