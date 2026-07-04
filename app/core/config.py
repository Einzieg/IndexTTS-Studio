from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Literal


DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE_NAME = ".env"


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


def _resolve_path(value: str | None, *, root: Path, default: Path) -> Path:
    if value is None or not value.strip():
        candidate = default
    else:
        candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    return (root / candidate).resolve()


def _strip_optional_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = _strip_optional_quotes(raw_value.strip())
        os.environ[key] = value


def _bootstrap_env() -> Path:
    default_root = Path(os.getenv("INDEXTTS_STUDIO_ROOT", DEFAULT_PROJECT_ROOT)).resolve()
    env_file_value = os.getenv("INDEXTTS_STUDIO_ENV_FILE")
    env_file_path = _resolve_path(
        env_file_value,
        root=default_root,
        default=Path(DEFAULT_ENV_FILE_NAME),
    )
    _load_dotenv(env_file_path)
    return env_file_path


LOADED_ENV_FILE = _bootstrap_env()


@dataclass(slots=True)
class ApiSettings:
    host: str = "127.0.0.1"
    port: int = 8000


@dataclass(slots=True)
class AuthSettings:
    enabled: bool = False
    username: str = ""
    password: str = ""
    session_secret: str = ""
    session_cookie_name: str = "indextts_studio_session"
    session_ttl_seconds: int = 43_200
    secure_cookie: bool = False
    same_site: Literal["lax", "strict", "none"] = "lax"


@dataclass(slots=True)
class GenerationDefaults:
    temperature: float = 0.8
    top_p: float = 0.8
    top_k: int = 30
    max_mel_tokens: int = 600
    repetition_penalty: float = 10.0
    length_penalty: float = 1.0
    num_beams: int = 3
    use_random: bool = True

    def as_dict(self) -> dict[str, object]:
        return {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "max_mel_tokens": self.max_mel_tokens,
            "repetition_penalty": self.repetition_penalty,
            "length_penalty": self.length_penalty,
            "num_beams": self.num_beams,
            "use_random": self.use_random,
        }


@dataclass(slots=True)
class ModelSettings:
    backend: Literal["official", "mock", "remote_gradio"] = "official"
    package_root: Path | None = None
    cfg_path: Path = Path("checkpoints/config.yaml")
    model_dir: Path = Path("checkpoints")
    use_fp16: bool = False
    use_cuda_kernel: bool = False
    use_deepspeed: bool = False
    warmup_on_startup: bool = True
    gradio_base_url: str = "http://127.0.0.1:7861"
    gradio_api_prefix: str = "/gradio_api"
    gradio_api_name: str = "/gen_single"
    gradio_request_timeout_seconds: int = 300
    gradio_stream_timeout_seconds: int = 1_800
    gradio_retry_attempts: int = 3
    gradio_retry_backoff_seconds: int = 2


@dataclass(slots=True)
class PathSettings:
    project_root: Path
    data_dir: Path
    speakers_file: Path
    scripts_dir: Path
    refs_dir: Path
    outputs_dir: Path
    logs_dir: Path
    jobs_dir: Path


@dataclass(slots=True)
class AppSettings:
    paths: PathSettings
    api: ApiSettings = field(default_factory=ApiSettings)
    auth: AuthSettings = field(default_factory=AuthSettings)
    generation: GenerationDefaults = field(default_factory=GenerationDefaults)
    model: ModelSettings = field(default_factory=ModelSettings)
    max_script_line_text_chars: int = 60
    log_level: str = "INFO"
    env_file: Path = LOADED_ENV_FILE

    def ensure_runtime_dirs(self) -> None:
        self.paths.data_dir.mkdir(parents=True, exist_ok=True)
        self.paths.scripts_dir.mkdir(parents=True, exist_ok=True)
        self.paths.refs_dir.mkdir(parents=True, exist_ok=True)
        self.paths.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.paths.logs_dir.mkdir(parents=True, exist_ok=True)
        self.paths.jobs_dir.mkdir(parents=True, exist_ok=True)


