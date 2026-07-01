from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_container
from app.api.path_validation import resolve_api_script_path
from app.api.responses import api_response
from app.core.container import ServiceContainer
from app.domain.schemas import (
    BatchSynthesizeRequest,
    RegenerateRequest,
    SingleSynthesizeRequest,
)


router = APIRouter(prefix="/tts", tags=["tts"])


@router.post("/single")
def synthesize_single(
    payload: SingleSynthesizeRequest,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    result = container.tts_service.synthesize_single(
        project_id=payload.project_id,
        episode_id=payload.episode_id,
        speaker=payload.speaker,
        text=payload.text,
        output_name=payload.output_name,
        override=payload.override,
        force=payload.force,
    )
    return api_response(
        success=True,
        message="Single-line synthesis completed.",
        data=result,
    )


@router.post("/batch")
def synthesize_batch(
    payload: BatchSynthesizeRequest,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    script_path = resolve_api_script_path(
        container,
        payload.script_path,
        project_id=payload.project_id,
    )
    report = container.job_service.run_batch(
        script_path=script_path,
        project_id=payload.project_id,
        episode_id=payload.episode_id,
        skip_existing=payload.skip_existing,
        continue_on_error=payload.continue_on_error,
        force=payload.force,
    )
    return api_response(
        success=True,
        message="Batch synthesis finished.",
        data=report,
    )


@router.post("/regenerate")
def regenerate_line(
    payload: RegenerateRequest,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    script_path = resolve_api_script_path(
        container,
        payload.script_path,
        project_id=payload.project_id,
    )
    result = container.job_service.regenerate_line(
        script_path=script_path,
        project_id=payload.project_id,
        episode_id=payload.episode_id,
        line_id=payload.line_id,
        force=payload.force,
    )
    return api_response(
        success=True,
        message="Line regeneration completed.",
        data=result,
    )
