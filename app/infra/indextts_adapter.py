from __future__ import annotations

import json
import math
import struct
import sys
import threading
import time
import wave
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request
from uuid import uuid4

from app.core.config import AppSettings
from app.core.exceptions import ModelUnavailableError, SynthesisError


OPTION_NAME_MAP = {
    "emo_audio": "emo_audio_prompt",
    "emo_alpha": "emo_alpha",
    "emo_vector": "emo_vector",
    "emo_text": "emo_text",
    "use_emo_text": "use_emo_text",
    "interval_silence": "interval_silence",
    "temperature": "temperature",
    "top_p": "top_p",
    "top_k": "top_k",
    "max_mel_tokens": "max_mel_tokens",
    "repetition_penalty": "repetition_penalty",
    "length_penalty": "length_penalty",
    "num_beams": "num_beams",
    "use_random": "use_random",
    "max_text_tokens_per_segment": "max_text_tokens_per_segment",
}


class TTSAdapter(Protocol):
    def warmup(self) -> None: ...

    def synthesize(
        self,
        *,
        ref_audio: Path,
        text: str,
        output_path: Path,
        options: Mapping[str, Any],
    ) -> dict[str, Any]: ...


class _MockIndexTTS2:
    def infer(
        self,
        *,
        text: str,
        output_path: str,
        spk_audio_prompt: str,
        **_: Any,
    ) -> dict[str, Any]:
        del spk_audio_prompt
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        duration_seconds = min(max(len(text) * 0.03, 0.4), 3.0)
        sample_rate = 22050
        frame_count = int(duration_seconds * sample_rate)

        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            for index in range(frame_count):
                amplitude = int(1600 * math.sin((2 * math.pi * 220 * index) / sample_rate))
                wav_file.writeframes(struct.pack("<h", amplitude))

        return {"output_path": str(path), "backend": "mock"}


class IndexTTSAdapter:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self._model: Any | None = None
        self._lock = threading.Lock()

    def warmup(self) -> None:
        self._get_model()

    def synthesize(
        self,
        *,
        ref_audio: Path,
        text: str,
        output_path: Path,
        options: Mapping[str, Any],
    ) -> dict[str, Any]:
        model = self._get_model()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        call_kwargs: dict[str, Any] = {
            "text": text,
            "spk_audio_prompt": str(ref_audio),
            "output_path": str(output_path),
            "verbose": False,
        }

        for key, value in options.items():
            if value is None or key not in OPTION_NAME_MAP:
                continue
            mapped_key = OPTION_NAME_MAP[key]
            call_kwargs[mapped_key] = str(value) if isinstance(value, Path) else value

        start_time = time.perf_counter()
        try:
            raw_result = model.infer(**call_kwargs)
        except ModuleNotFoundError as exc:
            raise ModelUnavailableError(
                "IndexTTS2 is not installed in the current environment. "
                "Install the upstream project first, or set "
                "`INDEXTTS_STUDIO_BACKEND=mock` for smoke testing."
            ) from exc
        except Exception as exc:  # pragma: no cover - defensive wrapper
            raise SynthesisError(f"IndexTTS2 inference failed: {exc}") from exc

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        if not output_path.exists():
            raise SynthesisError(
                f"IndexTTS2 completed without creating the output file: {output_path}"
            )

        return {"duration_ms": duration_ms, "raw_result": raw_result}

    def _get_model(self) -> Any:
        if self._model is not None:
            return self._model

        with self._lock:
            if self._model is None:
                self._model = self._build_model()
        return self._model

    def _build_model(self) -> Any:
        if self.settings.model.backend == "mock":
            return _MockIndexTTS2()

        if self.settings.model.package_root is not None:
            package_root = str(self.settings.model.package_root)
            if package_root not in sys.path:
                sys.path.insert(0, package_root)

        try:
            from indextts.infer_v2 import IndexTTS2
        except ModuleNotFoundError as exc:
            raise ModelUnavailableError(
                "Unable to import `indextts.infer_v2.IndexTTS2`. "
                "Install the upstream IndexTTS repository in this environment "
                "or point `INDEXTTS_STUDIO_INDEXTTS_PACKAGE_ROOT` at a checkout."
            ) from exc

        return IndexTTS2(
            cfg_path=str(self.settings.model.cfg_path),
            model_dir=str(self.settings.model.model_dir),
            use_fp16=self.settings.model.use_fp16,
            use_cuda_kernel=self.settings.model.use_cuda_kernel,
            use_deepspeed=self.settings.model.use_deepspeed,
        )


