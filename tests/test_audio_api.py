from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.container import ServiceContainer
from app.main import create_app


def _write_srt_script(path: Path, speakers: list[str]) -> None:
    path.write_text(
        "\n".join(
            [
                "1",
                "00:00:00,000 --> 00:00:00,800",
                f"{speakers[0]}: API timeline one.",
                "",
                "2",
                "00:00:01,000 --> 00:00:01,900",
                f"[{speakers[1]}]",
                "API timeline two.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_audio_api_merge_endpoints(container: ServiceContainer) -> None:
    with TestClient(create_app(container)) as client:
        batch_response = client.post(
            "/tts/batch",
            json={
                "script_path": "data/scripts/episode1.csv",
                "skip_existing": False,
                "continue_on_error": True,
                "force": True,
            },
        )
        assert batch_response.status_code == 200

        capabilities_response = client.get("/audio/capabilities")
        assert capabilities_response.status_code == 200
        assert capabilities_response.json()["data"] == {
            "merge_segments": True,
            "timeline_alignment": True,
            "preview_mixdown": True,
        }

        merge_response = client.post(
            "/audio/merge",
            json={
                "script_path": "data/scripts/episode1.csv",
                "gap_ms": 150,
                "force": True,
            },
        )
        assert merge_response.status_code == 200
        payload = merge_response.json()["data"]
        assert payload["mode"] == "sequence"
        assert payload["segment_count"] == 3
        assert payload["gap_ms"] == 150
        assert payload["tail_padding_ms"] == 0
        assert payload["output_path"].endswith("episode1_preview.wav")
        assert len(payload["source_paths"]) == 3


def test_audio_api_timeline_merge_endpoint(container: ServiceContainer) -> None:
    speakers = container.speaker_service.list_speakers()
    srt_path = container.settings.paths.scripts_dir / "api_timeline_episode.srt"
    _write_srt_script(srt_path, speakers)

    with TestClient(create_app(container)) as client:
        batch_response = client.post(
            "/tts/batch",
            json={
                "script_path": str(srt_path),
                "skip_existing": False,
                "continue_on_error": True,
                "force": True,
            },
        )
        assert batch_response.status_code == 200

        merge_response = client.post(
            "/audio/merge",
            json={
                "script_path": str(srt_path),
                "use_timeline": True,
                "tail_padding_ms": 180,
                "force": True,
            },
        )
        assert merge_response.status_code == 200
        payload = merge_response.json()["data"]
        assert payload["mode"] == "timeline"
        assert payload["gap_ms"] == 0
        assert payload["tail_padding_ms"] == 180
        assert payload["segment_count"] == 2
        assert payload["duration_ms"] > 0
        assert payload["output_path"].endswith("api_timeline_episode_preview.wav")
