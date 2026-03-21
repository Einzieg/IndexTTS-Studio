from __future__ import annotations

import json
import threading
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from app.core.config import AppSettings
from app.infra.indextts_adapter import RemoteGradioAdapter


def _make_wav_bytes() -> bytes:
    import io
    import math
    import struct

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(22050)
        for index in range(2205):
            amplitude = int(900 * math.sin((2 * math.pi * 220 * index) / 22050))
            wav_file.writeframes(struct.pack("<h", amplitude))
    return buffer.getvalue()


class _FakeGradioHandler(BaseHTTPRequestHandler):
    response_wav = _make_wav_bytes()
    last_payload: dict[str, Any] | None = None

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/config":
            self._send_json({"api_prefix": "/gradio_api"})
            return
        if self.path == "/gradio_api/info":
            self._send_json({"named_endpoints": {"/gen_single": {}}})
            return
        if self.path == "/gradio_api/call/gen_single/event-1":
            payload = [
                {
                    "value": {
                        "path": "/tmp/gradio/output.wav",
                        "url": f"http://127.0.0.1:{self.server.server_port}/gradio_api/file=/tmp/gradio/output.wav",  # type: ignore[attr-defined]
                        "orig_name": "output.wav",
                        "meta": {"_type": "gradio.FileData"},
                    },
                    "__type__": "update",
                }
            ]
            body = f"event: complete\ndata: {json.dumps(payload)}\n\n".encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/gradio_api/file=/tmp/gradio/output.wav":
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(self.response_wav)))
            self.end_headers()
            self.wfile.write(self.response_wav)
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)

        if self.path == "/gradio_api/upload":
            self._send_json(["/tmp/gradio/ref.wav"])
            return

        if self.path == "/gradio_api/call/gen_single":
            _FakeGradioHandler.last_payload = json.loads(body.decode("utf-8"))
            self._send_json({"event_id": "event-1"})
            return

        self.send_error(404)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        del format, args

    def _send_json(self, payload: Any) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def test_remote_gradio_adapter_downloads_output(
    studio_settings: AppSettings,
    studio_root: Path,
) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeGradioHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        studio_settings.model.backend = "remote_gradio"
        studio_settings.model.gradio_base_url = f"http://127.0.0.1:{server.server_port}"
        adapter = RemoteGradioAdapter(studio_settings)
        adapter.warmup()

        output_path = studio_root / "data" / "outputs" / "remote_test.wav"
        result = adapter.synthesize(
            ref_audio=studio_root / "data" / "refs" / "hero_a.wav",
            text="远程适配器测试。",
            output_path=output_path,
            options={
                "temperature": 0.8,
                "top_p": 0.8,
                "top_k": 30,
                "max_mel_tokens": 1500,
                "num_beams": 3,
                "repetition_penalty": 10.0,
                "length_penalty": 0.0,
                "max_text_tokens_per_segment": 120,
                "use_random": True,
            },
        )

        assert output_path.exists()
        assert result["duration_ms"] >= 0

        payload = _FakeGradioHandler.last_payload
        assert payload is not None
        assert len(payload["data"]) == 24
        assert payload["data"][2] == "远程适配器测试。"
    finally:
        server.shutdown()
        server.server_close()
