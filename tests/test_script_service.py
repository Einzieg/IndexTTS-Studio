from __future__ import annotations

import json
from pathlib import Path

from app.core.container import ServiceContainer


def _write_srt_script(path: Path, speakers: list[str]) -> None:
    path.write_text(
        "\n".join(
            [
                "1",
                "00:00:00,000 --> 00:00:00,900",
                f"{speakers[0]}: First timed line.",
                "",
                "2",
                "00:00:01,200 --> 00:00:02,100",
                f"[{speakers[1]}]",
                "Second timed line.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_script_service_loads_csv(container: ServiceContainer) -> None:
    lines = container.script_service.load_script("data/scripts/episode1.csv")
    speakers = container.speaker_service.list_speakers()

    assert [line.id for line in lines] == ["1", "2", "3"]
    assert lines[0].speaker == speakers[0]
    assert lines[2].output_name == f"001_0003_{speakers[2]}.wav"


def test_script_service_loads_srt(container: ServiceContainer) -> None:
    speakers = container.speaker_service.list_speakers()
    srt_path = container.settings.paths.scripts_dir / "timed_episode.srt"
    _write_srt_script(srt_path, speakers)

    lines = container.script_service.load_script(srt_path)

    assert [line.id for line in lines] == ["1", "2"]
    assert lines[0].speaker == speakers[0]
    assert lines[0].text == "First timed line."
    assert lines[0].start_ms == 0
    assert lines[0].end_ms == 900
    assert lines[1].speaker == speakers[1]
    assert lines[1].text == "Second timed line."
    assert lines[1].scene == "srt"


def test_script_service_loads_line_overrides(container: ServiceContainer) -> None:
    speakers = container.speaker_service.list_speakers()
    csv_path = container.settings.paths.scripts_dir / "override_episode.csv"
    csv_path.write_text(
        "\n".join(
            [
                "id,scene,speaker,text,temperature,emo_alpha,interval_silence,emo_vector,output_name",
                (
                    "1,010,"
                    f"{speakers[0]},Line override sample,0.35,0.8,0.45,\"[0,0,0,0,0,0,1,0]\",override_line.wav"
                ),
            ]
        ),
        encoding="utf-8",
    )

    json_path = container.settings.paths.scripts_dir / "override_episode.json"
    json_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "id": "2",
                        "scene": "011",
                        "speaker": speakers[1],
                        "text": "JSON override sample",
                        "override": {
                            "temperature": 0.4,
                            "top_k": 12,
                            "emo_text": "whispering",
                            "use_emo_text": True,
                        },
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    csv_lines = container.script_service.load_script(csv_path)
    json_lines = container.script_service.load_script(json_path)

    assert csv_lines[0].override["temperature"] == 0.35
    assert csv_lines[0].override["emo_alpha"] == 0.8
    assert csv_lines[0].override["interval_silence"] == 0.45
    assert csv_lines[0].override["emo_vector"] == [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    assert json_lines[0].override["temperature"] == 0.4
    assert json_lines[0].override["top_k"] == 12
    assert json_lines[0].override["emo_text"] == "whispering"
    assert json_lines[0].override["use_emo_text"] is True