class RemoteGradioAdapter:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.base_url = settings.model.gradio_base_url.rstrip("/")
        self.api_prefix = settings.model.gradio_api_prefix.rstrip("/")
        self.api_name = settings.model.gradio_api_name
        self._lock = threading.Lock()
        self._info_cache: dict[str, Any] | None = None

    def warmup(self) -> None:
        self._request_json("GET", f"{self.base_url}/config")
        self._get_info(force_refresh=True)

    def synthesize(
        self,
        *,
        ref_audio: Path,
        text: str,
        output_path: Path,
        options: Mapping[str, Any],
    ) -> dict[str, Any]:
        uploaded_ref = self._upload_file(ref_audio)
        uploaded_emo = None
        emo_audio = options.get("emo_audio")
        if isinstance(emo_audio, Path):
            uploaded_emo = self._upload_file(emo_audio)

        errors: list[str] = []
        start_time = time.perf_counter()
        for variant in self._build_variants(
            text=text,
            ref_audio=ref_audio,
            uploaded_ref=uploaded_ref,
            emo_audio=emo_audio if isinstance(emo_audio, Path) else None,
            uploaded_emo=uploaded_emo,
            options=options,
        ):
            try:
                event_id = self._request_json(
                    "POST",
                    self._route(f"/call{self.api_name}"),
                    payload={"data": variant},
                )["event_id"]
                event_type, event_payload = self._read_sse_terminal_event(
                    self._route(f"/call{self.api_name}/{event_id}")
                )
                if event_type != "complete":
                    raise SynthesisError(self._format_terminal_error(event_type, event_payload))

                remote_output = self._extract_remote_output(event_payload)
                self._download_to(remote_output, output_path)
                return {
                    "duration_ms": int((time.perf_counter() - start_time) * 1000),
                    "raw_result": remote_output,
                }
            except SynthesisError as exc:
                errors.append(exc.message)

        joined = " | ".join(errors) if errors else "unknown remote error"
        raise SynthesisError(
            "Remote Gradio synthesis failed after trying multiple payload variants. "
            f"Details: {joined}"
        )

    def _build_variants(
        self,
        *,
        text: str,
        ref_audio: Path,
        uploaded_ref: str,
        emo_audio: Path | None,
        uploaded_emo: str | None,
        options: Mapping[str, Any],
    ) -> Iterable[list[Any]]:
        file_data_ref = self._build_file_data(ref_audio, uploaded_ref)
        file_data_emo = (
            self._build_file_data(emo_audio, uploaded_emo)
            if emo_audio is not None and uploaded_emo is not None
            else None
        )
        common_tail = [
            float(options.get("emo_alpha", 0.65)),
            *self._emotion_vector_values(options.get("emo_vector")),
            options.get("emo_text") or "",
            bool(options.get("emo_random", False)),
            int(options.get("max_text_tokens_per_segment", 120)),
            bool(options.get("do_sample", options.get("use_random", True))),
            float(options.get("top_p", 0.8)),
            int(options.get("top_k", 30)),
            float(options.get("temperature", 0.8)),
            float(options.get("length_penalty", 0.0)),
            int(options.get("num_beams", 3)),
            float(options.get("repetition_penalty", 10.0)),
            int(options.get("max_mel_tokens", 1500)),
        ]

        prompt_candidates: list[Any] = [file_data_ref]
        emo_candidates: list[Any] = [None]
        if file_data_emo is not None:
            emo_candidates.insert(0, file_data_emo)
        mode_candidates = self._emotion_mode_candidates(options)

        for mode in mode_candidates:
            for prompt in prompt_candidates:
                for emo_input in emo_candidates:
                    yield [mode, prompt, text, emo_input, *common_tail]

    def _resolve_emotion_mode(self, options: Mapping[str, Any]) -> tuple[int, str]:
        if options.get("use_emo_text"):
            return 3, "使用情感描述文本控制"
        if options.get("emo_vector"):
            return 2, "使用情感向量控制"
        if options.get("emo_audio") is not None:
            return 1, "使用情感参考音频"
        return 0, "与音色参考音频相同"

    def _emotion_mode_candidates(self, options: Mapping[str, Any]) -> list[Any]:
        mode_key = self._resolve_emotion_mode_key(options)
        choices = self._available_emotion_mode_choices()
        if choices:
            matches = [
                choice for choice in choices if self._matches_emotion_mode_choice(choice, mode_key)
            ]
            if matches:
                return matches
            if mode_key == "text":
                raise SynthesisError(
                    "The remote IndexTTS WebUI does not expose an emotion-text control mode."
                )

        fallback: dict[str, list[Any]] = {
            "same": ["Same as the voice reference", "与音色参考音频相同", 0],
            "audio": ["Use emotion reference audio", "使用情感参考音频", 1],
            "vector": ["Use emotion vectors", "使用情感向量", 2],
            "text": ["Use emotion description text", "使用情感描述文本控制", 3],
        }
        return fallback[mode_key]

    def _resolve_emotion_mode_key(self, options: Mapping[str, Any]) -> str:
        if options.get("use_emo_text"):
            return "text"
        if options.get("emo_vector"):
            return "vector"
        if options.get("emo_audio") is not None:
            return "audio"
        return "same"

    def _available_emotion_mode_choices(self) -> list[str]:
        endpoint = self._get_named_endpoint(self.api_name)
        parameters = endpoint.get("parameters")
        if not isinstance(parameters, list):
            return []
        for parameter in parameters:
            if not isinstance(parameter, dict):
                continue
            if parameter.get("parameter_name") != "emo_control_method":
                continue
            type_info = parameter.get("type")
            if not isinstance(type_info, dict):
                return []
            enum_values = type_info.get("enum")
            if not isinstance(enum_values, list):
                return []
            return [str(item) for item in enum_values]
        return []

    def _get_named_endpoint(self, api_name: str) -> dict[str, Any]:
        info = self._get_info()
        endpoints = info.get("named_endpoints")
        if not isinstance(endpoints, dict):
            return {}
        endpoint = endpoints.get(api_name)
        if isinstance(endpoint, dict):
            return endpoint
        return {}

    def _get_info(self, *, force_refresh: bool = False) -> dict[str, Any]:
        with self._lock:
            if self._info_cache is not None and not force_refresh:
                return self._info_cache
        response = self._request_json("GET", self._route("/info"))
        info = response if isinstance(response, dict) else {}
        with self._lock:
            self._info_cache = info
        return info

    def _matches_emotion_mode_choice(self, choice: str, mode_key: str) -> bool:
        normalized = choice.strip().lower()
        if mode_key == "same":
            return "same as the voice reference" in normalized or (
                "音色" in choice and "相同" in choice
            )
        if mode_key == "audio":
            return "emotion reference audio" in normalized or (
                "情感" in choice and "参考" in choice and "音频" in choice
            )
        if mode_key == "vector":
            return (
                "emotion vectors" in normalized
                or "emotion vector" in normalized
                or "向量" in choice
            )
        return (
            "emotion description" in normalized
            or "emotion text" in normalized
            or ("情感" in choice and "文本" in choice)
        )

    def _emotion_vector_values(self, value: Any) -> list[float]:
        if isinstance(value, list):
            vector = [float(item) for item in value[:8]]
            while len(vector) < 8:
                vector.append(0.0)
            return vector
        return [0.0] * 8

    def _build_file_data(self, local_path: Path | None, uploaded_path: str | None) -> dict[str, Any]:
        if local_path is None or uploaded_path is None:
            raise SynthesisError("Missing local or uploaded path for remote file input.")
        return {
            "path": uploaded_path,
            "url": self._remote_file_url(uploaded_path),
            "size": local_path.stat().st_size,
            "orig_name": local_path.name,
            "mime_type": self._guess_mime_type(local_path),
            "is_stream": False,
            "meta": {"_type": "gradio.FileData"},
        }

    def _upload_file(self, file_path: Path) -> str:
        path = file_path.resolve()
        boundary = "----IndexTTSStudio" + uuid4().hex
        body = (
            f"--{boundary}\r\n".encode("utf-8")
            + f'Content-Disposition: form-data; name="files"; filename="{path.name}"\r\n'.encode(
                "utf-8"
            )
            + f"Content-Type: {self._guess_mime_type(path)}\r\n\r\n".encode("utf-8")
            + path.read_bytes()
            + f"\r\n--{boundary}--\r\n".encode("utf-8")
        )
        response = self._request_json(
            "POST",
            self._route("/upload"),
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        if not isinstance(response, list) or not response:
            raise SynthesisError(f"Unexpected Gradio upload response: {response!r}")
        return str(response[0])

    def _read_sse_terminal_event(self, url: str) -> tuple[str, Any]:
        request_obj = urllib_request.Request(url, method="GET")
        try:
            with urllib_request.urlopen(request_obj, timeout=300) as response:
                event_type: str | None = None
                event_data: str | None = None
                for raw_line in response:
                    line = raw_line.decode("utf-8").strip()
                    if not line:
                        if event_type in {"complete", "error"}:
                            break
                        event_type = None
                        event_data = None
                        continue
                    if line.startswith("event:"):
                        event_type = line.partition(":")[2].strip()
                    elif line.startswith("data:"):
                        event_data = line.partition(":")[2].strip()
                if event_type is None:
                    raise SynthesisError("Remote Gradio queue did not return an event type.")
                payload = json.loads(event_data) if event_data and event_data != "null" else None
                return event_type, payload
        except urllib_error.URLError as exc:
            raise SynthesisError(f"Failed to read Gradio queue stream: {exc}") from exc

    def _extract_remote_output(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, list) or not payload:
            raise SynthesisError(f"Unexpected Gradio completion payload: {payload!r}")
        first = payload[0]
        if isinstance(first, dict) and "value" in first and isinstance(first["value"], dict):
            candidate = dict(first["value"])
        elif isinstance(first, dict):
            candidate = dict(first)
        else:
            raise SynthesisError(f"Unexpected Gradio output payload: {payload!r}")

        if "url" not in candidate and "path" in candidate:
            candidate["url"] = self._remote_file_url(str(candidate["path"]))
        if "url" not in candidate:
            raise SynthesisError(f"Missing output URL in Gradio payload: {candidate!r}")
        return candidate

    def _download_to(self, remote_output: Mapping[str, Any], destination: Path) -> None:
        url = str(remote_output["url"])
        request_obj = urllib_request.Request(url, method="GET")
        try:
            with urllib_request.urlopen(request_obj, timeout=300) as response:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(response.read())
        except urllib_error.URLError as exc:
            raise SynthesisError(f"Failed to download remote audio output: {exc}") from exc

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        payload: Any | None = None,
        data: bytes | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        if payload is not None and data is not None:
            raise ValueError("Use either `payload` or raw `data`, not both.")
        body = json.dumps(payload).encode("utf-8") if payload is not None else data
        request_headers = {"Accept": "application/json"}
        if payload is not None:
            request_headers["Content-Type"] = "application/json"
        if headers:
            request_headers.update(headers)
        request_obj = urllib_request.Request(url, data=body, method=method, headers=request_headers)
        try:
            with urllib_request.urlopen(request_obj, timeout=60) as response:
                content = response.read().decode("utf-8")
        except urllib_error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "ignore")
            raise SynthesisError(
                f"Remote Gradio request failed with HTTP {exc.code}: {detail or exc.reason}"
            ) from exc
        except urllib_error.URLError as exc:
            raise SynthesisError(f"Remote Gradio request failed: {exc}") from exc
        if not content:
            return None
        return json.loads(content)

    def _format_terminal_error(self, event_type: str, payload: Any) -> str:
        if isinstance(payload, dict):
            for key in ("error", "message", "detail"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return f"Remote Gradio queue returned `{event_type}`: {value.strip()}"
        if isinstance(payload, str) and payload.strip():
            return f"Remote Gradio queue returned `{event_type}`: {payload.strip()}"
        return f"Remote Gradio queue returned `{event_type}` without details."

    def _route(self, suffix: str) -> str:
        normalized_suffix = suffix if suffix.startswith("/") else f"/{suffix}"
        return f"{self.base_url}{self.api_prefix}{normalized_suffix}"

    def _remote_file_url(self, remote_path: str) -> str:
        encoded = urllib_parse.quote(remote_path, safe="/")
        return self._route(f"/file={encoded}")

    @staticmethod
    def _guess_mime_type(path: Path) -> str:
        if path.suffix.lower() == ".wav":
            return "audio/wav"
        if path.suffix.lower() == ".mp3":
            return "audio/mpeg"
        return "application/octet-stream"
