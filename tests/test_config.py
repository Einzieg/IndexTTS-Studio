from __future__ import annotations

from app.core import config as config_module


def test_load_settings_from_dotenv_file(monkeypatch, tmp_path) -> None:
    for key in [
        "INDEXTTS_STUDIO_ENV_FILE",
        "INDEXTTS_STUDIO_ROOT",
        "INDEXTTS_STUDIO_DATA_DIR",
        "INDEXTTS_STUDIO_BACKEND",
        "INDEXTTS_STUDIO_GRADIO_BASE_URL",
        "INDEXTTS_STUDIO_PORT",
    ]:
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
    assert settings.model.backend == "mock"
    assert settings.model.gradio_base_url == "http://127.0.0.1:9999"
    assert settings.api.port == 8123
