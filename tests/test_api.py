from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.container import ServiceContainer
from app.domain.models import MAX_SCRIPT_LINE_TEXT_CHARS
from app.main import create_app


def test_api_endpoints(container: ServiceContainer) -> None:
    with TestClient(create_app(container)) as client:
        root_response = client.get("/", follow_redirects=False)
        assert root_response.status_code == 307
        assert root_response.headers["location"] == "/ui"

        health_response = client.get("/health")
        assert health_response.status_code == 200
        assert health_response.json()["data"]["status"] == "ok"
        assert (
            health_response.json()["data"]["max_script_line_text_chars"]
            == container.settings.max_script_line_text_chars
        )

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


def test_single_tts_rejects_overlong_text(container: ServiceContainer) -> None:
    with TestClient(create_app(container)) as client:
        response = client.post(
            "/tts/single",
            json={
                "speaker": "主角A",
                "text": "长" * (MAX_SCRIPT_LINE_TEXT_CHARS + 1),
                "output_name": "too_long.wav",
                "force": True,
            },
        )

        assert response.status_code == 422
        assert response.json()["success"] is False
        assert f"单行台词最多 {MAX_SCRIPT_LINE_TEXT_CHARS} 字" in response.json()["message"]


def test_single_tts_uses_configured_line_limit(container: ServiceContainer) -> None:
    container.settings.max_script_line_text_chars = 5

    with TestClient(create_app(container)) as client:
        health_response = client.get("/health")
        response = client.post(
            "/tts/single",
            json={
                "speaker": "主角A",
                "text": "长" * 6,
                "output_name": "too_long_custom.wav",
                "force": True,
            },
        )

        assert health_response.status_code == 200
        assert health_response.json()["data"]["max_script_line_text_chars"] == 5
        assert response.status_code == 422
        assert response.json()["success"] is False
        assert "单行台词最多 5 字" in response.json()["message"]
