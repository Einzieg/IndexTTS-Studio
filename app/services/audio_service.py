from __future__ import annotations

from array import array
import sys
import wave
from pathlib import Path

from app.core.exceptions import MissingFileError, OutputNameCollisionError, ValidationError
from app.domain.models import AudioMergeReport, ScriptLine
from app.infra.storage import StorageService
from app.services.script_service import ScriptService
from app.services.tts_service import TTSService


class AudioService:
    def __init__(
        self,
        storage: StorageService,
        script_service: ScriptService,
        tts_service: TTSService,
    ) -> None:
        self.storage = storage
        self.script_service = script_service
        self.tts_service = tts_service

    def capabilities(self) -> dict[str, bool]:
        return {
            "merge_segments": True,
            "timeline_alignment": True,
            "preview_mixdown": True,
        }

    def merge_script_outputs(
        self,
        *,
        script_path: str | Path,
        output_name: str | None = None,
        gap_ms: int = 250,
        use_timeline: bool = False,
        tail_padding_ms: int = 0,
        force: bool = False,
    ) -> AudioMergeReport:
        if gap_ms < 0:
            raise ValidationError("`gap_ms` must be greater than or equal to 0.")
        if tail_padding_ms < 0:
            raise ValidationError("`tail_padding_ms` must be greater than or equal to 0.")

        resolved_script_path = self.storage.resolve_path(script_path)
        lines = self.script_service.load_script(resolved_script_path)
        if not lines:
            raise ValidationError("Script does not contain any lines to merge.")

        output_dir = self.storage.script_output_dir(resolved_script_path)
        source_paths = self._resolve_source_paths(lines, output_dir)
        missing = [path for path in source_paths if not path.exists()]
        if missing:
            raise MissingFileError(
                "Cannot build preview mix because some synthesized outputs are missing: "
                + ", ".join(path.name for path in missing[:5])
            )

        default_output_name = f"{self.storage.sanitize_fragment(resolved_script_path.stem)}_preview.wav"
        output_path = self.storage.resolve_output_path(
            output_dir,
            output_name or default_output_name,
        )
        if output_path in source_paths:
            raise ValidationError("Preview output name must not overwrite an input segment.")
        if output_path.exists() and not force:
            raise OutputNameCollisionError(
                f"Output already exists: {output_path}. Use `force=true` to overwrite it."
            )

        if use_timeline:
            if any(line.start_ms is None for line in lines):
                raise ValidationError(
                    "Timeline merge requires every script line to provide `start_ms`. "
                    "Use an `.srt` script or timed `.csv`/`.json` input."
                )
            report = self._merge_wav_files_on_timeline(
                script_path=resolved_script_path,
                lines=lines,
                source_paths=source_paths,
                output_path=output_path,
                tail_padding_ms=tail_padding_ms,
            )
        else:
            report = self._merge_wav_files_in_sequence(
                script_path=resolved_script_path,
                source_paths=source_paths,
                output_path=output_path,
                gap_ms=gap_ms,
            )
        self.storage.write_json(output_dir / "preview_mix_report.json", report)
        return report

    def _resolve_source_paths(self, lines: list[ScriptLine], output_dir: Path) -> list[Path]:
        return [self.tts_service.resolve_line_output_path(line, output_dir) for line in lines]

    def _merge_wav_files_in_sequence(
        self,
        *,
        script_path: Path,
        source_paths: list[Path],
        output_path: Path,
        gap_ms: int,
    ) -> AudioMergeReport:
        with wave.open(str(source_paths[0]), "rb") as first_source:
            channels = first_source.getnchannels()
            sample_width = first_source.getsampwidth()
            sample_rate = first_source.getframerate()
            compression_type = first_source.getcomptype()
            compression_name = first_source.getcompname()
            first_frames = first_source.readframes(first_source.getnframes())

        if compression_type != "NONE":
            raise ValidationError(
                f"Unsupported WAV compression for preview merge: {compression_name}."
            )

        gap_frames = int(round(sample_rate * (gap_ms / 1000)))
        silence = b"\x00" * gap_frames * channels * sample_width
        total_frames = 0

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "wb") as target:
            target.setnchannels(channels)
            target.setsampwidth(sample_width)
            target.setframerate(sample_rate)
            target.writeframes(first_frames)
            total_frames += len(first_frames) // (channels * sample_width)

            for source_path in source_paths[1:]:
                with wave.open(str(source_path), "rb") as source:
                    if source.getcomptype() != compression_type:
                        raise ValidationError(
                            f"WAV format mismatch for `{source_path.name}`: compression must match."
                        )
                    if source.getnchannels() != channels:
                        raise ValidationError(
                            f"WAV format mismatch for `{source_path.name}`: channel count must match."
                        )
                    if source.getsampwidth() != sample_width:
                        raise ValidationError(
                            f"WAV format mismatch for `{source_path.name}`: sample width must match."
                        )
                    if source.getframerate() != sample_rate:
                        raise ValidationError(
                            f"WAV format mismatch for `{source_path.name}`: sample rate must match."
                        )
                    if gap_frames > 0:
                        target.writeframes(silence)
                        total_frames += gap_frames
                    frames = source.readframes(source.getnframes())
                    target.writeframes(frames)
                    total_frames += len(frames) // (channels * sample_width)

        duration_ms = int((total_frames / sample_rate) * 1000)
        return AudioMergeReport(
            mode="sequence",
            script_path=script_path,
            output_path=output_path,
            segment_count=len(source_paths),
            gap_ms=gap_ms,
            tail_padding_ms=0,
            duration_ms=duration_ms,
            sample_rate=sample_rate,
            channels=channels,
            sample_width=sample_width,
            source_paths=source_paths,
        )

    def _merge_wav_files_on_timeline(
        self,
        *,
        script_path: Path,
        lines: list[ScriptLine],
        source_paths: list[Path],
        output_path: Path,
        tail_padding_ms: int,
    ) -> AudioMergeReport:
        first_frame_count, first_samples, wav_params = self._read_wav_samples(source_paths[0])
        if wav_params["sample_width"] != 2:
            raise ValidationError(
                "Timeline merge currently supports 16-bit PCM WAV files only."
            )

        segments: list[tuple[int, array[int]]] = []
        first_start_frame = self._ms_to_frames(lines[0].start_ms or 0, wav_params["sample_rate"])
        segments.append((first_start_frame, first_samples))

        max_audio_end_frame = first_start_frame + first_frame_count
        max_timeline_frame = self._ms_to_frames(lines[0].end_ms or 0, wav_params["sample_rate"])

        for line, source_path in zip(lines[1:], source_paths[1:], strict=True):
            frame_count, samples, params = self._read_wav_samples(
                source_path,
                expected_channels=wav_params["channels"],
                expected_sample_width=wav_params["sample_width"],
                expected_sample_rate=wav_params["sample_rate"],
                expected_compression_type=wav_params["compression_type"],
            )
            start_frame = self._ms_to_frames(line.start_ms or 0, wav_params["sample_rate"])
            segments.append((start_frame, samples))
            max_audio_end_frame = max(max_audio_end_frame, start_frame + frame_count)
            if line.end_ms is not None:
                max_timeline_frame = max(
                    max_timeline_frame,
                    self._ms_to_frames(line.end_ms, wav_params["sample_rate"]),
                )

        total_frames = max(max_audio_end_frame, max_timeline_frame) + self._ms_to_frames(
            tail_padding_ms,
            wav_params["sample_rate"],
        )
        total_samples = total_frames * wav_params["channels"]
        mixed_samples = array("h", [0]) * total_samples

        for start_frame, samples in segments:
            start_index = start_frame * wav_params["channels"]
            for offset, sample in enumerate(samples):
                mixed_index = start_index + offset
                mixed_value = mixed_samples[mixed_index] + sample
                if mixed_value > 32767:
                    mixed_value = 32767
                elif mixed_value < -32768:
                    mixed_value = -32768
                mixed_samples[mixed_index] = mixed_value

        if sys.byteorder != "little":
            mixed_samples.byteswap()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "wb") as target:
            target.setnchannels(wav_params["channels"])
            target.setsampwidth(wav_params["sample_width"])
            target.setframerate(wav_params["sample_rate"])
            target.writeframes(mixed_samples.tobytes())

        duration_ms = int((total_frames / wav_params["sample_rate"]) * 1000)
        return AudioMergeReport(
            mode="timeline",
            script_path=script_path,
            output_path=output_path,
            segment_count=len(source_paths),
            gap_ms=0,
            tail_padding_ms=tail_padding_ms,
            duration_ms=duration_ms,
            sample_rate=wav_params["sample_rate"],
            channels=wav_params["channels"],
            sample_width=wav_params["sample_width"],
            source_paths=source_paths,
        )

    def _read_wav_samples(
        self,
        path: Path,
        *,
        expected_channels: int | None = None,
        expected_sample_width: int | None = None,
        expected_sample_rate: int | None = None,
        expected_compression_type: str | None = None,
    ) -> tuple[int, array[int], dict[str, int | str]]:
        with wave.open(str(path), "rb") as source:
            channels = source.getnchannels()
            sample_width = source.getsampwidth()
            sample_rate = source.getframerate()
            compression_type = source.getcomptype()
            compression_name = source.getcompname()

            if compression_type != "NONE":
                raise ValidationError(
                    f"Unsupported WAV compression for preview merge: {compression_name}."
                )
            if expected_channels is not None and channels != expected_channels:
                raise ValidationError(
                    f"WAV format mismatch for `{path.name}`: channel count must match."
                )
            if expected_sample_width is not None and sample_width != expected_sample_width:
                raise ValidationError(
                    f"WAV format mismatch for `{path.name}`: sample width must match."
                )
            if expected_sample_rate is not None and sample_rate != expected_sample_rate:
                raise ValidationError(
                    f"WAV format mismatch for `{path.name}`: sample rate must match."
                )
            if (
                expected_compression_type is not None
                and compression_type != expected_compression_type
            ):
                raise ValidationError(
                    f"WAV format mismatch for `{path.name}`: compression must match."
                )

            frame_count = source.getnframes()
            raw_frames = source.readframes(frame_count)

        if sample_width != 2:
            raise ValidationError(
                f"Unsupported WAV sample width for `{path.name}`: only 16-bit PCM is supported."
            )

        samples = array("h")
        samples.frombytes(raw_frames)
        if sys.byteorder != "little":
            samples.byteswap()

        return frame_count, samples, {
            "channels": channels,
            "sample_width": sample_width,
            "sample_rate": sample_rate,
            "compression_type": compression_type,
        }

    @staticmethod
    def _ms_to_frames(milliseconds: int, sample_rate: int) -> int:
        return int(round(sample_rate * (milliseconds / 1000)))
