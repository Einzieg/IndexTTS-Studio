from __future__ import annotations

from pathlib import Path

from app.core.container import ServiceContainer
from app.core.exceptions import ValidationError


def resolve_api_script_path(
    container: ServiceContainer,
    script_path: str,
    *,
    project_id: str | None = None,
) -> Path:
    resolved_path = container.storage.resolve_path(script_path).resolve()
    allowed_roots = [container.settings.paths.scripts_dir.resolve()]
    if project_id:
        allowed_roots.append(container.project_service.project_paths(project_id).scripts_dir.resolve())

    if not any(_is_under_root(resolved_path, root) for root in allowed_roots):
        raise ValidationError("Script path must be under a managed scripts directory.")
    return resolved_path


def _is_under_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
