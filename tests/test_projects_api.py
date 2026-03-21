from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.container import ServiceContainer
from app.main import create_app


def test_projects_api_creates_project_and_episode(container: ServiceContainer) -> None:
    with TestClient(create_app(container)) as client:
        create_response = client.post(
            "/projects",
            json={
                "project_id": "ignored_custom_project_id",
                "name": "Drama Alpha",
                "description": "Main production project",
            },
        )
        assert create_response.status_code == 200
        project = create_response.json()["data"]
        assert project["id"] == "drama_alpha"
        assert project["name"] == "Drama Alpha"

        episode_response = client.post(
            f"/projects/{project['id']}/episodes",
            json={
                "episode_id": "ignored_custom_episode_id",
                "name": "Episode 01",
                "description": "Opening sequence",
            },
        )
        assert episode_response.status_code == 200
        episode_project = episode_response.json()["data"]
        assert episode_project["episodes"][0]["id"] == "episode_01"

        list_response = client.get("/projects")
        assert list_response.status_code == 200
        items = list_response.json()["data"]["items"]
        assert any(item["id"] == project["id"] for item in items)


def test_project_scoped_speakers_and_outputs_are_isolated(container: ServiceContainer) -> None:
    ref_audio_path = container.settings.paths.refs_dir / "hero_a.wav"

    with TestClient(create_app(container)) as client:
        project_response = client.post(
            "/projects",
            json={
                "name": "Drama Alpha",
            },
        )
        assert project_response.status_code == 200
        project = project_response.json()["data"]

        episode_response = client.post(
            f"/projects/{project['id']}/episodes",
            json={
                "name": "Episode 01",
            },
        )
        assert episode_response.status_code == 200
        episode_id = episode_response.json()["data"]["episodes"][0]["id"]

        save_speaker_response = client.post(
            "/speakers",
            data={
                "project_id": project["id"],
                "name": "项目主角",
            },
            files={"ref_audio": ("hero.wav", ref_audio_path.read_bytes(), "audio/wav")},
        )
        assert save_speaker_response.status_code == 200

        scoped_profiles_response = client.get("/speakers/profiles", params={"project_id": project["id"]})
        assert scoped_profiles_response.status_code == 200
        scoped_profiles = scoped_profiles_response.json()["data"]["items"]
        assert [item["name"] for item in scoped_profiles] == ["项目主角"]

        synthesis_response = client.post(
            "/tts/single",
            json={
                "project_id": project["id"],
                "episode_id": episode_id,
                "speaker": "项目主角",
                "text": "这一句要生成到项目的分集目录里。",
                "output_name": "line_001.wav",
                "force": True,
            },
        )
        assert synthesis_response.status_code == 200
        result = synthesis_response.json()["data"]
        assert (
            f"data/projects/{project['id']}/outputs/{episode_id}/line_001.wav"
            in result["output_path"].replace("\\", "/")
        )
