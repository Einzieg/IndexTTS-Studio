from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.container import ServiceContainer
from app.main import create_app


def test_ui_support_endpoints(container: ServiceContainer) -> None:
    batch_report = container.job_service.run_batch(
        script_path="data/scripts/episode1.csv",
        force=True,
    )
    sample_audio = batch_report.output_dir / "001_0001_主角A.wav"

    with TestClient(create_app(container)) as client:
        scripts_response = client.get("/scripts")
        assert scripts_response.status_code == 200
        scripts = scripts_response.json()["data"]["items"]
        assert any(item["path"] == "data/scripts/episode1.csv" for item in scripts)

        preview_response = client.get(
            "/scripts/preview",
            params={"script_path": "data/scripts/episode1.srt"},
        )
        assert preview_response.status_code == 200
        preview = preview_response.json()["data"]
        assert preview["has_timeline"] is True
        assert len(preview["items"]) == 3

        audio_response = client.get(
            "/files/audio",
            params={"path": str(sample_audio)},
        )
        assert audio_response.status_code == 200
        assert audio_response.headers["content-type"] == "audio/wav"

        ui_response = client.get("/ui")
        assert ui_response.status_code == 200


def test_script_preview_rejects_paths_outside_managed_scripts(
    container: ServiceContainer,
    studio_root,
) -> None:
    outside_script = studio_root / "outside.csv"
    outside_script.write_text(
        "id,scene,speaker,text\n1,001,主角A,outside script\n",
        encoding="utf-8",
    )

    with TestClient(create_app(container)) as client:
        response = client.get(
            "/scripts/preview",
            params={"script_path": str(outside_script)},
        )

        assert response.status_code == 422
        assert response.json()["success"] is False
        assert "managed scripts directory" in response.json()["message"]


def test_script_preview_returns_422_for_invalid_script_line(
    container: ServiceContainer,
) -> None:
    bad_script = container.settings.paths.scripts_dir / "bad_timing.json"
    bad_script.write_text(
        (
            "{\n"
            '  "items": [\n'
            '    {"id": "1", "speaker": "主角A", "text": "bad timing", "start_ms": "bad"}\n'
            "  ]\n"
            "}\n"
        ),
        encoding="utf-8",
    )

    with TestClient(create_app(container)) as client:
        response = client.get(
            "/scripts/preview",
            params={"script_path": str(bad_script)},
        )

        assert response.status_code == 422
        assert response.json()["success"] is False
        assert "Invalid script line `1`" in response.json()["message"]
