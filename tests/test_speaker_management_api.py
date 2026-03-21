from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.core.container import ServiceContainer
from app.main import create_app


def test_speaker_management_api_creates_profile(container: ServiceContainer) -> None:
    ref_audio_path = container.settings.paths.refs_dir / "hero_a.wav"

    with TestClient(create_app(container)) as client:
        response = client.post(
            "/speakers",
            data={
                "name": "测试角色",
                "temperature": "0.65",
                "top_k": "24",
                "use_random": "false",
                "emo_vector": json.dumps([0.1, 0.2, 0.3]),
            },
            files={"ref_audio": ("test_ref.wav", ref_audio_path.read_bytes(), "audio/wav")},
        )

        assert response.status_code == 200
        profile = response.json()["data"]
        assert profile["name"] == "测试角色"
        assert profile["options"]["temperature"] == 0.65
        assert profile["options"]["top_k"] == 24
        assert profile["options"]["use_random"] is False
        assert profile["options"]["emo_vector"] == [0.1, 0.2, 0.3]

        profiles_response = client.get("/speakers/profiles")
        assert profiles_response.status_code == 200
        profiles = profiles_response.json()["data"]["items"]
        assert any(item["name"] == "测试角色" for item in profiles)


def test_speaker_management_api_deletes_profile(container: ServiceContainer) -> None:
    ref_audio_path = container.settings.paths.refs_dir / "hero_a.wav"

    with TestClient(create_app(container)) as client:
        create_response = client.post(
            "/speakers",
            data={"name": "可删除角色"},
            files={"ref_audio": ("delete_me.wav", ref_audio_path.read_bytes(), "audio/wav")},
        )
        assert create_response.status_code == 200

        delete_response = client.delete("/speakers/%E5%8F%AF%E5%88%A0%E9%99%A4%E8%A7%92%E8%89%B2")
        assert delete_response.status_code == 200
        assert delete_response.json()["data"]["name"] == "可删除角色"

        profiles_response = client.get("/speakers/profiles")
        assert profiles_response.status_code == 200
        profiles = profiles_response.json()["data"]["items"]
        assert all(item["name"] != "可删除角色" for item in profiles)

        assert not (container.settings.paths.refs_dir / "可删除角色").exists()
