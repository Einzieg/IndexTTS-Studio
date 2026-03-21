from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.container import ServiceContainer
from app.main import create_app


def test_async_job_endpoints(container: ServiceContainer) -> None:
    with TestClient(create_app(container)) as client:
        capabilities_response = client.get("/jobs/capabilities")
        assert capabilities_response.status_code == 200
        capabilities = capabilities_response.json()["data"]
        assert capabilities["async_jobs"] is True
        assert capabilities["queue_backend"] == "in_memory_serial"

        create_response = client.post(
            "/jobs",
            json={
                "script_path": "data/scripts/episode1.csv",
                "skip_existing": False,
                "continue_on_error": True,
                "force": True,
            },
        )
        assert create_response.status_code == 200
        created_job = create_response.json()["data"]
        job_id = created_job["job_id"]
        assert created_job["status"] in {"queued", "running"}
        assert created_job["total"] == 3

        final_job: dict | None = None
        for _ in range(40):
            job_response = client.get(f"/jobs/{job_id}")
            assert job_response.status_code == 200
            final_job = job_response.json()["data"]
            if final_job["status"] in {"completed", "completed_with_errors", "failed"}:
                break
            time.sleep(0.05)

        assert final_job is not None
        assert final_job["status"] == "completed"
        assert final_job["done"] == 3
        assert final_job["failed"] == 0
        assert final_job["report"]["success"] is True
        assert final_job["report"]["done"] == 3

        lines_response = client.get(f"/jobs/{job_id}/lines")
        assert lines_response.status_code == 200
        lines = lines_response.json()["data"]["items"]
        assert len(lines) == 3
        assert all(line["status"] == "done" for line in lines)
        assert all(line["output_path"] for line in lines)

        list_response = client.get("/jobs")
        assert list_response.status_code == 200
        job_ids = [item["job_id"] for item in list_response.json()["data"]["items"]]
        assert job_id in job_ids


def test_job_lines_expose_script_override(container: ServiceContainer) -> None:
    speakers = container.speaker_service.list_speakers()
    script_path = container.settings.paths.scripts_dir / "job_override_episode.json"
    script_path.write_text(
        (
            "{\n"
            '  "items": [\n'
            "    {\n"
            '      "id": "1",\n'
            '      "scene": "030",\n'
            f'      "speaker": "{speakers[0]}",\n'
            '      "text": "job override sample",\n'
            '      "override": {\n'
            '        "temperature": 0.31,\n'
            '        "top_k": 11\n'
            "      }\n"
            "    }\n"
            "  ]\n"
            "}\n"
        ),
        encoding="utf-8",
    )

    with TestClient(create_app(container)) as client:
        create_response = client.post(
            "/jobs",
            json={
                "script_path": str(Path(script_path)),
                "skip_existing": False,
                "continue_on_error": True,
                "force": True,
            },
        )
        assert create_response.status_code == 200
        job_id = create_response.json()["data"]["job_id"]

        final_job: dict | None = None
        for _ in range(40):
            job_response = client.get(f"/jobs/{job_id}")
            assert job_response.status_code == 200
            final_job = job_response.json()["data"]
            if final_job["status"] in {"completed", "completed_with_errors", "failed"}:
                break
            time.sleep(0.05)

        assert final_job is not None
        assert final_job["status"] == "completed"

        lines_response = client.get(f"/jobs/{job_id}/lines")
        assert lines_response.status_code == 200
        line = lines_response.json()["data"]["items"][0]
        assert line["override"]["temperature"] == 0.31
        assert line["override"]["top_k"] == 11
