from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_container
from app.api.responses import api_response
from app.core.container import ServiceContainer
from app.domain.schemas import CreateInlineJobRequest, CreateJobRequest


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/capabilities")
def job_capabilities(container: ServiceContainer = Depends(get_container)) -> dict:
    return api_response(
        success=True,
        message="Job capabilities loaded.",
        data={
            "async_jobs": True,
            "queue_backend": "json_file_serial",
            "persistent": True,
            "queue_size": container.job_service.queue_size(),
            "audio": container.audio_service.capabilities(),
        },
    )


@router.post("")
def create_job(
    payload: CreateJobRequest,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    job = container.job_service.create_job(
        script_path=payload.script_path,
        project_id=payload.project_id,
        episode_id=payload.episode_id,
        skip_existing=payload.skip_existing,
        continue_on_error=payload.continue_on_error,
        force=payload.force,
    )
    return api_response(
        success=True,
        message="Job queued successfully.",
        data=job.model_dump(mode="json", exclude={"lines"}),
    )


@router.post("/from-lines")
def create_job_from_lines(
    payload: CreateInlineJobRequest,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    job = container.job_service.create_job_from_lines(
        title=payload.title,
        project_id=payload.project_id,
        episode_id=payload.episode_id,
        lines_payload=[line.model_dump(mode="json", exclude_none=True) for line in payload.lines],
        skip_existing=payload.skip_existing,
        continue_on_error=payload.continue_on_error,
        force=payload.force,
    )
    return api_response(
        success=True,
        message="Inline job queued successfully.",
        data=job.model_dump(mode="json", exclude={"lines"}),
    )


@router.get("")
def list_jobs(container: ServiceContainer = Depends(get_container)) -> dict:
    jobs = [
        job.model_dump(mode="json", exclude={"lines"})
        for job in container.job_service.list_jobs()
    ]
    return api_response(
        success=True,
        message="Loaded jobs successfully.",
        data={"items": jobs},
    )


@router.get("/{job_id}")
def get_job(job_id: str, container: ServiceContainer = Depends(get_container)) -> dict:
    job = container.job_service.get_job(job_id)
    return api_response(
        success=True,
        message="Loaded job successfully.",
        data=job.model_dump(mode="json", exclude={"lines"}),
    )


@router.get("/{job_id}/lines")
def get_job_lines(job_id: str, container: ServiceContainer = Depends(get_container)) -> dict:
    return api_response(
        success=True,
        message="Loaded job lines successfully.",
        data={"items": container.job_service.get_job_lines(job_id)},
    )
