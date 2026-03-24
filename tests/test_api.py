from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.container import ServiceContainer
from app.main import create_app


def test_api_endpoints(container: ServiceContainer) -> None:
    with TestClient(create_app(container)) as client:
        root_response = client.get("/", follow_redirects=False)
        assert root_response.status_code == 307
        assert root_response.headers["location"] == "/ui"

        health_response = client.get("/health")
        assert health_response.status_code == 200
        assert health_response.json()["data"]["status"] == "ok"

        speakers_response = client.get("/speakers")
        assert speakers_response.status_code == 200
        assert speakers_response.json()["data"]["items"] == ["主角A", "反派B", "旁白"]

        single_response = client.post(
            "/tts/single",
            json={
                "speaker": "主角A",
                "text": "API 单句测试。",
                "output_name": "api_single.wav",
                "force": True,
            },
        )
        assert single_response.status_code == 200
        assert single_response.json()["data"]["status"] == "done"

        batch_response = client.post(
            "/tts/batch",
            json={
                "script_path": "data/scripts/episode1.csv",
                "skip_existing": True,
                "continue_on_error": True,
            },
        )
        assert batch_response.status_code == 200
        assert batch_response.json()["data"]["total"] == 3

        regenerate_response = client.post(
            "/tts/regenerate",
            json={
                "script_path": "data/scripts/episode1.csv",
                "line_id": "2",
                "force": True,
            },
        )
        assert regenerate_response.status_code == 200
        assert regenerate_response.json()["data"]["line_id"] == "2"
