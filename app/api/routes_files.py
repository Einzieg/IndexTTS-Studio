from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from app.api.dependencies import get_container
from app.core.container import ServiceContainer
from app.core.exceptions import MissingFileError, ValidationError


router = APIRouter(prefix="/files", tags=["files"])


@router.get("/audio")
def read_audio_file(
    path: str = Query(...),
    container: ServiceContainer = Depends(get_container),
) -> FileResponse:
    resolved_path = container.storage.resolve_path(path)
    if not resolved_path.exists() or not resolved_path.is_file():
        raise MissingFileError(f"Audio file not found: {resolved_path}")
    if resolved_path.suffix.lower() not in {".wav", ".mp3"}:
        raise ValidationError("Only `.wav` and `.mp3` files can be previewed from the UI.")

    data_root = container.settings.paths.data_dir.resolve()
    if not _is_under_root(resolved_path, data_root):
        raise ValidationError("UI audio preview is restricted to files under the data directory.")

    media_type = "audio/wav" if resolved_path.suffix.lower() == ".wav" else "audio/mpeg"
    return FileResponse(resolved_path, media_type=media_type, filename=resolved_path.name)


def _is_under_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root)
    except ValueError:
        return False
    return True
