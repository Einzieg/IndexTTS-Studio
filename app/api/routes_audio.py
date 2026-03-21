from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_container
from app.api.responses import api_response
from app.core.container import ServiceContainer
from app.domain.schemas import MergeAudioRequest


router = APIRouter(prefix="/audio", tags=["audio"])


@router.get("/capabilities")
def audio_capabilities(container: ServiceContainer = Depends(get_container)) -> dict:
    return api_response(
        success=True,
        message="Audio capabilities loaded.",
        data=container.audio_service.capabilities(),
    )


@router.post("/merge")
def merge_script_audio(
    payload: MergeAudioRequest,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    report = container.audio_service.merge_script_outputs(
        script_path=payload.script_path,
        output_name=payload.output_name,
        gap_ms=payload.gap_ms,
        use_timeline=payload.use_timeline,
        tail_padding_ms=payload.tail_padding_ms,
        force=payload.force,
    )
    return api_response(
        success=True,
        message="Preview mixdown completed.",
        data=report,
    )
