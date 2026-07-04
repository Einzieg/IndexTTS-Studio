from __future__ import annotations

from collections.abc import Callable
import queue
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.core.exceptions import NotFoundError, OutputNameCollisionError, StudioError, ValidationError
from app.core.logger import get_logger
from app.domain.models import (
    BatchFailure,
    BatchReport,
    JobLineRecord,
    JobRecord,
    ScriptLine,
    SynthesisResult,
)
from app.infra.storage import StorageService
from app.services.project_service import ProjectService
from app.services.script_service import ScriptService
from app.services.tts_service import TTSService


@dataclass(slots=True)
class _QueuedBatchJob:
    job_id: str
    script_path: Path
    output_dir: Path
    project_id: str | None
    lines: list[ScriptLine]
    skip_existing: bool
    continue_on_error: bool
    force: bool


def _utc_now() -> datetime:
    return datetime.now(UTC)


class JobService:
    def __init__(
        self,
        storage: StorageService,
        project_service: ProjectService,
        script_service: ScriptService,
        tts_service: TTSService,
    ) -> None:
        self.storage = storage
        self.project_service = project_service
        self.script_service = script_service
        self.tts_service = tts_service
        self.logger = get_logger("indextts_studio.jobs")
        self._jobs_dir = self.storage.settings.paths.jobs_dir
        self._jobs: dict[str, JobRecord] = {}
        self._queue: queue.Queue[_QueuedBatchJob | None] = queue.Queue()
        self._jobs_lock = threading.RLock()
        self._worker_thread: threading.Thread | None = None
        self._shutdown_event = threading.Event()
        self._initialized = False

    def initialize(self) -> None:
        with self._jobs_lock:
            if self._initialized:
                return
            loaded_job_ids = self._load_persisted_jobs_locked()
            resumable_tasks = self._restore_resumable_tasks_locked(loaded_job_ids)
            self._initialized = True

        if resumable_tasks:
            self._ensure_worker_started()
            for task in resumable_tasks:
                self._queue.put(task)
            self.logger.info("Recovered %s queued job(s) from disk.", len(resumable_tasks))

    def run_batch(
        self,
        *,
        script_path: str | Path,
        project_id: str | None = None,
        episode_id: str | None = None,
        skip_existing: bool = True,
        continue_on_error: bool = True,
        force: bool = False,
    ) -> BatchReport:
        resolved_script_path = self.storage.resolve_path(script_path)
        lines = self.script_service.load_script(resolved_script_path)
        self._validate_line_text_lengths(lines)
        output_dir = self._resolve_output_dir(
            resolved_script_path,
            project_id=project_id,
            episode_id=episode_id,
        )
        return self._execute_batch(
            script_path=resolved_script_path,
            lines=lines,
            output_dir=output_dir,
            project_id=project_id,
            skip_existing=skip_existing,
            continue_on_error=continue_on_error,
            force=force,
        )

    def create_job(
        self,
        *,
        script_path: str | Path,
        project_id: str | None = None,
        episode_id: str | None = None,
        skip_existing: bool = True,
        continue_on_error: bool = True,
        force: bool = False,
    ) -> JobRecord:
        resolved_script_path = self.storage.resolve_path(script_path)
        lines = self.script_service.load_script(resolved_script_path)
        self._validate_line_text_lengths(lines)
        output_dir = self._resolve_output_dir(
            resolved_script_path,
            project_id=project_id,
            episode_id=episode_id,
        )
        job_id = uuid4().hex
        record = JobRecord(
            job_id=job_id,
            script_path=resolved_script_path,
            output_dir=output_dir,
            project_id=project_id,
            episode_id=episode_id,
            skip_existing=skip_existing,
            continue_on_error=continue_on_error,
            force=force,
            total=len(lines),
            lines=[
                JobLineRecord(
                    line_id=line.id,
                    scene=line.scene,
                    speaker=line.speaker,
                    text=line.text,
                    output_name=line.output_name,
                    override=line.override,
                    start_ms=line.start_ms,
                    end_ms=line.end_ms,
                )
                for line in lines
            ],
        )
        with self._jobs_lock:
            self._jobs[job_id] = record
            self._persist_job_locked(record)
        self._ensure_worker_started()
        self._queue.put(
            _QueuedBatchJob(
                job_id=job_id,
                script_path=resolved_script_path,
                output_dir=output_dir,
                project_id=project_id,
                lines=lines,
                skip_existing=skip_existing,
                continue_on_error=continue_on_error,
                force=force,
            )
        )
        self.logger.info("Queued async batch job %s for %s", job_id, resolved_script_path)
        return self.get_job(job_id)

    def create_job_from_lines(
        self,
        *,
        title: str | None,
        project_id: str | None = None,
        episode_id: str | None = None,
        lines_payload: list[dict[str, object]],
        skip_existing: bool = True,
        continue_on_error: bool = True,
        force: bool = False,
    ) -> JobRecord:
        lines = self.script_service.build_lines(
            lines_payload,
            auto_assign_ids=True,
        )
        self._validate_line_text_lengths(lines)
        script_path = self.script_service.save_inline_script(
            title=title,
            lines=lines,
            base_dir=self._inline_script_dir(project_id=project_id, episode_id=episode_id),
        )
        return self.create_job(
            script_path=script_path,
            project_id=project_id,
            episode_id=episode_id,
            skip_existing=skip_existing,
            continue_on_error=continue_on_error,
            force=force,
        )

    def list_jobs(self) -> list[JobRecord]:
        with self._jobs_lock:
            jobs = list(self._jobs.values())
        jobs.sort(key=lambda item: item.created_at, reverse=True)
        return [job.model_copy(deep=True) for job in jobs]

    def get_job(self, job_id: str) -> JobRecord:
        with self._jobs_lock:
            record = self._jobs.get(job_id)
            if record is None:
                raise NotFoundError(f"Job `{job_id}` does not exist.")
            return record.model_copy(deep=True)

    def get_job_lines(self, job_id: str) -> list[JobLineRecord]:
        return self.get_job(job_id).lines

    def _validate_line_text_lengths(self, lines: list[ScriptLine]) -> None:
        max_line_chars = self.storage.settings.max_script_line_text_chars
        for line in lines:
            text_length = len(line.text.strip())
            if text_length > max_line_chars:
                raise ValidationError(
                    f"第 `{line.id}` 行台词长度为 {text_length} 字，超过单行上限 "
                    f"{max_line_chars} 字，请先拆分后再生成。"
                )

    def queue_size(self) -> int:
        return self._queue.qsize()

    def shutdown(self) -> None:
        self._shutdown_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._queue.put(None)
            self._worker_thread.join(timeout=2)

    def regenerate_line(
        self,
        *,
        script_path: str | Path,
        project_id: str | None = None,
        episode_id: str | None = None,
        line_id: str,
        force: bool = True,
    ) -> SynthesisResult:
        resolved_script_path = self.storage.resolve_path(script_path)
        line = self.script_service.get_line(resolved_script_path, line_id)
        output_dir = self._resolve_output_dir(
            resolved_script_path,
            project_id=project_id,
            episode_id=episode_id,
        )
        return self.tts_service.synthesize_script_line(
            line,
            output_dir,
            project_id=project_id,
            skip_existing=False,
            force=force,
        )

    def _execute_batch(
        self,
        *,
        script_path: Path,
        lines: list[ScriptLine],
        output_dir: Path,
        project_id: str | None,
        skip_existing: bool,
        continue_on_error: bool,
        force: bool,
        on_line_start: Callable[[ScriptLine, Path], None] | None = None,
        on_line_result: Callable[[ScriptLine, SynthesisResult], None] | None = None,
        on_line_failure: Callable[[ScriptLine, BatchFailure], None] | None = None,
    ) -> BatchReport:
        results: list[SynthesisResult] = []
        failures: list[BatchFailure] = []
        reserved_outputs: dict[Path, str] = {}
        stopped_early = False

        for line in lines:
            try:
                output_path = self.tts_service.resolve_line_output_path(line, output_dir)
                self._validate_output_collision(line, output_path, reserved_outputs)
                if on_line_start is not None:
                    on_line_start(line, output_path)
                result = self.tts_service.synthesize_script_line(
                    line,
                    output_dir,
                    project_id=project_id,
                    skip_existing=skip_existing,
                    force=force,
                )
                results.append(result)
                if on_line_result is not None:
                    on_line_result(line, result)
            except StudioError as exc:
                failure = self._build_failure(line, exc.message)
                failures.append(failure)
                if on_line_failure is not None:
                    on_line_failure(line, failure)
                if not continue_on_error:
                    stopped_early = True
                    break

        report = BatchReport(
            success=not stopped_early,
            stopped_early=stopped_early,
            script_path=script_path,
            output_dir=output_dir,
            total=len(lines),
            done=sum(result.status == "done" for result in results),
            skipped=sum(result.status == "skipped" for result in results),
            failed=len(failures),
            failed_ids=[failure.line_id for failure in failures],
            failures=failures,
        )
        self.storage.write_json(output_dir / "failed_lines.json", failures)
        self.storage.write_json(output_dir / "batch_report.json", report)
        return report

    def _ensure_worker_started(self) -> None:
        if self._worker_thread and self._worker_thread.is_alive():
            return
        with self._jobs_lock:
            if self._worker_thread and self._worker_thread.is_alive():
                return
            self._shutdown_event.clear()
            self._worker_thread = threading.Thread(
                target=self._worker_loop,
                name="indextts-job-worker",
                daemon=True,
            )
            self._worker_thread.start()

    def _worker_loop(self) -> None:
        while not self._shutdown_event.is_set():
            task = self._queue.get()
            if task is None:
                self._queue.task_done()
                break
            try:
                self._execute_queued_job(task)
            except Exception as exc:  # pragma: no cover - defensive worker guard
                self.logger.exception("Unexpected async job worker error", exc_info=exc)
                self._mark_job_failed(task.job_id, f"Unexpected worker error: {exc}")
            finally:
                self._queue.task_done()

    def _execute_queued_job(self, task: _QueuedBatchJob) -> None:
        self._update_job(
            task.job_id,
            status="running",
            started_at=_utc_now(),
            completed_at=None,
            stopped_early=False,
            report=None,
        )
        self.logger.info("Running async batch job %s", task.job_id)
        report = self._execute_batch(
            script_path=task.script_path,
            lines=task.lines,
            output_dir=task.output_dir,
            project_id=task.project_id,
            skip_existing=task.skip_existing,
            continue_on_error=task.continue_on_error,
            force=task.force,
            on_line_start=lambda line, output_path: self._mark_line_running(
                task.job_id, line.id, output_path
            ),
            on_line_result=lambda line, result: self._mark_line_result(
                task.job_id, line.id, result
            ),
            on_line_failure=lambda line, failure: self._mark_line_failure(
                task.job_id, line.id, failure
            ),
        )
        current_record = self.get_job(task.job_id)
        final_status = "completed"
        if report.stopped_early:
            final_status = "failed"
        elif current_record.failed > 0:
            final_status = "completed_with_errors"
        aggregate_report = self._build_report_from_record(
            current_record,
            stopped_early=report.stopped_early,
        )

        self._update_job(
            task.job_id,
            status=final_status,
            report=aggregate_report,
            stopped_early=report.stopped_early,
            completed_at=_utc_now(),
        )
        self.storage.write_json(task.output_dir / "failed_lines.json", aggregate_report.failures)
        self.storage.write_json(task.output_dir / "batch_report.json", aggregate_report)
        self.logger.info(
            "Completed async batch job %s with status %s",
            task.job_id,
            final_status,
        )

    def _mark_job_failed(self, job_id: str, message: str) -> None:
        now = _utc_now()
        with self._jobs_lock:
            record = self._jobs.get(job_id)
            if record is None:
                return
            record.status = "failed"
            record.stopped_early = True
            record.completed_at = now
            if record.lines:
                pending_line = next(
                    (line for line in record.lines if line.status in {"pending", "running"}),
                    None,
                )
                if pending_line is not None:
                    pending_line.status = "failed"
                    pending_line.error = message
                    pending_line.updated_at = now
                    pending_line.completed_at = now
            self._refresh_job_counts(record)
            record.report = self._build_report_from_record(record, stopped_early=True)
            self._persist_job_locked(record)
            self.storage.write_json(record.output_dir / "failed_lines.json", record.report.failures)
            self.storage.write_json(record.output_dir / "batch_report.json", record.report)

    def _mark_line_running(self, job_id: str, line_id: str, output_path: Path) -> None:
        now = _utc_now()
        with self._jobs_lock:
            record = self._jobs[job_id]
            line = self._find_job_line(record, line_id)
            line.status = "running"
            line.output_path = output_path
            line.error = None
            line.started_at = now
            line.updated_at = now
            self._refresh_job_counts(record)
            self._persist_job_locked(record)

    def _mark_line_result(self, job_id: str, line_id: str, result: SynthesisResult) -> None:
        now = _utc_now()
        with self._jobs_lock:
            record = self._jobs[job_id]
            line = self._find_job_line(record, line_id)
            line.status = result.status
            line.output_path = result.output_path
            line.duration_ms = result.duration_ms
            line.error = result.error
            line.updated_at = now
            line.completed_at = now
            self._refresh_job_counts(record)
            self._persist_job_locked(record)

    def _mark_line_failure(self, job_id: str, line_id: str, failure: BatchFailure) -> None:
        now = _utc_now()
        with self._jobs_lock:
            record = self._jobs[job_id]
            line = self._find_job_line(record, line_id)
            line.status = "failed"
            line.error = failure.error_message
            line.updated_at = now
            line.completed_at = now
            self._refresh_job_counts(record)
            self._persist_job_locked(record)

    def _update_job(self, job_id: str, **updates: object) -> None:
        with self._jobs_lock:
            record = self._jobs[job_id]
            for key, value in updates.items():
                setattr(record, key, value)
            self._refresh_job_counts(record)
            self._persist_job_locked(record)

    def _refresh_job_counts(self, record: JobRecord) -> None:
        record.done = sum(line.status == "done" for line in record.lines)
        record.skipped = sum(line.status == "skipped" for line in record.lines)
        record.failed = sum(line.status == "failed" for line in record.lines)
        record.failed_ids = [line.line_id for line in record.lines if line.status == "failed"]

    @staticmethod
    def _find_job_line(record: JobRecord, line_id: str) -> JobLineRecord:
        for line in record.lines:
            if line.line_id == line_id:
                return line
        raise NotFoundError(f"Line `{line_id}` does not exist in job `{record.job_id}`.")

    def _validate_output_collision(
        self,
        line: ScriptLine,
        output_path: Path,
        reserved_outputs: dict[Path, str],
    ) -> None:
        existing_owner = reserved_outputs.get(output_path)
        if existing_owner and existing_owner != line.id:
            raise OutputNameCollisionError(
                f"Line `{line.id}` resolves to an output name already used by "
                f"line `{existing_owner}`: {output_path.name}"
            )
        reserved_outputs[output_path] = line.id

    @staticmethod
    def _build_failure(line: ScriptLine, message: str) -> BatchFailure:
        return BatchFailure(
            line_id=line.id,
            speaker=line.speaker,
            text=line.text,
            error_message=message,
            timestamp=_utc_now(),
        )

    @staticmethod
    def _build_report_from_record(record: JobRecord, *, stopped_early: bool) -> BatchReport:
        failures = [
            BatchFailure(
                line_id=line.line_id,
                speaker=line.speaker,
                text=line.text,
                error_message=line.error or "Unknown job failure.",
                timestamp=line.completed_at or line.updated_at,
            )
            for line in record.lines
            if line.status == "failed"
        ]
        return BatchReport(
            success=not stopped_early,
            stopped_early=stopped_early,
            script_path=record.script_path,
            output_dir=record.output_dir,
            total=record.total,
            done=record.done,
            skipped=record.skipped,
            failed=record.failed,
            failed_ids=list(record.failed_ids),
            failures=failures,
        )

    def _job_record_path(self, job_id: str) -> Path:
        return self._jobs_dir / f"{job_id}.json"

    def _persist_job_locked(self, record: JobRecord) -> None:
        self.storage.write_json(self._job_record_path(record.job_id), record)

    def _load_persisted_jobs_locked(self) -> set[str]:
        self._jobs_dir.mkdir(parents=True, exist_ok=True)
        loaded_job_ids: set[str] = set()
        for path in sorted(self._jobs_dir.glob("*.json")):
            try:
                record = JobRecord.model_validate(self.storage.read_json(path))
            except Exception as exc:  # pragma: no cover - defensive corrupted file guard
                self.logger.warning("Skipping invalid job record %s: %s", path, exc)
                continue
            if record.job_id not in self._jobs:
                self._jobs[record.job_id] = record
                loaded_job_ids.add(record.job_id)
        return loaded_job_ids

    def _restore_resumable_tasks_locked(self, loaded_job_ids: set[str]) -> list[_QueuedBatchJob]:
        tasks: list[_QueuedBatchJob] = []
        queued_statuses = {"queued", "running"}
        resumable_jobs = [
            record
            for record in self._jobs.values()
            if record.job_id in loaded_job_ids and record.status in queued_statuses
        ]
        resumable_jobs.sort(key=lambda item: item.created_at)

        for record in resumable_jobs:
            now = _utc_now()
            if record.status == "running":
                for line in record.lines:
                    if line.status == "running":
                        line.status = "pending"
                        line.output_path = None
                        line.duration_ms = 0
                        line.error = None
                        line.started_at = None
                        line.completed_at = None
                        line.updated_at = now

            record.status = "queued"
            record.started_at = None
            record.completed_at = None
            record.stopped_early = False
            record.report = None
            self._refresh_job_counts(record)

            pending_lines = [
                line
                for line in record.lines
                if line.status == "pending"
            ]

            if not pending_lines:
                if record.failed > 0:
                    record.status = "completed_with_errors"
                else:
                    record.status = "completed"
                record.completed_at = now
                record.report = self._build_report_from_record(record, stopped_early=False)
                self._persist_job_locked(record)
                continue

            self._persist_job_locked(record)
            tasks.append(
                _QueuedBatchJob(
                    job_id=record.job_id,
                    script_path=record.script_path,
                    output_dir=record.output_dir,
                    project_id=record.project_id,
                    lines=[self._to_script_line(item) for item in pending_lines],
                    skip_existing=record.skip_existing,
                    continue_on_error=record.continue_on_error,
                    force=record.force,
                )
            )

        return tasks

    @staticmethod
    def _to_script_line(line: JobLineRecord) -> ScriptLine:
        return ScriptLine(
            id=line.line_id,
            scene=line.scene,
            speaker=line.speaker,
            text=line.text,
            output_name=line.output_name,
            override=line.override,
            start_ms=line.start_ms,
            end_ms=line.end_ms,
        )

    def _resolve_output_dir(
        self,
        script_path: Path,
        *,
        project_id: str | None,
        episode_id: str | None,
    ) -> Path:
        if project_id:
            return self.project_service.episode_output_dir(project_id, episode_id)
        return self.storage.script_output_dir(script_path)

    def _inline_script_dir(
        self,
        *,
        project_id: str | None,
        episode_id: str | None,
    ) -> Path | None:
        if not project_id:
            return None
        project_paths = self.project_service.project_paths(project_id)
        if episode_id:
            return project_paths.scripts_dir / self.storage.sanitize_fragment(
                episode_id,
                default="episode",
            )
        return project_paths.scripts_dir / "drafts"
