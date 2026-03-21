from __future__ import annotations

import io
from zipfile import ZipFile

from fastapi.testclient import TestClient

from app.core.container import ServiceContainer
from app.main import create_app


def test_studio_table_api_persists_rows_per_project_episode(
    container: ServiceContainer,
) -> None:
    with TestClient(create_app(container)) as client:
        project_response = client.post(
            "/projects",
            json={"name": "Table Project"},
        )
        assert project_response.status_code == 200
        project = project_response.json()["data"]

        episode_response = client.post(
            f"/projects/{project['id']}/episodes",
            json={"name": "Episode One"},
        )
        assert episode_response.status_code == 200
        episode_id = episode_response.json()["data"]["episodes"][0]["id"]

        empty_response = client.get(
            "/scripts/table",
            params={"project_id": project["id"], "episode_id": episode_id},
        )
        assert empty_response.status_code == 200
        assert empty_response.json()["data"]["rows"] == []

        save_response = client.put(
            "/scripts/table",
            json={
                "project_id": project["id"],
                "episode_id": episode_id,
                "rows": [
                    {
                        "rowId": "row-1",
                        "speaker": "主角A",
                        "text": "测试台词",
                        "selected": True,
                        "override": {"temperature": 0.55},
                        "renders": [
                            {
                                "renderId": "render-1",
                                "outputPath": "data/projects/table_project/outputs/episode_one/row-1.wav",
                                "durationMs": 1280,
                                "createdAt": "2026-03-21T12:00:00+00:00",
                                "source": "batch",
                                "usedOptions": {"temperature": 0.55},
                            }
                        ],
                        "selectedRenderId": "render-1",
                        "lastStatus": "done",
                        "lastError": None,
                    }
                ],
            },
        )
        assert save_response.status_code == 200
        saved = save_response.json()["data"]
        assert saved["projectId"] == project["id"]
        assert saved["episodeId"] == episode_id
        assert saved["rows"][0]["rowId"] == "row-1"
        assert saved["rows"][0]["selectedRenderId"] == "render-1"

        load_response = client.get(
            "/scripts/table",
            params={"project_id": project["id"], "episode_id": episode_id},
        )
        assert load_response.status_code == 200
        loaded = load_response.json()["data"]
        assert loaded["rows"][0]["text"] == "测试台词"
        assert loaded["rows"][0]["lastStatus"] == "done"
        assert loaded["rows"][0]["renders"][0]["outputPath"].endswith("row-1.wav")


def test_studio_table_export_packages_selected_renders(
    container: ServiceContainer,
) -> None:
    with TestClient(create_app(container)) as client:
        project_response = client.post(
            "/projects",
            json={"name": "导出项目"},
        )
        assert project_response.status_code == 200
        project = project_response.json()["data"]

        episode_response = client.post(
            f"/projects/{project['id']}/episodes",
            json={"name": "第一集"},
        )
        assert episode_response.status_code == 200
        episode_id = episode_response.json()["data"]["episodes"][0]["id"]

        output_dir = (
            container.settings.paths.data_dir
            / "projects"
            / project["id"]
            / "outputs"
            / episode_id
        )
        line1 = output_dir / "line1.wav"
        line3a = output_dir / "line3a.wav"
        line3b = output_dir / "line3b.wav"
        line1.parent.mkdir(parents=True, exist_ok=True)
        line1.write_bytes(b"RIFFline1")
        line3a.write_bytes(b"RIFFline3a")
        line3b.write_bytes(b"RIFFline3b")

        save_response = client.put(
            "/scripts/table",
            json={
                "project_id": project["id"],
                "episode_id": episode_id,
                "rows": [
                    {
                        "rowId": "row-1",
                        "speaker": "主角A",
                        "text": "第一句",
                        "selected": True,
                        "override": {},
                        "renders": [
                            {
                                "renderId": "render-1",
                                "outputPath": str(line1),
                                "durationMs": 1000,
                                "createdAt": "2026-03-21T12:00:00+00:00",
                                "source": "batch",
                                "usedOptions": {},
                            }
                        ],
                        "selectedRenderId": "render-1",
                        "lastStatus": "done",
                        "lastError": None,
                    },
                    {
                        "rowId": "row-2",
                        "speaker": "旁白",
                        "text": "第二句",
                        "selected": False,
                        "override": {},
                        "renders": [],
                        "selectedRenderId": None,
                        "lastStatus": "idle",
                        "lastError": None,
                    },
                    {
                        "rowId": "row-3",
                        "speaker": "反派B",
                        "text": "第三句",
                        "selected": False,
                        "override": {},
                        "renders": [
                            {
                                "renderId": "render-3a",
                                "outputPath": str(line3a),
                                "durationMs": 900,
                                "createdAt": "2026-03-21T12:01:00+00:00",
                                "source": "batch",
                                "usedOptions": {},
                            },
                            {
                                "renderId": "render-3b",
                                "outputPath": str(line3b),
                                "durationMs": 950,
                                "createdAt": "2026-03-21T12:02:00+00:00",
                                "source": "config",
                                "usedOptions": {},
                            },
                        ],
                        "selectedRenderId": "render-3b",
                        "lastStatus": "done",
                        "lastError": None,
                    },
                ],
            },
        )
        assert save_response.status_code == 200

        export_response = client.get(
            "/scripts/table/export",
            params={"project_id": project["id"], "episode_id": episode_id},
        )
        assert export_response.status_code == 200
        assert export_response.headers["content-type"] == "application/zip"
        assert export_response.headers["x-exported-count"] == "2"

        with ZipFile(io.BytesIO(export_response.content)) as archive:
            assert sorted(archive.namelist()) == [
                "项目-导出项目-分集-第一集-001-主角A.wav",
                "项目-导出项目-分集-第一集-003-反派B.wav",
            ]
            assert archive.read("项目-导出项目-分集-第一集-001-主角A.wav") == b"RIFFline1"
            assert archive.read("项目-导出项目-分集-第一集-003-反派B.wav") == b"RIFFline3b"
