from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


class GenerationOptions(BaseModel):
    model_config = ConfigDict(extra="ignore")

    emo_audio: Path | None = None
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

    def as_infer_kwargs(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)

    @model_validator(mode="after")
    def _validate_emotion_inputs(self) -> "GenerationOptions":
        if self.emo_audio and self.emo_vector:
            raise ValueError("`emo_audio` and `emo_vector` are mutually exclusive.")
        return self


class SpeakerProfile(BaseModel):
    name: str
    ref_audio: Path
    options: GenerationOptions = Field(default_factory=GenerationOptions)


class EpisodeConfig(BaseModel):
    id: str
    name: str
    description: str | None = None


class ProjectConfig(BaseModel):
    id: str
    name: str
    description: str | None = None
    episodes: list[EpisodeConfig] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ScriptLine(BaseModel):
    id: str
    scene: str | None = None
    speaker: str
    text: str
    output_name: str | None = None
    override: dict[str, Any] = Field(default_factory=dict)
    start_ms: int | None = None
    end_ms: int | None = None

    @field_validator("id", "speaker", "text", mode="before")
    @classmethod
    def _strip_required_fields(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("start_ms", "end_ms", mode="before")
    @classmethod
    def _normalize_timing_field(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            return int(float(stripped))
        if isinstance(value, float):
            return int(value)
        return value

    @model_validator(mode="after")
    def _validate_timing_range(self) -> "ScriptLine":
        if self.start_ms is not None and self.start_ms < 0:
            raise ValueError("`start_ms` must be greater than or equal to 0.")
        if self.end_ms is not None and self.end_ms < 0:
            raise ValueError("`end_ms` must be greater than or equal to 0.")
        if (
            self.start_ms is not None
            and self.end_ms is not None
            and self.end_ms < self.start_ms
        ):
            raise ValueError("`end_ms` must be greater than or equal to `start_ms`.")
        return self


class SynthesisResult(BaseModel):
    success: bool
    status: Literal["done", "skipped"]
    speaker: str
    text: str
    output_path: Path
    duration_ms: int = 0
    error: str | None = None
    line_id: str | None = None
    used_options: dict[str, Any] = Field(default_factory=dict)


class BatchFailure(BaseModel):
    line_id: str
    speaker: str
    text: str
    error_message: str
    timestamp: datetime


class BatchReport(BaseModel):
    success: bool
    stopped_early: bool = False
    script_path: Path
    output_dir: Path
    total: int
    done: int
    skipped: int
    failed: int
    failed_ids: list[str] = Field(default_factory=list)
    failures: list[BatchFailure] = Field(default_factory=list)


class AudioMergeReport(BaseModel):
    mode: Literal["sequence", "timeline"] = "sequence"
    script_path: Path
    output_path: Path
    segment_count: int
    gap_ms: int
    tail_padding_ms: int = 0
    duration_ms: int
    sample_rate: int
    channels: int
    sample_width: int
    source_paths: list[Path] = Field(default_factory=list)


class JobLineRecord(BaseModel):
    line_id: str
    scene: str | None = None
    speaker: str
    text: str
    output_name: str | None = None
    override: dict[str, Any] = Field(default_factory=dict)
    start_ms: int | None = None
    end_ms: int | None = None
    status: Literal["pending", "running", "done", "skipped", "failed"] = "pending"
    output_path: Path | None = None
    duration_ms: int = 0
    error: str | None = None
    updated_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class JobRecord(BaseModel):
    job_id: str
    status: Literal[
        "queued",
        "running",
        "completed",
        "completed_with_errors",
        "failed",
    ] = "queued"
    script_path: Path
    output_dir: Path
    project_id: str | None = None
    episode_id: str | None = None
    skip_existing: bool = True
    continue_on_error: bool = True
    force: bool = False
    total: int = 0
    done: int = 0
    skipped: int = 0
    failed: int = 0
    failed_ids: list[str] = Field(default_factory=list)
    stopped_early: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    lines: list[JobLineRecord] = Field(default_factory=list)
    report: BatchReport | None = None


class StudioRenderRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    render_id: str = Field(alias="renderId")
    output_path: Path = Field(alias="outputPath")
    duration_ms: int = Field(default=0, alias="durationMs")
    created_at: datetime = Field(default_factory=utc_now, alias="createdAt")
    source: Literal["batch", "config"] = "batch"
    used_options: dict[str, Any] = Field(default_factory=dict, alias="usedOptions")


class StudioTableRowRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    row_id: str = Field(alias="rowId")
    speaker: str = ""
    text: str = ""
    selected: bool = False
    override: dict[str, Any] = Field(default_factory=dict)
    renders: list[StudioRenderRecord] = Field(default_factory=list)
    selected_render_id: str | None = Field(default=None, alias="selectedRenderId")
    last_status: Literal["idle", "generating", "done", "skipped", "failed"] = Field(
        default="idle",
        alias="lastStatus",
    )
    last_error: str | None = Field(default=None, alias="lastError")


class StudioTableRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    project_id: str = Field(alias="projectId")
    episode_id: str = Field(alias="episodeId")
    rows: list[StudioTableRowRecord] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now, alias="updatedAt")


class HealthStatus(BaseModel):
    status: str = "ok"
