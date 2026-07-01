from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from app.api.dependencies import get_container
from app.api.responses import api_response
from app.core.container import ServiceContainer
from app.core.exceptions import ValidationError
from app.domain.schemas import CopySpeakersRequest


router = APIRouter(tags=["speakers"])


@router.get("/speakers")
def list_speakers(
    project_id: str | None = Query(default=None),
    container: ServiceContainer = Depends(get_container),
) -> dict:
    return api_response(
        success=True,
        message="Loaded speakers successfully.",
        data={"items": container.speaker_service.list_speakers(project_id=project_id)},
    )


@router.get("/speakers/profiles")
def list_speaker_profiles(
    project_id: str | None = Query(default=None),
    container: ServiceContainer = Depends(get_container),
) -> dict:
    return api_response(
        success=True,
        message="Loaded speaker profiles successfully.",
        data={"items": container.speaker_service.list_speaker_profiles(project_id=project_id)},
    )


@router.post("/speakers/copy")
def copy_speakers(
    payload: CopySpeakersRequest,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    profiles = container.speaker_service.copy_speakers(
        source_project_id=payload.source_project_id,
        target_project_id=payload.target_project_id,
        speaker_names=payload.speaker_names,
        overwrite=payload.overwrite,
    )
    return api_response(
        success=True,
        message="Speakers copied successfully.",
        data={"items": profiles},
    )


@router.get("/speakers/{speaker_name}")
def get_speaker_profile(
    speaker_name: str,
    project_id: str | None = Query(default=None),
    container: ServiceContainer = Depends(get_container),
) -> dict:
    return api_response(
        success=True,
        message="Loaded speaker profile successfully.",
        data=container.speaker_service.get_speaker_profile(speaker_name, project_id=project_id),
    )


@router.post("/speakers")
async def upsert_speaker(
    container: ServiceContainer = Depends(get_container),
    project_id: str | None = Form(default=None),
    name: str = Form(...),
    ref_audio: UploadFile | None = File(default=None),
    emo_alpha: str | None = Form(default=None),
    emo_vector: str | None = Form(default=None),
    emo_text: str | None = Form(default=None),
    use_emo_text: str | None = Form(default=None),
    text_split_method: str | None = Form(default=None),
    interval_silence: str | None = Form(default=None),
    temperature: str | None = Form(default=None),
    top_p: str | None = Form(default=None),
    top_k: str | None = Form(default=None),
    max_mel_tokens: str | None = Form(default=None),
    repetition_penalty: str | None = Form(default=None),
    length_penalty: str | None = Form(default=None),
    num_beams: str | None = Form(default=None),
    use_random: str | None = Form(default=None),
    max_text_tokens_per_segment: str | None = Form(default=None),
) -> dict:
    fields = {
        "emo_alpha": _parse_float(emo_alpha),
        "emo_vector": _parse_json_list(emo_vector),
        "emo_text": _normalize_text(emo_text),
        "use_emo_text": _parse_bool(use_emo_text),
        "text_split_method": _normalize_text(text_split_method),
        "interval_silence": _parse_float(interval_silence),
        "temperature": _parse_float(temperature),
        "top_p": _parse_float(top_p),
        "top_k": _parse_int(top_k),
        "max_mel_tokens": _parse_int(max_mel_tokens),
        "repetition_penalty": _parse_float(repetition_penalty),
        "length_penalty": _parse_float(length_penalty),
        "num_beams": _parse_int(num_beams),
        "use_random": _parse_bool(use_random),
        "max_text_tokens_per_segment": _parse_int(max_text_tokens_per_segment),
    }
    upload_bytes = await ref_audio.read() if ref_audio is not None else None
    profile = container.speaker_service.upsert_speaker(
        project_id=project_id,
        name=name,
        fields=fields,
        ref_audio_bytes=upload_bytes,
        ref_audio_filename=ref_audio.filename if ref_audio is not None else None,
    )
    return api_response(
        success=True,
        message="Speaker saved successfully.",
        data=profile,
    )


@router.delete("/speakers/{speaker_name}")
def delete_speaker(
    speaker_name: str,
    project_id: str | None = Query(default=None),
    container: ServiceContainer = Depends(get_container),
) -> dict:
    return api_response(
        success=True,
        message="Speaker deleted successfully.",
        data=container.speaker_service.delete_speaker(speaker_name, project_id=project_id),
    )


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _parse_float(value: str | None) -> float | None:
    normalized = _normalize_text(value)
    if normalized is None:
        return None
    try:
        return float(normalized)
    except ValueError as exc:
        raise ValidationError(f"Invalid float value: {value}") from exc


def _parse_int(value: str | None) -> int | None:
    normalized = _normalize_text(value)
    if normalized is None:
        return None
    try:
        return int(normalized)
    except ValueError as exc:
        raise ValidationError(f"Invalid integer value: {value}") from exc


def _parse_bool(value: str | None) -> bool | None:
    normalized = _normalize_text(value)
    if normalized is None:
        return None
    lowered = normalized.lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    raise ValidationError(f"Invalid boolean value: {value}")


def _parse_json_list(value: str | None) -> list[Any] | None:
    normalized = _normalize_text(value)
    if normalized is None:
        return None
    try:
        decoded = json.loads(normalized)
    except json.JSONDecodeError as exc:
        raise ValidationError("`emo_vector` must be a JSON array.") from exc
    if not isinstance(decoded, list):
        raise ValidationError("`emo_vector` must be a JSON array.")
    return decoded
