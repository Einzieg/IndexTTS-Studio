from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.models import (
    ProjectConfig,
    StudioRenderRecord,
    StudioTableRecord,
    StudioTableRowRecord,
    utc_now,
)
from app.infra.storage import StorageService
from app.services.project_service import ProjectService


@dataclass(slots=True)
class StudioTableExportResult:
    archive_path: Path
    download_name: str
    exported_count: int


class StudioTableService:
    def __init__(
        self,
        storage: StorageService,
        project_service: ProjectService,
    ) -> None:
        self.storage = storage
        self.project_service = project_service

    def load_table(self, *, project_id: str, episode_id: str) -> StudioTableRecord:
        normalized_project_id, normalized_episode_id, draft_path = self._resolve_draft_path(
            project_id=project_id,
            episode_id=episode_id,
        )
        if not draft_path.exists():
            return StudioTableRecord(
                project_id=normalized_project_id,
                episode_id=normalized_episode_id,
                rows=[],
            )

        payload = StudioTableRecord.model_validate_json(draft_path.read_text(encoding="utf-8"))
        return payload.model_copy(
            update={
                "project_id": normalized_project_id,
                "episode_id": normalized_episode_id,
            }
        )

    def save_table(
        self,
        *,
        project_id: str,
        episode_id: str,
        rows: list[StudioTableRowRecord],
    ) -> StudioTableRecord:
        normalized_project_id, normalized_episode_id, draft_path = self._resolve_draft_path(
            project_id=project_id,
            episode_id=episode_id,
        )
        payload = StudioTableRecord(
            project_id=normalized_project_id,
            episode_id=normalized_episode_id,
            rows=rows,
            updated_at=utc_now(),
        )
        self.storage.write_json(draft_path, payload.model_dump(mode="json", by_alias=True))
        return payload

    def export_table_audio(
        self,
        *,
        project_id: str,
        episode_id: str,
    ) -> StudioTableExportResult:
        normalized_project_id, normalized_episode_id, _ = self._resolve_draft_path(
            project_id=project_id,
            episode_id=episode_id,
        )
        project = self.project_service.get_project(normalized_project_id)
        episode = next(
            (item for item in project.episodes if item.id == normalized_episode_id),
            None,
        )
        if episode is None:
            raise NotFoundError(
                f"Episode `{normalized_episode_id}` does not exist in project `{project.id}`."
            )

        table = self.load_table(
            project_id=normalized_project_id,
            episode_id=normalized_episode_id,
        )
        project_paths = self.project_service.project_paths(project.id)
        export_dir = project_paths.outputs_dir / normalized_episode_id / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)

        stamp = utc_now().strftime("%Y%m%d_%H%M%S")
        download_name = self.storage.sanitize_filename(
            f"项目-{project.name}-分集-{episode.name}-导出-{stamp}.zip",
            default_stem="studio_export",
            default_suffix=".zip",
        )
        archive_path = export_dir / download_name
        exported_count = 0

        with ZipFile(archive_path, mode="w", compression=ZIP_DEFLATED) as archive:
            for index, row in enumerate(table.rows, start=1):
                selected_render = self._selected_render(row)
                if selected_render is None:
                    continue

                source_path = self.storage.resolve_path(selected_render.output_path)
                if (
                    not source_path.exists()
                    or not source_path.is_file()
                    or not self._is_under_root(source_path, self.storage.settings.paths.data_dir)
                ):
                    continue

                archive_name = self._build_export_filename(
                    project=project,
                    episode_name=episode.name,
                    row_index=index,
                    speaker=row.speaker,
                    suffix=source_path.suffix or ".wav",
                )
                archive.write(source_path, arcname=archive_name)
                exported_count += 1

        if exported_count == 0:
            archive_path.unlink(missing_ok=True)
            raise ValidationError("当前分集还没有可导出的配音，请先生成并选定配音版本。")

        return StudioTableExportResult(
            archive_path=archive_path,
            download_name=download_name,
            exported_count=exported_count,
        )

    def _resolve_draft_path(self, *, project_id: str, episode_id: str) -> tuple[str, str, Path]:
        normalized_project_id = self._normalize_identifier(project_id, label="Project id")
        normalized_episode_id = self._normalize_identifier(episode_id, label="Episode id")
        project = self.project_service.get_project(normalized_project_id)
        if not any(episode.id == normalized_episode_id for episode in project.episodes):
            raise NotFoundError(
                f"Episode `{normalized_episode_id}` does not exist in project `{project.id}`."
            )
        project_paths = self.project_service.project_paths(project.id)
        episode_dir = project_paths.scripts_dir / normalized_episode_id
        episode_dir.mkdir(parents=True, exist_ok=True)
        return project.id, normalized_episode_id, episode_dir / "studio_table.json"

    @staticmethod
    def _normalize_identifier(value: str, *, label: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValidationError(f"{label} must not be empty.")
        return normalized

    def _build_export_filename(
        self,
        *,
        project: ProjectConfig,
        episode_name: str,
        row_index: int,
        speaker: str,
        suffix: str,
    ) -> str:
        project_name = self.storage.sanitize_fragment(project.name, default="project")
        safe_episode_name = self.storage.sanitize_fragment(episode_name, default="episode")
        safe_speaker_name = self.storage.sanitize_fragment(speaker, default="speaker")
        safe_suffix = suffix if suffix.startswith(".") else f".{suffix}"
        return (
            f"项目-{project_name}-分集-{safe_episode_name}-"
            f"{str(row_index).zfill(3)}-{safe_speaker_name}{safe_suffix}"
        )

    @staticmethod
    def _selected_render(row: StudioTableRowRecord) -> StudioRenderRecord | None:
        if row.selected_render_id:
            for render in row.renders:
                if render.render_id == row.selected_render_id:
                    return render
        return row.renders[-1] if row.renders else None

    @staticmethod
    def _is_under_root(path: Path, root: Path) -> bool:
        try:
            path.resolve().relative_to(root.resolve())
        except ValueError:
            return False
        return True