def load_settings() -> AppSettings:
    project_root = Path(
        os.getenv("INDEXTTS_STUDIO_ROOT", DEFAULT_PROJECT_ROOT)
    ).resolve()
    env_file = _resolve_path(
        os.getenv("INDEXTTS_STUDIO_ENV_FILE"),
        root=project_root,
        default=Path(DEFAULT_ENV_FILE_NAME),
    )
    data_dir = _resolve_path(
        os.getenv("INDEXTTS_STUDIO_DATA_DIR"),
        root=project_root,
        default=Path("data"),
    )

    paths = PathSettings(
        project_root=project_root,
        data_dir=data_dir,
        speakers_file=_resolve_path(
            os.getenv("INDEXTTS_STUDIO_SPEAKERS_FILE"),
            root=project_root,
            default=data_dir / "speakers.json",
        ),
        scripts_dir=_resolve_path(
            os.getenv("INDEXTTS_STUDIO_SCRIPTS_DIR"),
            root=project_root,
            default=data_dir / "scripts",
        ),
        refs_dir=_resolve_path(
            os.getenv("INDEXTTS_STUDIO_REFS_DIR"),
            root=project_root,
            default=data_dir / "refs",
        ),
        outputs_dir=_resolve_path(
            os.getenv("INDEXTTS_STUDIO_OUTPUTS_DIR"),
            root=project_root,
            default=data_dir / "outputs",
        ),
        logs_dir=_resolve_path(
            os.getenv("INDEXTTS_STUDIO_LOGS_DIR"),
            root=project_root,
            default=data_dir / "logs",
        ),
        jobs_dir=_resolve_path(
            os.getenv("INDEXTTS_STUDIO_JOBS_DIR"),
            root=project_root,
            default=data_dir / "jobs",
        ),
    )

    model_package_root = os.getenv("INDEXTTS_STUDIO_INDEXTTS_PACKAGE_ROOT")
    model = ModelSettings(
        backend=os.getenv("INDEXTTS_STUDIO_BACKEND", "official").strip().lower(),  # type: ignore[arg-type]
        package_root=_resolve_path(
            model_package_root,
            root=project_root,
            default=Path("."),
        )
        if model_package_root
        else None,
        cfg_path=_resolve_path(
            os.getenv("INDEXTTS_STUDIO_MODEL_CFG"),
            root=project_root,
            default=Path("checkpoints/config.yaml"),
        ),
        model_dir=_resolve_path(
            os.getenv("INDEXTTS_STUDIO_MODEL_DIR"),
            root=project_root,
            default=Path("checkpoints"),
        ),
        use_fp16=_parse_bool(os.getenv("INDEXTTS_STUDIO_USE_FP16"), False),
        use_cuda_kernel=_parse_bool(
            os.getenv("INDEXTTS_STUDIO_USE_CUDA_KERNEL"), False
        ),
        use_deepspeed=_parse_bool(os.getenv("INDEXTTS_STUDIO_USE_DEEPSPEED"), False),
        warmup_on_startup=_parse_bool(
            os.getenv("INDEXTTS_STUDIO_WARMUP_ON_STARTUP"), True
        ),
        gradio_base_url=os.getenv(
            "INDEXTTS_STUDIO_GRADIO_BASE_URL",
            "http://127.0.0.1:7861",
        ).rstrip("/"),
        gradio_api_prefix=os.getenv(
            "INDEXTTS_STUDIO_GRADIO_API_PREFIX",
            "/gradio_api",
        ).rstrip("/"),
        gradio_api_name=os.getenv(
            "INDEXTTS_STUDIO_GRADIO_API_NAME",
            "/gen_single",
        ),
        gradio_request_timeout_seconds=max(
            _parse_int(
                os.getenv("INDEXTTS_STUDIO_GRADIO_REQUEST_TIMEOUT_SECONDS"),
                300,
            ),
            1,
        ),
        gradio_stream_timeout_seconds=max(
            _parse_int(
                os.getenv("INDEXTTS_STUDIO_GRADIO_STREAM_TIMEOUT_SECONDS"),
                1_800,
            ),
            1,
        ),
        gradio_retry_attempts=max(
            _parse_int(
                os.getenv("INDEXTTS_STUDIO_GRADIO_RETRY_ATTEMPTS"),
                3,
            ),
            1,
        ),
        gradio_retry_backoff_seconds=max(
            _parse_int(
                os.getenv("INDEXTTS_STUDIO_GRADIO_RETRY_BACKOFF_SECONDS"),
                2,
            ),
            0,
        ),
    )

    api = ApiSettings(
        host=os.getenv("INDEXTTS_STUDIO_HOST", "127.0.0.1"),
        port=int(os.getenv("INDEXTTS_STUDIO_PORT", "8000")),
    )

    auth_username = os.getenv("INDEXTTS_STUDIO_AUTH_USERNAME", "").strip()
    auth_password = os.getenv("INDEXTTS_STUDIO_AUTH_PASSWORD", "")
    auth_enabled_env = os.getenv("INDEXTTS_STUDIO_AUTH_ENABLED")
    auth_enabled = (
        _parse_bool(auth_enabled_env, False)
        if auth_enabled_env is not None
        else bool(auth_username and auth_password)
    )
    auth_secret = os.getenv("INDEXTTS_STUDIO_AUTH_SESSION_SECRET", "").strip()
    if auth_enabled and not auth_secret:
        auth_secret = secrets.token_urlsafe(32)
    auth_same_site = os.getenv("INDEXTTS_STUDIO_AUTH_SAME_SITE", "lax").strip().lower()
    if auth_same_site not in {"lax", "strict", "none"}:
        auth_same_site = "lax"

    auth = AuthSettings(
        enabled=auth_enabled,
        username=auth_username,
        password=auth_password,
        session_secret=auth_secret,
        session_cookie_name=os.getenv(
            "INDEXTTS_STUDIO_AUTH_COOKIE_NAME",
            "indextts_studio_session",
        ).strip()
        or "indextts_studio_session",
        session_ttl_seconds=_parse_int(
            os.getenv("INDEXTTS_STUDIO_AUTH_SESSION_TTL_SECONDS"),
            43_200,
        ),
        secure_cookie=_parse_bool(
            os.getenv("INDEXTTS_STUDIO_AUTH_SECURE_COOKIE"),
            False,
        ),
        same_site=auth_same_site,  # type: ignore[arg-type]
    )

    settings = AppSettings(
        paths=paths,
        api=api,
        auth=auth,
        model=model,
        max_script_line_text_chars=max(
            1,
            _parse_int(os.getenv("INDEXTTS_STUDIO_MAX_SCRIPT_LINE_TEXT_CHARS"), 60),
        ),
        log_level=os.getenv("INDEXTTS_STUDIO_LOG_LEVEL", "INFO").upper(),
        env_file=env_file,
    )
    settings.ensure_runtime_dirs()
    return settings


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return load_settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
