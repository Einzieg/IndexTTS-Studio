from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import ValidationError as PydanticValidationError

from app.core.config import AppSettings
from app.core.exceptions import MissingFileError, SpeakerNotFoundError, ValidationError
from app.domain.models import GenerationOptions, SpeakerProfile
from app.domain.schemas import SpeakerConfigSchema
from app.infra.storage import StorageService
from app.services.project_service import ProjectPaths, ProjectService


ALLOWED_REF_AUDIO_SUFFIXES = {".wav", ".mp3"}


class SpeakerService:
    def __init__(
        self,
        settings: AppSettings,
        storage: StorageService,
        project_service: ProjectService,
    ) -> None:
        self.settings = settings
        self.storage = storage
        self.project_service = project_service
        self._cache: dict[str, dict[str, SpeakerProfile]] = {}

    def load_speakers(
        self,
        force_reload: bool = False,
        *,
        project_id: str | None = None,
    ) -> dict[str, SpeakerProfile]:
        cache_key = self._cache_key(project_id)
        if cache_key in self._cache and not force_reload:
            return self._cache[cache_key]

        raw_data = self._read_raw_configs(project_id=project_id)
        speakers: dict[str, SpeakerProfile] = {}
        for speaker_name, config in raw_data.items():
            schema = self._validate_schema(speaker_name, config)
            ref_audio = self.storage.resolve_path(schema.ref_audio)
            if not ref_audio.exists():
                raise MissingFileError(
                    f"Reference audio for speaker `{speaker_name}` was not found: {ref_audio}"
                )

            emo_audio: Path | None = None
            if schema.emo_audio:
                emo_audio = self.storage.resolve_path(schema.emo_audio)
                if not emo_audio.exists():
                    raise MissingFileError(
                        f"Emotion audio for speaker `{speaker_name}` was not found: {emo_audio}"
                    )

            options = GenerationOptions(
                emo_audio=emo_audio,
                emo_alpha=schema.emo_alpha,
                emo_vector=schema.emo_vector,
                emo_text=schema.emo_text,
                use_emo_text=schema.use_emo_text,
                text_split_method=schema.text_split_method,
                interval_silence=schema.interval_silence,
                temperature=schema.temperature,
                top_p=schema.top_p,
                top_k=schema.top_k,
                max_mel_tokens=schema.max_mel_tokens,
                repetition_penalty=schema.repetition_penalty,
                length_penalty=schema.length_penalty,
                num_beams=schema.num_beams,
                use_random=schema.use_random,
                max_text_tokens_per_segment=schema.max_text_tokens_per_segment,
            )

            speakers[speaker_name] = SpeakerProfile(
                name=speaker_name,
                ref_audio=ref_audio,
                options=options,
            )

        self._cache[cache_key] = speakers
        return speakers

    def list_speakers(self, *, project_id: str | None = None) -> list[str]:
        return sorted(self.load_speakers(project_id=project_id).keys())

    def list_speaker_profiles(self, *, project_id: str | None = None) -> list[dict[str, Any]]:
        profiles = []
        for speaker in self.load_speakers(project_id=project_id).values():
            profiles.append(self._serialize_profile(speaker))
        profiles.sort(key=lambda item: item["name"])
        return profiles

    def get_speaker(self, speaker_name: str, *, project_id: str | None = None) -> SpeakerProfile:
        speakers = self.load_speakers(project_id=project_id)
        try:
            return speakers[speaker_name]
        except KeyError as exc:
            raise SpeakerNotFoundError(f"Speaker `{speaker_name}` does not exist.") from exc

    def get_speaker_profile(
        self,
        speaker_name: str,
        *,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        return self._serialize_profile(self.get_speaker(speaker_name, project_id=project_id))

    def upsert_speaker(
        self,
        *,
        project_id: str | None = None,
        name: str,
        fields: dict[str, Any],
        ref_audio_bytes: bytes | None = None,
        ref_audio_filename: str | None = None,
    ) -> dict[str, Any]:
        speaker_name = name.strip()
        if not speaker_name:
            raise ValidationError("Speaker name must not be empty.")

        raw_configs = self._read_raw_configs(project_id=project_id)
        existing = dict(raw_configs.get(speaker_name, {}))
        updated = dict(existing)

        for key, value in fields.items():
            if key == "ref_audio":
                continue
            if value is None:
                updated.pop(key, None)
            else:
                updated[key] = value

        if ref_audio_bytes is not None:
            saved_ref_audio = self._save_reference_audio(
                project_id=project_id,
                speaker_name=speaker_name,
                payload=ref_audio_bytes,
                filename=ref_audio_filename,
            )
            updated["ref_audio"] = self.storage.to_project_relative(saved_ref_audio)
        elif existing.get("ref_audio"):
            updated["ref_audio"] = existing["ref_audio"]

        if not updated.get("ref_audio"):
            raise ValidationError("Reference audio is required when creating a speaker.")

        schema = self._validate_schema(speaker_name, updated)
        raw_configs[speaker_name] = schema.model_dump(exclude_none=True)
        self._write_raw_configs(raw_configs, project_id=project_id)
        self._clear_cache(project_id)
        return self.get_speaker_profile(speaker_name, project_id=project_id)

    def delete_speaker(self, speaker_name: str, *, project_id: str | None = None) -> dict[str, Any]:
        normalized_name = speaker_name.strip()
        if not normalized_name:
            raise ValidationError("Speaker name must not be empty.")

        raw_configs = self._read_raw_configs(project_id=project_id)
        if normalized_name not in raw_configs:
            raise SpeakerNotFoundError(f"Speaker `{normalized_name}` does not exist.")

        raw_configs.pop(normalized_name)
        self._write_raw_configs(raw_configs, project_id=project_id)
        self._clear_cache(project_id)
        self._remove_managed_reference_dir(normalized_name, project_id=project_id)
        return {"name": normalized_name}

    def copy_speakers(
        self,
        *,
        source_project_id: str,
        target_project_id: str,
        speaker_names: list[str] | None = None,
        overwrite: bool = False,
    ) -> list[dict[str, Any]]:
        source_project = self.project_service.get_project(source_project_id)
        target_project = self.project_service.get_project(target_project_id)
        if source_project.id == target_project.id:
            raise ValidationError("Source and target projects must be different.")

        source_configs = self._read_raw_configs(project_id=source_project.id)
        target_configs = self._read_raw_configs(project_id=target_project.id)
        selected_names = [name.strip() for name in speaker_names or [] if name.strip()]
        if not selected_names:
            selected_names = sorted(source_configs)

        if not selected_names:
            raise ValidationError("Source project has no speakers to copy.")

        missing_names = [name for name in selected_names if name not in source_configs]
        if missing_names:
            raise SpeakerNotFoundError(
                f"Speaker `{missing_names[0]}` does not exist in source project."
            )

        conflicts = [name for name in selected_names if name in target_configs]
        if conflicts and not overwrite:
            raise ValidationError(
                f"Speaker `{conflicts[0]}` already exists in target project."
            )

        target_paths = self.project_service.project_paths(target_project.id)
        plans: list[dict[str, Any]] = []
        managed_dirs: set[str] = set()
        for speaker_name in selected_names:
            source_schema = self._validate_schema(speaker_name, source_configs[speaker_name])
            safe_speaker = self.storage.sanitize_fragment(speaker_name, default="speaker")
            if safe_speaker in managed_dirs:
                raise ValidationError(
                    f"Multiple speaker names resolve to the same managed directory: `{safe_speaker}`."
                )
            managed_dirs.add(safe_speaker)

            ref_source_path = self._resolve_referenced_audio(source_schema.ref_audio)
            ref_safe_name = self.storage.sanitize_filename(
                ref_source_path.name,
                default_stem=f"{safe_speaker}_ref",
                default_suffix=ref_source_path.suffix or ".wav",
            )
            ref_final_path = target_paths.refs_dir / safe_speaker / ref_safe_name

            copied_config = source_schema.model_dump(exclude_none=True)
            copied_config["ref_audio"] = self.storage.to_project_relative(ref_final_path)

            audio_copies = [
                {
                    "source_path": ref_source_path,
                    "safe_name": ref_safe_name,
                    "final_path": ref_final_path,
                }
            ]
            if source_schema.emo_audio:
                emo_source_path = self._resolve_referenced_audio(source_schema.emo_audio)
                emo_safe_name = self.storage.sanitize_filename(
                    emo_source_path.name,
                    default_stem=f"{safe_speaker}_emo",
                    default_suffix=emo_source_path.suffix or ".wav",
                )
                emo_final_path = target_paths.refs_dir / safe_speaker / emo_safe_name
                copied_config["emo_audio"] = self.storage.to_project_relative(emo_final_path)
                audio_copies.append(
                    {
                        "source_path": emo_source_path,
                        "safe_name": emo_safe_name,
                        "final_path": emo_final_path,
                    }
                )

            plans.append(
                {
                    "speaker_name": speaker_name,
                    "safe_speaker": safe_speaker,
                    "managed_dir": target_paths.refs_dir / safe_speaker,
                    "copied_config": copied_config,
                    "audio_copies": audio_copies,
                }
            )

        target_config_path = target_paths.speakers_file
        original_target_config = (
            target_config_path.read_text(encoding="utf-8")
            if target_config_path.exists()
            else None
        )
        staging_root = target_paths.refs_dir / f".copy-staging-{uuid4().hex}"
        backup_root = target_paths.refs_dir / f".copy-backup-{uuid4().hex}"
        moved_dirs: list[tuple[Path, Path]] = []
        installed_dirs: list[Path] = []
        try:
            for plan in plans:
                for audio_copy in plan["audio_copies"]:
                    staged_path = staging_root / plan["safe_speaker"] / audio_copy["safe_name"]
                    self.storage.ensure_parent(staged_path)
                    shutil.copy2(audio_copy["source_path"], staged_path)

            for plan in plans:
                managed_dir = plan["managed_dir"]
                if managed_dir.exists():
                    backup_dir = backup_root / plan["safe_speaker"]
                    self.storage.ensure_parent(backup_dir)
                    shutil.move(str(managed_dir), str(backup_dir))
                    moved_dirs.append((managed_dir, backup_dir))

                staged_dir = staging_root / plan["safe_speaker"]
                shutil.move(str(staged_dir), str(managed_dir))
                installed_dirs.append(managed_dir)
                target_configs[plan["speaker_name"]] = plan["copied_config"]

            self._write_raw_configs(target_configs, project_id=target_project.id)
        except Exception:
            for installed_dir in installed_dirs:
                if installed_dir.exists():
                    shutil.rmtree(installed_dir, ignore_errors=True)
            for managed_dir, backup_dir in reversed(moved_dirs):
                if backup_dir.exists():
                    if managed_dir.exists():
                        shutil.rmtree(managed_dir, ignore_errors=True)
                    shutil.move(str(backup_dir), str(managed_dir))
            self._restore_raw_config_file(target_config_path, original_target_config)
            self._clear_cache(target_project.id)
            raise
        finally:
            shutil.rmtree(staging_root, ignore_errors=True)
            shutil.rmtree(backup_root, ignore_errors=True)

        self._clear_cache(target_project.id)
        return [
            self.get_speaker_profile(plan["speaker_name"], project_id=target_project.id)
            for plan in plans
        ]

    def _serialize_profile(self, speaker: SpeakerProfile) -> dict[str, Any]:
        payload = {
            "name": speaker.name,
            "ref_audio": self.storage.to_project_relative(speaker.ref_audio),
            "options": self._serialize_options(speaker.options),
        }
        return payload

    def _serialize_options(self, options: GenerationOptions) -> dict[str, Any]:
        serialized: dict[str, Any] = {}
        for key, value in options.model_dump(exclude_none=True).items():
            if isinstance(value, Path):
                serialized[key] = self.storage.to_project_relative(value)
            else:
                serialized[key] = value
        return serialized

    def _save_reference_audio(
        self,
        *,
        project_id: str | None,
        speaker_name: str,
        payload: bytes,
        filename: str | None,
    ) -> Path:
        if not payload:
            raise ValidationError("Uploaded reference audio is empty.")
        suffix = Path(filename or "").suffix.lower()
        if suffix not in ALLOWED_REF_AUDIO_SUFFIXES:
            raise ValidationError("Reference audio must be a `.wav` or `.mp3` file.")

        safe_speaker = self.storage.sanitize_fragment(speaker_name, default="speaker")
        safe_name = self.storage.sanitize_filename(
            filename or f"{safe_speaker}_ref{suffix}",
            default_stem=f"{safe_speaker}_ref",
            default_suffix=suffix or ".wav",
        )
        target = self._project_paths(project_id).refs_dir / safe_speaker / safe_name
        return self.storage.write_bytes(target, payload)

    def _validate_schema(
        self,
        speaker_name: str,
        config: dict[str, Any],
    ) -> SpeakerConfigSchema:
        try:
            return SpeakerConfigSchema.model_validate(config)
        except PydanticValidationError as exc:
            raise ValidationError(
                f"Invalid speaker config for `{speaker_name}`: {exc.errors(include_url=False)}"
            ) from exc

    def _resolve_referenced_audio(
        self,
        audio_path: str,
    ) -> Path:
        source_path = self.storage.resolve_path(audio_path)
        if not source_path.exists() or not source_path.is_file():
            raise MissingFileError(f"Referenced audio was not found: {source_path}")
        return source_path

    def _read_raw_configs(self, *, project_id: str | None = None) -> dict[str, dict[str, Any]]:
        speakers_path = self._project_paths(project_id).speakers_file
        if not speakers_path.exists():
            return {}

        raw_data = json.loads(speakers_path.read_text(encoding="utf-8"))
        if not isinstance(raw_data, dict):
            raise ValidationError("`speakers.json` must be an object keyed by speaker name.")
        return {
            str(key): value
            for key, value in raw_data.items()
            if isinstance(value, dict)
        }

    def _write_raw_configs(
        self,
        payload: dict[str, dict[str, Any]],
        *,
        project_id: str | None = None,
    ) -> None:
        ordered = dict(sorted(payload.items(), key=lambda item: item[0]))
        self.storage.write_json(self._project_paths(project_id).speakers_file, ordered)

    def _restore_raw_config_file(self, path: Path, content: str | None) -> None:
        if content is None:
            path.unlink(missing_ok=True)
            return
        self.storage.ensure_parent(path)
        temp_path = path.with_name(f".{path.name}.{uuid4().hex}.restore")
        try:
            temp_path.write_text(content, encoding="utf-8")
            temp_path.replace(path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

    def _remove_managed_reference_dir(
        self,
        speaker_name: str,
        *,
        project_id: str | None = None,
    ) -> None:
        managed_dir = self._project_paths(project_id).refs_dir / self.storage.sanitize_fragment(
            speaker_name,
            default="speaker",
        )
        if managed_dir.exists() and managed_dir.is_dir():
            shutil.rmtree(managed_dir, ignore_errors=True)

    def _project_paths(self, project_id: str | None) -> ProjectPaths:
        if project_id:
            return self.project_service.project_paths(project_id)
        return ProjectPaths(
            root=self.settings.paths.data_dir,
            speakers_file=self.settings.paths.speakers_file,
            refs_dir=self.settings.paths.refs_dir,
            outputs_dir=self.settings.paths.outputs_dir,
            scripts_dir=self.settings.paths.scripts_dir,
        )

    def _cache_key(self, project_id: str | None) -> str:
        return project_id or "__global__"

    def _clear_cache(self, project_id: str | None = None) -> None:
        if project_id is None:
            self._cache.clear()
            return
        self._cache.pop(self._cache_key(project_id), None)
