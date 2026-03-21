from __future__ import annotations

import json
import math
import struct
import wave
from pathlib import Path

import pytest

from app.core.config import ApiSettings, AppSettings, ModelSettings, PathSettings
from app.core.container import ServiceContainer, build_container


def _write_wave_file(path: Path, frequency: float = 220.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 22050
    frames = int(sample_rate * 0.3)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        for index in range(frames):
            amplitude = int(1000 * math.sin((2 * math.pi * frequency * index) / sample_rate))
            wav_file.writeframes(struct.pack("<h", amplitude))


@pytest.fixture()
def studio_root(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    refs_dir = data_dir / "refs"
    scripts_dir = data_dir / "scripts"

    _write_wave_file(refs_dir / "hero_a.wav", 220.0)
    _write_wave_file(refs_dir / "hero_a_emo.wav", 246.94)
    _write_wave_file(refs_dir / "villain_b.wav", 196.0)
    _write_wave_file(refs_dir / "narrator.wav", 174.61)

    speakers_payload = {
        "主角A": {
            "ref_audio": "data/refs/hero_a.wav",
            "emo_audio": "data/refs/hero_a_emo.wav",
            "emo_alpha": 0.6,
            "temperature": 0.8,
            "top_p": 0.8,
            "top_k": 30,
        },
        "反派B": {
            "ref_audio": "data/refs/villain_b.wav",
        },
        "旁白": {
            "ref_audio": "data/refs/narrator.wav",
            "emo_vector": [0, 0, 0, 0, 0, 0, 0, 1.0],
        },
    }
    (data_dir / "speakers.json").write_text(
        json.dumps(speakers_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "episode1.csv").write_text(
        "id,scene,speaker,text,output_name\n"
        "1,001,主角A,今天必须把事情查清楚。,001_0001_主角A.wav\n"
        "2,001,反派B,你来晚了。,001_0002_反派B.wav\n"
        "3,001,旁白,夜色渐深，真相开始浮出水面。,001_0003_旁白.wav\n",
        encoding="utf-8",
    )
    (scripts_dir / "episode1.srt").write_text(
        "1\n"
        "00:00:00,000 --> 00:00:01,100\n"
        "涓昏A: First subtitle line.\n\n"
        "2\n"
        "00:00:01,400 --> 00:00:02,200\n"
        "鍙嶆淳B: Second subtitle line.\n\n"
        "3\n"
        "00:00:02,600 --> 00:00:04,100\n"
        "[鏃佺櫧]\n"
        "Third subtitle line.\n",
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture()
def studio_settings(studio_root: Path) -> AppSettings:
    data_dir = studio_root / "data"
    settings = AppSettings(
        paths=PathSettings(
            project_root=studio_root,
            data_dir=data_dir,
            speakers_file=data_dir / "speakers.json",
            scripts_dir=data_dir / "scripts",
            refs_dir=data_dir / "refs",
            outputs_dir=data_dir / "outputs",
            logs_dir=data_dir / "logs",
        ),
        api=ApiSettings(host="127.0.0.1", port=8001),
        model=ModelSettings(backend="mock", warmup_on_startup=True),
    )
    settings.ensure_runtime_dirs()
    return settings


@pytest.fixture()
def container(studio_settings: AppSettings) -> ServiceContainer:
    active_container = build_container(studio_settings)
    try:
        yield active_container
    finally:
        active_container.shutdown()
