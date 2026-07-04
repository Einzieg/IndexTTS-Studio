from __future__ import annotations

import argparse
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.responses import api_response
from app.api.routes_audio import router as audio_router
from app.api.routes_auth import router as auth_router
from app.api.routes_files import router as files_router
from app.api.routes_jobs import router as jobs_router
from app.api.routes_projects import router as projects_router
from app.api.routes_scripts import router as scripts_router
from app.api.routes_speakers import router as speakers_router
from app.api.routes_tts import router as tts_router
from app.core.auth import session_from_request
from app.core.config import get_settings
from app.core.container import ServiceContainer, build_container
from app.core.exceptions import StudioError
from app.core.logger import get_logger
from app.domain.models import HealthStatus


def create_app(container: ServiceContainer | None = None) -> FastAPI:
    active_container = container or build_container()
    logger = get_logger("indextts_studio")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("Starting IndexTTS-Studio API.")
        active_container.initialize(resume_jobs=True)
        yield
        active_container.shutdown()
        logger.info("Stopping IndexTTS-Studio API.")

    app = FastAPI(
        title="IndexTTS-Studio",
        version="0.1.0",
        description="基于 IndexTTS2 的多角色配音工作台。",
        lifespan=lifespan,
    )
    app.state.container = active_container

    @app.middleware("http")
    async def auth_guard(request: Request, call_next):
        auth_settings = active_container.settings.auth
        if (
            not auth_settings.enabled
            or request.method == "OPTIONS"
            or _is_public_path(request.url.path)
        ):
            return await call_next(request)

        session = session_from_request(request, auth_settings)
        if session is None:
            return JSONResponse(
                status_code=401,
                content=api_response(success=False, message="请先登录。"),
            )

        request.state.auth_session = session
        return await call_next(request)

    @app.exception_handler(StudioError)
    async def handle_studio_error(_: Request, exc: StudioError) -> JSONResponse:
        logger.warning("Handled studio error: %s", exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content=api_response(success=False, message=exc.message),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled server error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=api_response(success=False, message="服务器发生未预期错误。"),
        )

    @app.get("/health")
    def health() -> dict[str, Any]:
        return api_response(
            success=True,
            message="服务运行正常。",
            data=HealthStatus(
                max_script_line_text_chars=active_container.settings.max_script_line_text_chars,
            ),
        )

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(url="/ui", status_code=307)

    app.include_router(auth_router)
    app.include_router(speakers_router)
    app.include_router(projects_router)
    app.include_router(scripts_router)
    app.include_router(tts_router)
    app.include_router(jobs_router)
    app.include_router(audio_router)
    app.include_router(files_router)

    _configure_web_ui(app, active_container.settings.paths.project_root / "web" / "dist")
    return app


def run(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    settings = get_settings()
    container = build_container(settings)

    try:
        if args.command == "serve":
            container.initialize(resume_jobs=True)
            uvicorn.run(
                create_app(container),
                host=args.host,
                port=args.port,
            )
            return

        container.initialize()

        if args.command == "single":
            result = container.tts_service.synthesize_single(
                speaker=args.speaker,
                text=args.text,
                output_name=args.output_name,
                force=args.force,
            )
            _print_json(result.model_dump(mode="json"))
            return

        if args.command == "batch":
            report = container.job_service.run_batch(
                script_path=args.script,
                skip_existing=args.skip_existing,
                continue_on_error=args.continue_on_error,
                force=args.force,
            )
            _print_json(report.model_dump(mode="json"))
            return

        if args.command == "regenerate":
            result = container.job_service.regenerate_line(
                script_path=args.script,
                line_id=args.line_id,
                force=args.force,
            )
            _print_json(result.model_dump(mode="json"))
            return

        if args.command == "merge":
            report = container.audio_service.merge_script_outputs(
                script_path=args.script,
                output_name=args.output_name,
                gap_ms=args.gap_ms,
                use_timeline=args.use_timeline,
                tail_padding_ms=args.tail_padding_ms,
                force=args.force,
            )
            _print_json(report.model_dump(mode="json"))
            return

        parser.error("Unknown command.")
    finally:
        container.shutdown()


def _build_parser() -> argparse.ArgumentParser:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="IndexTTS-Studio command line interface")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve_parser = subparsers.add_parser("serve", help="Run the FastAPI service")
    serve_parser.add_argument("--host", default=settings.api.host)
    serve_parser.add_argument("--port", type=int, default=settings.api.port)

    single_parser = subparsers.add_parser("single", help="Synthesize a single line")
    single_parser.add_argument("--speaker", required=True)
    single_parser.add_argument("--text", required=True)
    single_parser.add_argument("--output-name")
    single_parser.add_argument("--force", action="store_true")

    batch_parser = subparsers.add_parser("batch", help="Run a batch script")
    batch_parser.add_argument("--script", required=True)
    batch_parser.add_argument("--skip-existing", dest="skip_existing", action="store_true")
    batch_parser.add_argument("--no-skip-existing", dest="skip_existing", action="store_false")
    batch_parser.add_argument(
        "--continue-on-error",
        dest="continue_on_error",
        action="store_true",
    )
    batch_parser.add_argument(
        "--stop-on-error",
        dest="continue_on_error",
        action="store_false",
    )
    batch_parser.add_argument("--force", action="store_true")
    batch_parser.set_defaults(skip_existing=True, continue_on_error=True)

    regenerate_parser = subparsers.add_parser(
        "regenerate",
        help="Re-run a single line from a batch script",
    )
    regenerate_parser.add_argument("--script", required=True)
    regenerate_parser.add_argument("--line-id", required=True)
    regenerate_parser.add_argument(
        "--force",
        action=argparse.BooleanOptionalAction,
        default=True,
    )

    merge_parser = subparsers.add_parser(
        "merge",
        help="Merge synthesized script lines into one preview WAV",
    )
    merge_parser.add_argument("--script", required=True)
    merge_parser.add_argument("--output-name")
    merge_parser.add_argument("--gap-ms", type=int, default=250)
    merge_parser.add_argument("--use-timeline", action="store_true")
    merge_parser.add_argument("--tail-padding-ms", type=int, default=0)
    merge_parser.add_argument("--force", action="store_true")

    return parser


def _print_json(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    try:
        sys.stdout.write(f"{text}\n")
    except UnicodeEncodeError:
        if sys.stdout.buffer is not None:
            encoded = text.encode(sys.stdout.encoding or "utf-8", errors="backslashreplace")
            sys.stdout.buffer.write(encoded + b"\n")
            sys.stdout.flush()
            return
        raise


def _configure_web_ui(app: FastAPI, dist_path: Path) -> None:
    if dist_path.exists():
        app.mount("/ui", StaticFiles(directory=dist_path, html=True), name="ui")
        return

    @app.get("/ui", include_in_schema=False)
    def ui_placeholder() -> HTMLResponse:
        return HTMLResponse(
            """
            <html>
              <head><title>IndexTTS-Studio 控制台</title></head>
              <body style="font-family: sans-serif; padding: 32px;">
                <h1>IndexTTS-Studio 前端还没有构建。</h1>
                <p>请先在 <code>web/</code> 目录运行 <code>npm install</code> 和 <code>npm run build</code>。</p>
              </body>
            </html>
            """
        )


def _is_public_path(path: str) -> bool:
    if path in {"/", "/health"}:
        return True
    return path.startswith("/ui") or path.startswith("/auth")


app = create_app()


if __name__ == "__main__":
    run()
