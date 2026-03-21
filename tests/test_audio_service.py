from __future__ import annotations

import wave
from pathlib import Path

from app.core.container import ServiceContainer


def _write_srt_script(path: Path, speakers: list[str]) -> None:
    path.write_text(
        "\n".join(
            [
                "1",
                "00:00:00,000 --> 00:00:00,900",
                f"{speakers[0]}: Timeline line one.",
                "",
                "2",
                "00:00:01,200 --> 00:00:02,000",
                f"{speakers[1]}: Timeline line two.",
                "",
                "3",
                "00:00:02,400 --> 00:00:03,300",
                f"[{speakers[2]}]",
                "Timeline line three.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_audio_service_merges_script_outputs(container: ServiceContainer) -> None:
    batch_report = container.job_service.run_batch(
        script_path="data/scripts/episode1.csv",
        force=True,
    )

    merge_report = container.audio_service.merge_script_outputs(
        script_path="data/scripts/episode1.csv",
        gap_ms=200,
        force=True,
    )

    assert container.audio_service.capabilities() == {
        "merge_segments": True,
        "timeline_alignment": True,
        "preview_mixdown": True,
    }
    assert merge_report.mode == "sequence"
    assert merge_report.segment_count == 3
    assert merge_report.gap_ms == 200
    assert merge_report.tail_padding_ms == 0
    assert merge_report.output_path.exists()
    assert (batch_report.output_dir / "preview_mix_report.json").exists()

    source_frame_total = 0
    sample_rate = None
    channels = None
    sample_width = None
    for source_path in merge_report.source_paths:
        with wave.open(str(source_path), "rb") as source:
            source_frame_total += source.getnframes()
            sample_rate = sample_rate or source.getframerate()
            channels = channels or source.getnchannels()
            sample_width = sample_width or source.getsampwidth()

    assert sample_rate is not None
    expected_total_frames = source_frame_total + int(sample_rate * 0.2) * (
        len(merge_report.source_paths) - 1
    )

    with wave.open(str(merge_report.output_path), "rb") as merged:
        assert merged.getframerate() == sample_rate
        assert merged.getnchannels() == channels
        assert merged.getsampwidth() == sample_width
        assert merged.getnframes() == expected_total_frames


def test_audio_service_merges_outputs_on_timeline(container: ServiceContainer) -> None:
    speakers = container.speaker_service.list_speakers()
    srt_path = container.settings.paths.scripts_dir / "timeline_episode.srt"
    _write_srt_script(srt_path, speakers)

    batch_report = container.job_service.run_batch(
        script_path=srt_path,
        force=True,
    )
    lines = container.script_service.load_script(srt_path)

    merge_report = container.audio_service.merge_script_outputs(
        script_path=srt_path,
        use_timeline=True,
        tail_padding_ms=200,
        force=True,
    )

    assert merge_report.mode == "timeline"
    assert merge_report.gap_ms == 0
    assert merge_report.tail_padding_ms == 200
    assert merge_report.segment_count == 3
    assert merge_report.output_path.exists()
    assert batch_report.output_dir == merge_report.output_path.parent

    sample_rate = merge_report.sample_rate
    expected_audio_end_frames = 0
    expected_timeline_frames = 0
    for line in lines:
        source_path = container.tts_service.resolve_line_output_path(line, batch_report.output_dir)
        with wave.open(str(source_path), "rb") as source:
            start_frames = round(sample_rate * ((line.start_ms or 0) / 1000))
            expected_audio_end_frames = max(
                expected_audio_end_frames,
                start_frames + source.getnframes(),
            )
        if line.end_ms is not None:
            expected_timeline_frames = max(
                expected_timeline_frames,
                round(sample_rate * (line.end_ms / 1000)),
            )

    expected_total_frames = max(expected_audio_end_frames, expected_timeline_frames) + round(
        sample_rate * 0.2
    )

    with wave.open(str(merge_report.output_path), "rb") as merged:
        assert merged.getframerate() == merge_report.sample_rate
        assert merged.getnchannels() == merge_report.channels
        assert merged.getsampwidth() == merge_report.sample_width
        assert merged.getnframes() == expected_total_frames
