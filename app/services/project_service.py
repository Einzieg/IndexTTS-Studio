from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel

from app.core.config import AppSettings
from app.core.exceptions import NotFoundError, ValidationError
from app.domain.models import EpisodeConfig, ProjectConfig
from app.infra.storage import StorageService


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class ProjectPaths:
    root: Path
    speakers_file: Path
    refs_dir: Path
    outputs_dir: Path
    scripts_dir: Path


class ProjectService:
    def __init__(self, settings: AppSettings, storage: StorageService) -> None:
        self.settings = settings
        self.storage = storage
        self._cache: dict[str, ProjectConfig] | None = None

    @property
    def projects_root(self) -> Path:
        return self.settings.paths.data_dir / "projects"

    @property
    def index_file(self) -> Path:
        return self.projects_root / "projects.json"

    def ensure_runtime_dirs(self) -> None:
        self.projects_root.mkdir(parents=True, exist_ok=True)

    def list_projects(self) -> list[ProjectConfig]:
        projects = list(self._load_projects().values())
        projects.sort(key=lambda item: item.updated_at, reverse=True)
        return projects

    def get_project(self, project_id: str) -> ProjectConfig:
        normalized = self._normalize_identifier(project_id, label="Project id")
        project = self._load_projects().get(normalized)
        if project is None:
            raise NotFoundError(f"Project `{normalized}` does not exist.")
        return project

    def upsert_project(
        self,
        *,
        name: str,
        project_id: str | None = None,
        description: str | None = None,
    ) -> ProjectConfig:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValidationError("Project name must not be empty.")

        projects = self._load_projects()
        normalized_id = self._resolve_existing_identifier(
            project_id,
            existing_ids=projects.keys(),
            label="Project id",
        ) or self._generate_unique_id(
            normalized_name,
            existing_ids=projects.keys(),
            default="project",
        )
        existing = projects.get(normalized_id)
        now = _utc_now()
        project = ProjectConfig(
            id=normalized_id,
            name=normalized_name,
            description=description.strip() if description and description.strip() else None,
            episodes=list(existing.episodes) if existing else [],
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        projects[normalized_id] = project
        self._write_projects(projects)
        self.ensure_project_dirs(normalized_id)
        return self.get_project(normalized_id)

    def delete_project(self, project_id: str) -> dict[str, str]:
        normalized = self._normalize_identifier(project_id, label="Project id")
        projects = self._load_projects()
        if normalized not in projects:
            raise NotFoundError(f"Project `{normalized}` does not exist.")
        projects.pop(normalized)
        self._write_projects(projects)
        project_root = self.projects_root / normalized
        if project_root.exists():
            shutil.rmtree(project_root, ignore_errors=True)
        return {"id": normalized}

    def upsert_episode(
        self,
        project_id: str,
        *,
        name: str,
        episode_id: str | None = None,
        description: str | None = None,
    ) -> ProjectConfig:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValidationError("Episode name must not be empty.")

        project = self.get_project(project_id)
        episodes_by_id = {episode.id: episode for episode in project.episodes}
        normalized_episode_id = self._resolve_existing_identifier(
            episode_id,
            existing_ids=episodes_by_id.keys(),
            label="Episode id",
        ) or self._generate_unique_id(
            normalized_name,
            existing_ids=episodes_by_id.keys(),
            default="episode",
        )
        existing = episodes_by_id.get(normalized_episode_id)
        episodes_by_id[normalized_episode_id] = EpisodeConfig(
            id=normalized_episode_id,
            name=normalized_name,
            description=description.strip() if description and description.strip() else None,
        )
        updated_project = project.model_copy(
            update={
                "episodes": sorted(episodes_by_id.values(), key=lambda item: item.id),
                "updated_at": _utc_now(),
            }
        )
        self._save_project(updated_project)
        project_paths = self.ensure_project_dirs(project.id)
        (project_paths.scripts_dir / normalized_episode_id).mkdir(parents=True, exist_ok=True)
        (project_paths.outputs_dir / normalized_episode_id).mkdir(parents=True, exist_ok=True)
        return self.get_project(updated_project.id)

    def delete_episode(self, project_id: str, episode_id: str) -> ProjectConfig:
        project = self.get_project(project_id)
        normalized_episode_id = self._normalize_identifier(episode_id, label="Episode id")
        episodes = [episode for episode in project.episodes if episode.id != normalized_episode_id]
        if len(episodes) == len(project.episodes):
            raise NotFoundError(
                f"Episode `{normalized_episode_id}` does not exist in project `{project.id}`."
            )

        updated_project = project.model_copy(
            update={
                "episodes": episodes,
                "updated_at": _utc_now(),
            }
        )
        self._save_project(updated_project)

        project_paths = self.ensure_project_dirs(project.id)
        episode_script_dir = project_paths.scripts_dir / normalized_episode_id
        episode_output_dir = project_paths.outputs_dir / normalized_episode_id
        if episode_script_dir.exists():
            shutil.rmtree(episode_script_dir, ignore_errors=True)
        if episode_output_dir.exists():
            shutil.rmtree(episode_output_dir, ignore_errors=True)
        return self.get_project(project.id)

    def ensure_project_dirs(self, project_id: str) -> ProjectPaths:
        normalized = self._normalize_identifier(project_id, label="Project id")
        root = self.projects_root / normalized
        speakers_file = root / "speakers.json"
        refs_dir = root / "refs"
        outputs_dir = root / "outputs"
        scripts_dir = root / "scripts"
        root.mkdir(parents=True, exist_ok=True)
        refs_dir.mkdir(parents=True, exist_ok=True)
        outputs_dir.mkdir(parents=True, exist_ok=True)
        scripts_dir.mkdir(parents=True, exist_ok=True)
        if not speakers_file.exists():
            self.storage.write_json(speakers_file, {})
        return ProjectPaths(
            root=root,
            speakers_file=speakers_file,
            refs_dir=refs_dir,
            outputs_dir=outputs_dir,
            scripts_dir=scripts_dir,
        )

    def project_paths(self, project_id: str) -> ProjectPaths:
        project = self.get_project(project_id)
        return self.ensure_project_dirs(project.id)

    def episode_output_dir(self, project_id: str, episode_id: str | None = None) -> Path:
        paths = self.project_paths(project_id)
        if episode_id:
            normalized_episode_id = self._normalize_identifier(episode_id, label="Episode id")
            target = paths.outputs_dir / normalized_episode_id
            target.mkdir(parents=True, exist_ok=True)
            return target
        paths.outputs_dir.mkdir(parents=True, exist_ok=True)
        return paths.outputs_dir

    def _save_project(self, project: ProjectConfig) -> None:
        projects = self._load_projects()
        projects[project.id] = project
        self._write_projects(projects)

    def _load_projects(self) -> dict[str, ProjectConfig]:
        if self._cache is not None:
            return self._cache

        self.ensure_runtime_dirs()
        if not self.index_file.exists():
            self.storage.write_json(self.index_file, {"items": []})

        raw_payload = self.index_file.read_text(encoding="utf-8")
        decoded = ProjectIndex.model_validate_json(raw_payload)
        self._cache = {project.id: project for project in decoded.items}
        return self._cache

    def _write_projects(self, projects: dict[str, ProjectConfig]) -> None:
        payload = ProjectIndex(items=sorted(projects.values(), key=lambda item: item.id))
        self.storage.write_json(self.index_file, payload)
        self._cache = {project.id: project for project in payload.items}

    @staticmethod
    def _normalize_identifier(value: str, *, label: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValidationError(f"{label} must not be empty.")
        return normalized

    def _generate_unique_id(
        self,
        name: str,
        *,
        existing_ids: object,
        default: str,
    ) -> str:
        seed = self.storage.sanitize_fragment(name, default=default).casefold()
        existing = set(existing_ids)
        candidate = seed
        while candidate in existing:
            candidate = f"{seed}_{uuid4().hex[:6]}"
        return candidate

    def _resolve_existing_identifier(
        self,
        value: str | None,
        *,
        existing_ids: object,
        label: str,
    ) -> str | None:
        if not value:
            return None
        normalized = self._normalize_identifier(value, label=label)
        existing = set(existing_ids)
        return normalized if normalized in existing else None


class ProjectIndex(BaseModel):
    items: list[ProjectConfig]
