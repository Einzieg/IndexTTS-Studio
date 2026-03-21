from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Mapping

from app.core.config import AppSettings
from app.core.exceptions import OutputNameCollisionError, ValidationError
from app.domain.models import ScriptLine, SpeakerProfile, SynthesisResult
from app.infra.indextts_adapter import TTSAdapter
from app.infra.storage import StorageService
from app.services.project_service import ProjectService
from app.services.speaker_service import SpeakerService


class TTSService:
    def __init__(
        self,
        settings: AppSettings,
        storage: StorageService,
        speaker_service: SpeakerService,
        project_service: ProjectService,
        adapter: TTSAdapter,
    ) -> None:
        self.settings = settings
        self.storage = storage
        self.speaker_service = speaker_service
        self.project_service = project_service
        self.adapter = adapter
        self._synthesis_lock = threading.Lock()

    def synthesize_single(
        self,
        *,
        project_id: str | None = None,
        episode_id: str | None = None,
        speaker: str,
        text: str,
        output_name: str | None = None,
        override: Mapping[str, Any] | None = None,
        force: bool = False,
    ) -> SynthesisResult:
        output_root = (
            self.project_service.episode_output_dir(project_id, episode_id)
            if project_id
            else self.settings.paths.outputs_dir
        )
        resolved_output = self.storage.resolve_output_path(
            output_root,
            output_name or self.storage.generate_single_output_name(speaker),
        )
        return self._synthesize(
            project_id=project_id,
            speaker_name=speaker,
            text=text,
            output_path=resolved_output,
            line_id=None,
            override=override,
            skip_existing=True,
            force=force,
        )

    def synthesize_script_line(
        self,
        line: ScriptLine,
        output_dir: Path,
        *,
        project_id: str | None = None,
        override: Mapping[str, Any] | None = None,
        skip_existing: bool = True,
        force: bool = False,
    ) -> SynthesisResult:
        effective_override = dict(line.override)
        effective_override.update(override or {})
        return self._synthesize(
            project_id=project_id,
            speaker_name=line.speaker,
            text=line.text,
            output_path=self.resolve_line_output_path(line, output_dir),
            line_id=line.id,
            override=effective_override,
            skip_existing=skip_existing,
            force=force,
        )

    def resolve_line_output_path(self, line: ScriptLine, output_dir: Path) -> Path:
        output_name = line.output_name or self.storage.generate_line_output_name(line)
        return self.storage.resolve_output_path(output_dir, output_name)

    def merge_generation_options(
        self,
        speaker_profile: SpeakerProfile,
        override: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        merged = dict(self.settings.generation.as_dict())
        merged.update(speaker_profile.options.as_infer_kwargs())

        for key, value in (override or {}).items():
            if value is None:
                continue
            if key == "emo_audio":
                merged.pop("emo_vector", None)
                merged[key] = self.storage.resolve_path(str(value))
            elif key == "emo_vector":
                merged.pop("emo_audio", None)
                merged[key] = value
            else:
                merged[key] = value
        return merged

    def _synthesize(
        self,
        *,
        project_id: str | None,
        speaker_name: str,
        text: str,
        output_path: Path,
        line_id: str | None,
        override: Mapping[str, Any] | None,
        skip_existing: bool,
        force: bool,
    ) -> SynthesisResult:
        clean_text = text.strip()
        if not clean_text:
            raise ValidationError("Text must not be empty.")

        if output_path.exists() and not force:
            if skip_existing:
                return SynthesisResult(
                    success=True,
                    status="skipped",
                    speaker=speaker_name,
                    text=clean_text,
                    output_path=output_path,
                    line_id=line_id,
                )
            raise OutputNameCollisionError(
                f"Output already exists: {output_path}. Use `force=true` to overwrite it."
            )

        speaker = self.speaker_service.get_speaker(speaker_name, project_id=project_id)
        merged_options = self.merge_generation_options(speaker, override=override)
        with self._synthesis_lock:
            adapter_result = self.adapter.synthesize(
                ref_audio=speaker.ref_audio,
                text=clean_text,
                output_path=output_path,
                options=merged_options,
            )
        return SynthesisResult(
            success=True,
            status="done",
            speaker=speaker_name,
            text=clean_text,
            output_path=output_path,
            duration_ms=int(adapter_result.get("duration_ms", 0)),
            line_id=line_id,
            used_options=self._serialize_options(merged_options),
        )

    def _serialize_options(self, options: Mapping[str, Any]) -> dict[str, Any]:
        serialized: dict[str, Any] = {}
        for key, value in options.items():
            if isinstance(value, Path):
                serialized[key] = str(value)
            else:
                serialized[key] = value
        return serialized
