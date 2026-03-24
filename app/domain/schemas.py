from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.models import StudioTableRowRecord


class SpeakerConfigSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ref_audio: str
    emo_audio: str | None = None
    emo_alpha: float | None = None
    emo_vector: list[float] | None = None
    emo_text: str | None = None
    use_emo_text: bool | None = None
    text_split_method: str | None = None
    interval_silence: float | None = None
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    max_mel_tokens: int | None = None
    repetition_penalty: float | None = None
    length_penalty: float | None = None
    num_beams: int | None = None
    use_random: bool | None = None
    max_text_tokens_per_segment: int | None = None

    @model_validator(mode="after")
    def validate_emotion_inputs(self) -> "SpeakerConfigSchema":
        if self.emo_audio and self.emo_vector:
            raise ValueError("`emo_audio` and `emo_vector` are mutually exclusive.")
        return self


class SingleSynthesizeRequest(BaseModel):
    project_id: str | None = None
    episode_id: str | None = None
    speaker: str
    text: str
    output_name: str | None = None
    override: dict[str, Any] = Field(default_factory=dict)
    force: bool = False


class LoginRequest(BaseModel):
    username: str
    password: str


class BatchSynthesizeRequest(BaseModel):
    project_id: str | None = None
    episode_id: str | None = None
    script_path: str
    skip_existing: bool = True
    continue_on_error: bool = True
    force: bool = False


class CreateJobRequest(BatchSynthesizeRequest):
    pass


class InlineScriptLineRequest(BaseModel):
    id: str | None = None
    scene: str | None = None
    speaker: str
    text: str
    output_name: str | None = None
    override: dict[str, Any] = Field(default_factory=dict)
    start_ms: int | None = None
    end_ms: int | None = None


class CreateInlineJobRequest(BaseModel):
    project_id: str | None = None
    episode_id: str | None = None
    title: str | None = None
    lines: list[InlineScriptLineRequest]
    skip_existing: bool = True
    continue_on_error: bool = True
    force: bool = False


class MergeAudioRequest(BaseModel):
    project_id: str | None = None
    episode_id: str | None = None
    script_path: str
    output_name: str | None = None
    gap_ms: int = 250
    use_timeline: bool = False
    tail_padding_ms: int = 0
    force: bool = False


class RegenerateRequest(BaseModel):
    project_id: str | None = None
    episode_id: str | None = None
    script_path: str
    line_id: str
    force: bool = True


class ProjectUpsertRequest(BaseModel):
    project_id: str | None = None
    name: str
    description: str | None = None


class EpisodeUpsertRequest(BaseModel):
    episode_id: str | None = None
    name: str
    description: str | None = None


class StudioTableSaveRequest(BaseModel):
    project_id: str
    episode_id: str
    rows: list[StudioTableRowRecord] = Field(default_factory=list)
