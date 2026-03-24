from __future__ import annotations

from dataclasses import dataclass

from app.core.config import AppSettings, get_settings
from app.core.logger import configure_logging, get_logger
from app.infra.indextts_adapter import IndexTTSAdapter, RemoteGradioAdapter, TTSAdapter
from app.infra.storage import StorageService
from app.services.audio_service import AudioService
from app.services.job_service import JobService
from app.services.project_service import ProjectService
from app.services.script_service import ScriptService
from app.services.speaker_service import SpeakerService
from app.services.studio_table_service import StudioTableService
from app.services.tts_service import TTSService


@dataclass(slots=True)
class ServiceContainer:
    settings: AppSettings
    storage: StorageService
    project_service: ProjectService
    speaker_service: SpeakerService
    script_service: ScriptService
    studio_table_service: StudioTableService
    tts_service: TTSService
    job_service: JobService
    audio_service: AudioService
    adapter: TTSAdapter
    initialized: bool = False
    jobs_initialized: bool = False

    def initialize(self, *, resume_jobs: bool = False) -> None:
        if self.initialized:
            if resume_jobs and not self.jobs_initialized:
                self.job_service.initialize()
                self.jobs_initialized = True
            return
        self.settings.ensure_runtime_dirs()
        logger = get_logger("indextts_studio")
        logger.info("Loaded runtime configuration from %s", self.settings.env_file)
        logger.info("Runtime directories prepared under %s", self.settings.paths.data_dir)
        if resume_jobs:
            self.job_service.initialize()
            self.jobs_initialized = True
        if self.settings.model.warmup_on_startup:
            logger.info(
                "Warming up TTS backend `%s` during startup.",
                self.settings.model.backend,
            )
            self.adapter.warmup()
        self.initialized = True

    def shutdown(self) -> None:
        self.job_service.shutdown()


def build_container(
    settings: AppSettings | None = None,
    *,
    adapter: TTSAdapter | None = None,
) -> ServiceContainer:
    app_settings = settings or get_settings()
    configure_logging(app_settings.paths.logs_dir, app_settings.log_level)

    storage = StorageService(app_settings)
    project_service = ProjectService(app_settings, storage)
    project_service.ensure_runtime_dirs()
    speaker_service = SpeakerService(app_settings, storage, project_service)
    script_service = ScriptService(storage)
    studio_table_service = StudioTableService(storage, project_service)
    if adapter is not None:
        active_adapter = adapter
    elif app_settings.model.backend == "remote_gradio":
        active_adapter = RemoteGradioAdapter(app_settings)
    else:
        active_adapter = IndexTTSAdapter(app_settings)
    tts_service = TTSService(
        app_settings,
        storage,
        speaker_service,
        project_service,
        active_adapter,
    )
    job_service = JobService(storage, project_service, script_service, tts_service)
    audio_service = AudioService(storage, script_service, tts_service)
    return ServiceContainer(
        settings=app_settings,
        storage=storage,
        project_service=project_service,
        speaker_service=speaker_service,
        script_service=script_service,
        studio_table_service=studio_table_service,
        tts_service=tts_service,
        job_service=job_service,
        audio_service=audio_service,
        adapter=active_adapter,
    )
