from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from app.api.dependencies import get_container
from app.api.responses import api_response
from app.core.container import ServiceContainer
from app.domain.schemas import StudioTableSaveRequest


SUPPORTED_SCRIPT_SUFFIXES = {".csv", ".json", ".srt"}


router = APIRouter(prefix="/scripts", tags=["scripts"])


@router.get("")
def list_scripts(container: ServiceContainer = Depends(get_container)) -> dict:
    project_root = container.settings.paths.project_root
    script_root = container.settings.paths.scripts_dir
    items: list[dict[str, object]] = []

    for path in sorted(script_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SCRIPT_SUFFIXES:
            continue
        try:
            relative_path = path.relative_to(project_root).as_posix()
        except ValueError:
            relative_path = str(path)

        items.append(
            {
                "name": path.name,
                "path": relative_path,
                "format": path.suffix.lower().lstrip("."),
                "updated_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
            }
        )

    return api_response(
        success=True,
        message="Loaded scripts successfully.",
        data={"items": items},
    )


@router.get("/preview")
def preview_script(
    script_path: str = Query(...),
    container: ServiceContainer = Depends(get_container),
) -> dict:
    resolved_path = container.storage.resolve_path(script_path)
    lines = container.script_service.load_script(resolved_path)
    return api_response(
        success=True,
        message="Loaded script preview successfully.",
        data={
            "script_path": _display_path(container.settings.paths.project_root, resolved_path),
            "has_timeline": any(line.start_ms is not None for line in lines),
            "items": lines,
        },
    )


@router.get("/table")
def load_studio_table(
    project_id: str = Query(...),
    episode_id: str = Query(...),
    container: ServiceContainer = Depends(get_container),
) -> dict:
    payload = container.studio_table_service.load_table(
        project_id=project_id,
        episode_id=episode_id,
    )
    return api_response(
        success=True,
        message="Loaded studio table successfully.",
        data=payload.model_dump(mode="json", by_alias=True),
    )


@router.put("/table")
def save_studio_table(
    payload: StudioTableSaveRequest,
    container: ServiceContainer = Depends(get_container),
) -> dict:
    saved = container.studio_table_service.save_table(
        project_id=payload.project_id,
        episode_id=payload.episode_id,
        rows=payload.rows,
    )
    return api_response(
        success=True,
        message="Saved studio table successfully.",
        data=saved.model_dump(mode="json", by_alias=True),
    )


@router.get("/table/export")
def export_studio_table(
    project_id: str = Query(...),
    episode_id: str = Query(...),
    container: ServiceContainer = Depends(get_container),
) -> FileResponse:
    export = container.studio_table_service.export_table_audio(
        project_id=project_id,
        episode_id=episode_id,
    )
    return FileResponse(
        export.archive_path,
        media_type="application/zip",
        filename=export.download_name,
        headers={"X-Exported-Count": str(export.exported_count)},
    )


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return str(path)
