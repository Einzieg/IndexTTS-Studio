from __future__ import annotations

from pathlib import Path

from app.core.container import ServiceContainer


def test_tts_service_merges_defaults_and_override(container: ServiceContainer) -> None:
    speaker = container.speaker_service.get_speaker(container.speaker_service.list_speakers()[0])
    merged = container.tts_service.merge_generation_options(
        speaker,
        override={"temperature": 0.25, "emo_alpha": 0.9},
    )

    assert merged["temperature"] == 0.25
    assert merged["emo_alpha"] == 0.9
    assert merged["top_k"] == 30
    assert Path(merged["emo_audio"]).name == "hero_a_emo.wav"


def test_tts_service_generates_audio(container: ServiceContainer) -> None:
    result = container.tts_service.synthesize_single(
        speaker=container.speaker_service.list_speakers()[0],
        text="test single line generation",
        output_name="single_test.wav",
        force=True,
    )

    assert result.status == "done"
    assert result.output_path.exists()


def test_tts_service_applies_line_override(container: ServiceContainer) -> None:
    speakers = container.speaker_service.list_speakers()
    script_path = container.settings.paths.scripts_dir / "line_override_batch.json"
    script_path.write_text(
        (
            "{\n"
            '  "items": [\n'
            "    {\n"
            '      "id": "1",\n'
            '      "scene": "020",\n'
            f'      "speaker": "{speakers[0]}",\n'
            '      "text": "line override should win",\n'
            '      "override": {\n'
            '        "temperature": 0.42,\n'
            '        "top_p": 0.55,\n'
            '        "interval_silence": 0.33,\n'
            '        "emo_vector": [0, 0, 0, 0, 1, 0, 0, 0]\n'
            "      }\n"
            "    }\n"
            "  ]\n"
            "}\n"
        ),
        encoding="utf-8",
    )

    line = container.script_service.load_script(script_path)[0]
    result = container.tts_service.synthesize_script_line(
        line,
        container.storage.script_output_dir(script_path),
        force=True,
    )

    assert result.status == "done"
    assert result.used_options["temperature"] == 0.42
    assert result.used_options["top_p"] == 0.55
    assert result.used_options["interval_silence"] == 0.33
    assert result.used_options["emo_vector"] == [0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
    assert "emo_audio" not in result.used_options
