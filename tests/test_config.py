from __future__ import annotations

from app.core import config as config_module


CONFIG_ENV_KEYS = [
    "INDEXTTS_STUDIO_ENV_FILE",
    "INDEXTTS_STUDIO_ROOT",
    "INDEXTTS_STUDIO_DATA_DIR",
    "INDEXTTS_STUDIO_SPEAKERS_FILE",
    "INDEXTTS_STUDIO_SCRIPTS_DIR",
    "INDEXTTS_STUDIO_REFS_DIR",
    "INDEXTTS_STUDIO_OUTPUTS_DIR",
    "INDEXTTS_STUDIO_LOGS_DIR",
    "INDEXTTS_STUDIO_JOBS_DIR",
    "INDEXTTS_STUDIO_BACKEND",
    "INDEXTTS_STUDIO_GRADIO_BASE_URL",
    "INDEXTTS_STUDIO_PORT",
    "INDEXTTS_STUDIO_MAX_SCRIPT_LINE_TEXT_CHARS",
    "INDEXTTS_STUDIO_AUTH_ENABLED",
    "INDEXTTS_STUDIO_AUTH_USERNAME",
    "INDEXTTS_STUDIO_AUTH_PASSWORD",
    "INDEXTTS_STUDIO_AUTH_SESSION_SECRET",
]


def test_load_settings_from_dotenv_file(monkeypatch, tmp_path) -> None:
    for key in CONFIG_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    env_file = tmp_path / "custom.env"
    env_file.write_text(
        "\n".join(
            [
                f"INDEXTTS_STUDIO_ROOT={tmp_path}",
                "INDEXTTS_STUDIO_DATA_DIR=runtime_data",
                "INDEXTTS_STUDIO_BACKEND=mock",
                "INDEXTTS_STUDIO_GRADIO_BASE_URL=http://127.0.0.1:9999",
                "INDEXTTS_STUDIO_PORT=8123",
                "INDEXTTS_STUDIO_MAX_SCRIPT_LINE_TEXT_CHARS=42",
                "INDEXTTS_STUDIO_AUTH_ENABLED=true",
                "INDEXTTS_STUDIO_AUTH_USERNAME=tester",
                "INDEXTTS_STUDIO_AUTH_PASSWORD=secret123",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("INDEXTTS_STUDIO_ENV_FILE", str(env_file))
    config_module._load_dotenv(env_file)

    settings = config_module.load_settings()

    assert settings.env_file == env_file
    assert settings.paths.project_root == tmp_path
    assert settings.paths.data_dir == (tmp_path / "runtime_data")
    assert settings.paths.jobs_dir == (tmp_path / "runtime_data" / "jobs")
    assert settings.model.backend == "mock"
    assert settings.model.gradio_base_url == "http://127.0.0.1:9999"
    assert settings.api.port == 8123
    assert settings.max_script_line_text_chars == 42
    assert settings.auth.enabled is True
    assert settings.auth.username == "tester"
    assert settings.auth.password == "secret123"


def test_blank_child_paths_follow_data_dir_and_blank_auth_secret_is_random(
    monkeypatch,
    tmp_path,
) -> None:
    for key in CONFIG_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    generated_secrets = iter(["generated-secret-one", "generated-secret-two"])
    monkeypatch.setattr(
        config_module.secrets,
        "token_urlsafe",
        lambda _: next(generated_secrets),
    )
    monkeypatch.setenv("INDEXTTS_STUDIO_ENV_FILE", str(tmp_path / "missing.env"))
    monkeypatch.setenv("INDEXTTS_STUDIO_ROOT", str(tmp_path))
    monkeypatch.setenv("INDEXTTS_STUDIO_DATA_DIR", "runtime")
    monkeypatch.setenv("INDEXTTS_STUDIO_SPEAKERS_FILE", "")
    monkeypatch.setenv("INDEXTTS_STUDIO_SCRIPTS_DIR", "")
    monkeypatch.setenv("INDEXTTS_STUDIO_REFS_DIR", "")
    monkeypatch.setenv("INDEXTTS_STUDIO_OUTPUTS_DIR", "")
    monkeypatch.setenv("INDEXTTS_STUDIO_LOGS_DIR", "")
    monkeypatch.setenv("INDEXTTS_STUDIO_JOBS_DIR", "")
    monkeypatch.setenv("INDEXTTS_STUDIO_AUTH_ENABLED", "true")
    monkeypatch.setenv("INDEXTTS_STUDIO_AUTH_USERNAME", "tester")
    monkeypatch.setenv("INDEXTTS_STUDIO_AUTH_PASSWORD", "secret123")
    monkeypatch.setenv("INDEXTTS_STUDIO_AUTH_SESSION_SECRET", "")

    settings = config_module.load_settings()
    second_settings = config_module.load_settings()

    data_dir = tmp_path / "runtime"
    assert settings.paths.data_dir == data_dir
    assert settings.paths.speakers_file == data_dir / "speakers.json"
    assert settings.paths.scripts_dir == data_dir / "scripts"
    assert settings.paths.refs_dir == data_dir / "refs"
    assert settings.paths.outputs_dir == data_dir / "outputs"
    assert settings.paths.logs_dir == data_dir / "logs"
    assert settings.paths.jobs_dir == data_dir / "jobs"
    assert settings.max_script_line_text_chars == 60
    assert settings.auth.session_secret == "generated-secret-one"
    assert second_settings.auth.session_secret == "generated-secret-two"
