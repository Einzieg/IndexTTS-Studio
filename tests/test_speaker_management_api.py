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


def test_speaker_management_api_copies_profile_between_projects(
    container: ServiceContainer,
) -> None:
    ref_audio_path = container.settings.paths.refs_dir / "hero_a.wav"

    with TestClient(create_app(container)) as client:
        source_response = client.post("/projects", json={"name": "Source Project"})
        target_response = client.post("/projects", json={"name": "Target Project"})
        assert source_response.status_code == 200
        assert target_response.status_code == 200
        source_project = source_response.json()["data"]
        target_project = target_response.json()["data"]

        create_response = client.post(
            "/speakers",
            data={
                "project_id": source_project["id"],
                "name": "可复用角色",
                "temperature": "0.72",
            },
            files={"ref_audio": ("copy_source.wav", ref_audio_path.read_bytes(), "audio/wav")},
        )
        assert create_response.status_code == 200
        source_profile = create_response.json()["data"]

        copy_response = client.post(
            "/speakers/copy",
            json={
                "source_project_id": source_project["id"],
                "target_project_id": target_project["id"],
                "speaker_names": ["可复用角色"],
            },
        )
        assert copy_response.status_code == 200
        copied_profile = copy_response.json()["data"]["items"][0]
        assert copied_profile["name"] == "可复用角色"
        assert copied_profile["options"]["temperature"] == 0.72
        assert copied_profile["ref_audio"] != source_profile["ref_audio"]
        assert f"data/projects/{target_project['id']}/refs/" in copied_profile["ref_audio"]
        assert container.settings.paths.project_root.joinpath(copied_profile["ref_audio"]).exists()

        target_profiles_response = client.get(
            "/speakers/profiles",
            params={"project_id": target_project["id"]},
        )
        assert target_profiles_response.status_code == 200
        target_profiles = target_profiles_response.json()["data"]["items"]
        assert [item["name"] for item in target_profiles] == ["可复用角色"]
