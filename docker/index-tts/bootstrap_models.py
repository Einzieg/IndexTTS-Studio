from __future__ import annotations

import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from pathlib import Path
from typing import Callable


LOGGER = logging.getLogger("index_tts_bootstrap")
REQUIRED_FILES = (
    "bpe.model",
    "config.yaml",
    "gpt.pth",
    "s2mel.pth",
    "wav2vec2bert_stats.pt",
)
DEFAULT_PROGRESS_INTERVAL_SECONDS = 30
DEFAULT_DOWNLOAD_RETRIES = 10
DEFAULT_RETRY_DELAY_SECONDS = 10


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def missing_files(model_dir: Path) -> list[str]:
    return [name for name in REQUIRED_FILES if not (model_dir / name).exists()]


def format_bytes(size_bytes: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size_bytes)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{size_bytes} B"


def collect_directory_stats(root: Path) -> tuple[int, int]:
    file_count = 0
    total_size = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        file_count += 1
        try:
            total_size += path.stat().st_size
        except OSError:
            continue
    return file_count, total_size


def progress_interval_seconds() -> int:
    raw = os.getenv(
        "INDEXTTS_BOOTSTRAP_PROGRESS_INTERVAL",
        str(DEFAULT_PROGRESS_INTERVAL_SECONDS),
    )
    try:
        return max(5, int(raw))
    except ValueError:
        LOGGER.warning(
            "Invalid INDEXTTS_BOOTSTRAP_PROGRESS_INTERVAL=%r, using %s seconds.",
            raw,
            DEFAULT_PROGRESS_INTERVAL_SECONDS,
        )
        return DEFAULT_PROGRESS_INTERVAL_SECONDS


def download_retry_count() -> int:
    raw = os.getenv("INDEXTTS_BOOTSTRAP_RETRIES", str(DEFAULT_DOWNLOAD_RETRIES))
    try:
        return max(1, int(raw))
    except ValueError:
        LOGGER.warning(
            "Invalid INDEXTTS_BOOTSTRAP_RETRIES=%r, using %s retries.",
            raw,
            DEFAULT_DOWNLOAD_RETRIES,
        )
        return DEFAULT_DOWNLOAD_RETRIES


def download_retry_delay_seconds() -> int:
    raw = os.getenv(
        "INDEXTTS_BOOTSTRAP_RETRY_DELAY",
        str(DEFAULT_RETRY_DELAY_SECONDS),
    )
    try:
        return max(1, int(raw))
    except ValueError:
        LOGGER.warning(
            "Invalid INDEXTTS_BOOTSTRAP_RETRY_DELAY=%r, using %s seconds.",
            raw,
            DEFAULT_RETRY_DELAY_SECONDS,
        )
        return DEFAULT_RETRY_DELAY_SECONDS


def run_with_progress(
    source_name: str, downloader: Callable[[Path], None], model_dir: Path
) -> None:
    interval = progress_interval_seconds()
    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(downloader, model_dir)
        while True:
            try:
                future.result(timeout=interval)
                elapsed = time.monotonic() - start
                file_count, total_size = collect_directory_stats(model_dir)
                LOGGER.info(
                    "Model bootstrap via `%s` completed in %.1fs with %s across %s files.",
                    source_name,
                    elapsed,
                    format_bytes(total_size),
                    file_count,
                )
                return
            except FutureTimeoutError:
                elapsed = time.monotonic() - start
                file_count, total_size = collect_directory_stats(model_dir)
                remaining = missing_files(model_dir)
                LOGGER.info(
                    "Model bootstrap via `%s` still running after %.0fs: %s across %s files; missing required files: %s",
                    source_name,
                    elapsed,
                    format_bytes(total_size),
                    file_count,
                    ", ".join(remaining) if remaining else "none",
                )


def download_from_huggingface(model_dir: Path) -> None:
    from huggingface_hub import hf_hub_download

    repo_id = os.getenv("INDEXTTS_MODEL_REPO", "IndexTeam/IndexTTS-2")
    token = os.getenv("HF_TOKEN") or None
    LOGGER.info("Downloading IndexTTS checkpoints from Hugging Face repo `%s`.", repo_id)
    for filename in missing_files(model_dir):
        LOGGER.info("Downloading missing Hugging Face file `%s`.", filename)
        hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=str(model_dir),
            token=token,
        )


def download_from_modelscope(model_dir: Path) -> None:
    from modelscope import snapshot_download

    model_id = os.getenv("INDEXTTS_MODELSCOPE_MODEL_ID", "IndexTeam/IndexTTS-2")
    LOGGER.info("Downloading IndexTTS checkpoints from ModelScope model `%s`.", model_id)
    snapshot_download(model_id=model_id, local_dir=str(model_dir))


def ensure_models(model_dir: Path) -> None:
    model_dir.mkdir(parents=True, exist_ok=True)
    missing = missing_files(model_dir)
    if not missing:
        LOGGER.info("IndexTTS checkpoints already present under `%s`.", model_dir)
        return

    source = os.getenv("INDEXTTS_MODEL_SOURCE", "auto").strip().lower()
    LOGGER.info("Missing checkpoints detected: %s", ", ".join(missing))

    attempts: list[tuple[str, Callable[[Path], None]]] = []
    if source == "huggingface":
        attempts = [("huggingface", download_from_huggingface)]
    elif source == "modelscope":
        attempts = [("modelscope", download_from_modelscope)]
    elif source == "none":
        raise RuntimeError(
            "IndexTTS checkpoints are missing and INDEXTTS_MODEL_SOURCE=none."
        )
    else:
        attempts = [
            ("huggingface", download_from_huggingface),
            ("modelscope", download_from_modelscope),
        ]

    last_error: Exception | None = None
    for name, downloader in attempts:
        retries = download_retry_count()
        delay_seconds = download_retry_delay_seconds()
        for attempt in range(1, retries + 1):
            try:
                LOGGER.info(
                    "Trying model bootstrap source `%s` (attempt %s/%s).",
                    name,
                    attempt,
                    retries,
                )
                run_with_progress(name, downloader, model_dir)
                remaining = missing_files(model_dir)
                if remaining:
                    raise RuntimeError(
                        f"Model download from `{name}` finished but files are still missing: "
                        f"{', '.join(remaining)}"
                    )
                LOGGER.info("IndexTTS checkpoints are ready under `%s`.", model_dir)
                return
            except Exception as exc:  # pragma: no cover - startup path
                last_error = exc
                remaining = missing_files(model_dir)
                LOGGER.warning(
                    "Model bootstrap via `%s` failed on attempt %s/%s: %s",
                    name,
                    attempt,
                    retries,
                    exc,
                )
                if attempt >= retries:
                    break
                LOGGER.info(
                    "Will retry `%s` after %s seconds; still missing: %s",
                    name,
                    delay_seconds,
                    ", ".join(remaining) if remaining else "none",
                )
                time.sleep(delay_seconds)

    raise RuntimeError("Unable to bootstrap IndexTTS checkpoints.") from last_error


def main() -> int:
    configure_logging()
    model_dir = Path(os.getenv("INDEXTTS_MODEL_DIR", "/opt/index-tts/checkpoints"))
    ensure_models(model_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
