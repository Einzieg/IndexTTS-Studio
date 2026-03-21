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
