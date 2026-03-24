#!/usr/bin/env bash
set -euo pipefail

cd /opt/index-tts

if [[ -z "${HF_ENDPOINT:-}" ]]; then
  unset HF_ENDPOINT
fi

if [[ -z "${HF_TOKEN:-}" ]]; then
  unset HF_TOKEN
fi

if [[ "${INDEXTTS_FORCE_CPU:-false}" == "true" ]]; then
  export CUDA_VISIBLE_DEVICES=""
fi

python /usr/local/bin/index-tts-bootstrap-models.py

args=(
  --host "${INDEXTTS_WEBUI_HOST:-0.0.0.0}"
  --port "${INDEXTTS_WEBUI_PORT:-7861}"
)

if [[ "${INDEXTTS_WEBUI_FP16:-true}" == "true" ]]; then
  args+=(--fp16)
fi

exec uv run python webui.py "${args[@]}"
