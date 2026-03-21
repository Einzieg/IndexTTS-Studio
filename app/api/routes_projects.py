from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_container
from app.api.responses import api_response
from app.core.container import ServiceContainer
from app.domain.schemas import EpisodeUpsertRequest, ProjectUpsertRequest


router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
def list_projects(container: ServiceContainer = Depends(get_container)) -> dict:
    return api_response(
        success=True,
        message="Loaded projects successfully.",
        data={
            "items": [
                project.model_dump(mode="json")
                for project in container.project_service.list_projects()
            ]
        },
    )


@router.get("/{project_id}")
def get_project(project_id: str, container: ServiceContainer = Depends(get_container)) -> dict:
    return api_response(
        success=True,
        message="Loaded project successfully.",
        data=container.project_service.get_project(project_id).model_dump(mode="json"),
    )


@router.post("")
def upsert_project(
    payload: ProjectUpsertRequest,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    project = container.project_service.upsert_project(
        project_id=payload.project_id,
        name=payload.name,
        description=payload.description,
    )
    return api_response(
        success=True,
        message="Project saved successfully.",
        data=project.model_dump(mode="json"),
    )


@router.delete("/{project_id}")
def delete_project(project_id: str, container: ServiceContainer = Depends(get_container)) -> dict:
    return api_response(
        success=True,
        message="Project deleted successfully.",
        data=container.project_service.delete_project(project_id),
    )


@router.post("/{project_id}/episodes")
def upsert_episode(
    project_id: str,
    payload: EpisodeUpsertRequest,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    project = container.project_service.upsert_episode(
        project_id,
        episode_id=payload.episode_id,
        name=payload.name,
        description=payload.description,
    )
    return api_response(
        success=True,
        message="Episode saved successfully.",
        data=project.model_dump(mode="json"),
    )


@router.delete("/{project_id}/episodes/{episode_id}")
def delete_episode(
    project_id: str,
    episode_id: str,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    project = container.project_service.delete_episode(project_id, episode_id)
    return api_response(
        success=True,
        message="Episode deleted successfully.",
        data=project.model_dump(mode="json"),
    )
