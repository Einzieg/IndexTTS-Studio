ARG INDEXTTS_CUDA_BASE_IMAGE=nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04
FROM ${INDEXTTS_CUDA_BASE_IMAGE}

ARG INDEXTTS_UPSTREAM_REPO=https://github.com/index-tts/index-tts.git
ARG INDEXTTS_UPSTREAM_REF=main

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    INDEXTTS_MODEL_DIR=/opt/index-tts/checkpoints \
    INDEXTTS_WEBUI_HOST=0.0.0.0 \
    INDEXTTS_WEBUI_PORT=7861

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        ffmpeg \
        git \
        git-lfs \
        libsndfile1 \
        python-is-python3 \
        python3 \
        python3-pip \
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv "huggingface_hub[hf_xet]" modelscope

RUN git lfs install --skip-smudge --system

WORKDIR /opt

RUN GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 --branch ${INDEXTTS_UPSTREAM_REF} ${INDEXTTS_UPSTREAM_REPO} index-tts

WORKDIR /opt/index-tts

RUN uv sync --frozen --no-dev --extra webui

COPY docker/index-tts/bootstrap_models.py /usr/local/bin/index-tts-bootstrap-models.py
COPY docker/index-tts/entrypoint.sh /usr/local/bin/index-tts-entrypoint

RUN chmod +x /usr/local/bin/index-tts-entrypoint

EXPOSE 7861

ENTRYPOINT ["index-tts-entrypoint"]
