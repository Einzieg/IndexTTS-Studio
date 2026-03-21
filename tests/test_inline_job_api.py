from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.core.container import ServiceContainer
from app.main import create_app


def test_inline_job_api_queues_page_authored_lines(container: ServiceContainer) -> None:
    with TestClient(create_app(container)) as client:
        response = client.post(
            "/jobs/from-lines",
            json={
                "title": "页面脚本",
                "force": True,
                "lines": [
                    {"speaker": "主角A", "text": "这是第一句。", "scene": "web"},
                    {"speaker": "旁白", "text": "这是第二句。", "scene": "web"},
                ],
            },
        )

        assert response.status_code == 200
        job = response.json()["data"]
        assert job["total"] == 2
        assert job["script_path"].endswith(".json")

        job_id = job["job_id"]
        deadline = time.time() + 3
        while time.time() < deadline:
            job_response = client.get(f"/jobs/{job_id}")
            assert job_response.status_code == 200
            payload = job_response.json()["data"]
            if payload["status"] in {"completed", "completed_with_errors", "failed"}:
                break
            time.sleep(0.05)
        else:
            raise AssertionError("Inline job did not complete in time.")

        assert payload["status"] == "completed"

        lines_response = client.get(f"/jobs/{job_id}/lines")
        assert lines_response.status_code == 200
        lines = lines_response.json()["data"]["items"]
        assert len(lines) == 2
        assert all(line["status"] == "done" for line in lines)


def test_inline_job_api_respects_project_and_episode_context(
    container: ServiceContainer,
) -> None:
    ref_audio_path = container.settings.paths.refs_dir / "hero_a.wav"

    with TestClient(create_app(container)) as client:
        project_response = client.post(
            "/projects",
            json={"name": "Project Inline"},
        )
        assert project_response.status_code == 200
        project = project_response.json()["data"]

        episode_response = client.post(
            f"/projects/{project['id']}/episodes",
            json={"name": "Episode Inline"},
        )
        assert episode_response.status_code == 200
        episode_id = episode_response.json()["data"]["episodes"][0]["id"]

        speaker_response = client.post(
            "/speakers",
            data={
                "project_id": project["id"],
                "name": "项目主角",
            },
            files={"ref_audio": ("hero.wav", ref_audio_path.read_bytes(), "audio/wav")},
        )
        assert speaker_response.status_code == 200

        response = client.post(
            "/jobs/from-lines",
            json={
                "project_id": project["id"],
                "episode_id": episode_id,
                "title": "页面批量任务",
                "force": True,
                "lines": [
                    {"id": "row-1", "speaker": "项目主角", "text": "第一句", "scene": "web"},
                    {"id": "row-2", "speaker": "项目主角", "text": "第二句", "scene": "web"},
                ],
            },
        )

        assert response.status_code == 200
        job = response.json()["data"]
        assert (
            f"data/projects/{project['id']}/scripts/{episode_id}/"
            in job["script_path"].replace("\\", "/")
        )
        assert (
            f"data/projects/{project['id']}/outputs/{episode_id}"
            in job["output_dir"].replace("\\", "/")
        )

        job_id = job["job_id"]
        deadline = time.time() + 3
        while time.time() < deadline:
            job_response = client.get(f"/jobs/{job_id}")
            assert job_response.status_code == 200
            payload = job_response.json()["data"]
            if payload["status"] in {"completed", "completed_with_errors", "failed"}:
                break
            time.sleep(0.05)
        else:
            raise AssertionError("Project-scoped inline job did not complete in time.")

        assert payload["status"] == "completed"

        lines_response = client.get(f"/jobs/{job_id}/lines")
        assert lines_response.status_code == 200
        lines = lines_response.json()["data"]["items"]
        assert len(lines) == 2
        assert all(line["status"] == "done" for line in lines)
        assert all(
            f"data/projects/{project['id']}/outputs/{episode_id}/"
            in line["output_path"].replace("\\", "/")
            for line in lines
        )
