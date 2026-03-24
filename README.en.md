# IndexTTS-Studio

[简体中文（默认）](./README.md) | [English](./README.en.md)

IndexTTS-Studio is a local multi-speaker dubbing workflow built on top of `IndexTTS2`.

It supports two parallel workflows:

- a script-driven CLI / REST API flow for `CSV`, `JSON`, and `SRT`
- a project-scoped Web UI for managing projects, episodes, speakers, text rows, jobs, and exports

## Highlights

- `uv`-managed Python project
- root `.env`-driven runtime configuration
- `official`, `mock`, and `remote_gradio` backends
- `.env`-backed username/password authentication
- project and episode management with auto-generated IDs
- project-isolated speaker profiles and reference audio uploads
- server-persisted Studio table per project + episode
- inline text dubbing, row-level overrides, and row-level auditioning
- file-backed serial async jobs with startup recovery for pending work
- preview merge and SRT timeline merge
- one-click export from the Studio table
- Docker image build and `docker compose` deployment

Current Studio export naming format:

```text
项目-项目名-分集-分集名-行号-角色名.wav
```

## Quick Start

1. Install Python dependencies:

```bash
uv sync --group dev
```

2. Create `.env` from `.env.example` if needed.

The provided example is already set up for a local WSL Gradio backend on `http://127.0.0.1:7861`:

```text
INDEXTTS_STUDIO_BACKEND=remote_gradio
INDEXTTS_STUDIO_GRADIO_BASE_URL=http://127.0.0.1:7861
```

3. Build the Web UI if `web/dist` is missing or if you changed frontend code:

```bash
cd web
npm install
npm run build
```

4. Start the backend:

```bash
uv run indextts-studio serve
```

5. Open the Web UI:

```text
http://127.0.0.1:8000/ui
```

If authentication is enabled, visiting `http://127.0.0.1:8000/` or `/ui` will show the login screen first.

6. Or run a script-driven batch job from the CLI:

```bash
uv run indextts-studio batch --script data/scripts/episode1.csv
```

## Docker

The repository now includes:

- [`Dockerfile`](./Dockerfile)
- [`docker-compose.yml`](./docker-compose.yml)
- [`.env.example`](./.env.example)
- [`.github/workflows/ci.yml`](./.github/workflows/ci.yml)
- [`.github/workflows/release.yml`](./.github/workflows/release.yml)
- [`docker/index-tts/Dockerfile`](./docker/index-tts/Dockerfile)
- [`docker/index-tts/entrypoint.sh`](./docker/index-tts/entrypoint.sh)

The default Compose flow now bootstraps both containers from this repository:

```bash
docker compose up --build
```

What happens in this setup:

- `studio` is built from this repository and serves the API + Web UI
- `index-tts` is also built from this repository through [`docker/index-tts/Dockerfile`](./docker/index-tts/Dockerfile)
- the upstream official `index-tts` source is cloned automatically during image build
- LFS example audio is intentionally skipped during build, so upstream Git LFS quota overruns do not block container creation
- on first container startup, checkpoints are downloaded automatically into a persistent Docker volume
- later restarts reuse the cached checkpoints and do not download them again
- `studio` waits for `index-tts` to become healthy before starting, so the first boot can take a while while checkpoints download
- during the first checkpoint bootstrap, `index-tts` is treated as starting rather than failed as long as the bootstrap process is still running
- bootstrap logs now periodically report downloaded size, file count, and remaining required files so you can distinguish normal progress from a stall

The bundled Compose config requests GPU access for the `index-tts` service with `gpus: all`.
Docker and local runs now share the same root `.env`; local values such as `127.0.0.1` stay in the standard keys, while container-only differences are overridden with `INDEXTTS_STUDIO_DOCKER_*`.
You can adjust the relevant settings in [`.env`](./.env) or [`.env.example`](./.env.example):

```text
INDEXTTS_STUDIO_DOCKER_HOST=0.0.0.0
INDEXTTS_STUDIO_DOCKER_PORT=8000
INDEXTTS_STUDIO_DOCKER_WARMUP_ON_STARTUP=false
INDEXTTS_STUDIO_DOCKER_GRADIO_BASE_URL=http://index-tts:7861
INDEXTTS_CUDA_BASE_IMAGE=nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04
INDEXTTS_UPSTREAM_REPO=https://github.com/index-tts/index-tts.git
INDEXTTS_UPSTREAM_REF=main
INDEXTTS_MODEL_SOURCE=auto
INDEXTTS_MODEL_REPO=IndexTeam/IndexTTS-2
INDEXTTS_MODELSCOPE_MODEL_ID=IndexTeam/IndexTTS-2
HF_TOKEN=
HF_ENDPOINT=
INDEXTTS_NVIDIA_VISIBLE_DEVICES=all
INDEXTTS_NVIDIA_DRIVER_CAPABILITIES=compute,utility
```

Notes:

- this GPU mapping is meant for the bundled upstream `index-tts` container, because the default Docker workflow uses `remote_gradio`
- the `studio` container itself does not need GPU in this setup
- if you want to run the `official` backend inside the `studio` container, you will need a separate CUDA-enabled image rather than the current slim Python image
- Docker still needs host-side GPU support to be available first, for example NVIDIA Container Toolkit on Linux or Docker Desktop GPU support for Linux containers
- `INDEXTTS_MODEL_SOURCE=auto` tries Hugging Face first and then falls back to ModelScope
- if you have a Hugging Face token, put it in the root `.env` as `HF_TOKEN=` for more reliable downloads and higher limits
- `HF_ENDPOINT` is also configured through the root `.env`; leave it blank unless you are intentionally using a mirror endpoint
- `docker compose` now reads the same `.env`, with only a few container-network overrides layered on top, so there is no separate `.env.docker` to maintain
- if you want to use only the Studio container, run `docker compose up studio`
- if Docker Hub access is flaky in your environment, you can point `INDEXTTS_CUDA_BASE_IMAGE` to a mirrored CUDA base image

The containerized default uses `remote_gradio` and targets:

```text
http://index-tts:7861
```

So the Studio container can always reach the bundled `index-tts` service by name on the internal `indextts-studio-net` network.

If your `index-tts` container is started separately, you can also attach it to the same network manually, for example:

```bash
docker network create indextts-studio-net
docker run --gpus all --name index-tts --network indextts-studio-net ...
```

## Configuration

All runtime configuration is loaded from the project root `.env`.

Files:

- `.env`: active local configuration
- `.env.example`: reference template

Docker-specific overrides also live in the same `.env`, for example:

- `INDEXTTS_STUDIO_DOCKER_HOST`
- `INDEXTTS_STUDIO_DOCKER_PORT`
- `INDEXTTS_STUDIO_DOCKER_WARMUP_ON_STARTUP`
- `INDEXTTS_STUDIO_DOCKER_GRADIO_BASE_URL`
- `INDEXTTS_CUDA_BASE_IMAGE`
- `HF_TOKEN`

Common keys:

- `INDEXTTS_STUDIO_BACKEND`
- `INDEXTTS_STUDIO_GRADIO_BASE_URL`
- `INDEXTTS_STUDIO_AUTH_ENABLED`
- `INDEXTTS_STUDIO_AUTH_USERNAME`
- `INDEXTTS_STUDIO_AUTH_PASSWORD`
- `INDEXTTS_STUDIO_AUTH_SESSION_SECRET`
- `INDEXTTS_STUDIO_HOST`
- `INDEXTTS_STUDIO_PORT`
- `INDEXTTS_STUDIO_WARMUP_ON_STARTUP`
- `INDEXTTS_STUDIO_DATA_DIR`
- `INDEXTTS_STUDIO_JOBS_DIR`
- `VITE_API_TARGET`
- `VITE_UI_DEV_HOST`
- `VITE_UI_DEV_PORT`

For the full list, see [`.env.example`](./.env.example).

## Authentication

The Web UI and most API routes can now be protected with username/password authentication from the root `.env`.

Minimal example:

```text
INDEXTTS_STUDIO_AUTH_ENABLED=true
INDEXTTS_STUDIO_AUTH_USERNAME=admin
INDEXTTS_STUDIO_AUTH_PASSWORD=admin123
INDEXTTS_STUDIO_AUTH_SESSION_SECRET=
INDEXTTS_STUDIO_AUTH_COOKIE_NAME=indextts_studio_session
INDEXTTS_STUDIO_AUTH_SESSION_TTL_SECONDS=43200
INDEXTTS_STUDIO_AUTH_SECURE_COOKIE=false
INDEXTTS_STUDIO_AUTH_SAME_SITE=lax
```

Notes:

- when `INDEXTTS_STUDIO_AUTH_ENABLED=true`, unauthenticated users will see the login page before entering `/ui`
- credentials come from the server-side root `.env`
- if `INDEXTTS_STUDIO_AUTH_SESSION_SECRET` is left blank, the app derives a signing secret from the project path and configured credentials; for real deployments, setting an explicit secret is recommended
- if you expose the service over HTTPS, also set `INDEXTTS_STUDIO_AUTH_SECURE_COOKIE=true`
- public routes are intentionally limited to `/`, `/ui`, `/health`, and `/auth/*`

Authentication endpoints:

- `GET /auth/session`
- `POST /auth/login`
- `POST /auth/logout`

## Backend Modes

### `remote_gradio`

Use this when the official IndexTTS2 Gradio UI is already running, for example inside WSL:

```text
INDEXTTS_STUDIO_BACKEND=remote_gradio
INDEXTTS_STUDIO_GRADIO_BASE_URL=http://127.0.0.1:7861
```

The adapter talks to the Gradio queue API and uploads reference audio automatically.

### `official`

Use this when you want to import the upstream `indextts` package inside the current Python environment:

```text
INDEXTTS_STUDIO_BACKEND=official
INDEXTTS_STUDIO_INDEXTTS_PACKAGE_ROOT=D:\Code\index-tts
INDEXTTS_STUDIO_MODEL_DIR=D:\Code\index-tts\checkpoints
INDEXTTS_STUDIO_MODEL_CFG=D:\Code\index-tts\checkpoints\config.yaml
```

### `mock`

Use this for smoke tests without a real model:

```text
INDEXTTS_STUDIO_BACKEND=mock
```

## Web UI

The Web UI lives in `web/` and is served by FastAPI from `/ui` after `npm run build`.

Current page structure:

- `#/projects`: create and delete projects and episodes
- `#/roles`: manage speakers for the current project, upload reference audio, set default options, delete speakers
- `#/studio`: edit the dubbing table for the current project + episode, configure rows, generate selected rows, skip or overwrite existing renders, audition line audio, and export the current episode
- `#/jobs`: inspect async jobs and line-level results

Current behavior:

- project IDs and episode IDs are generated by the server
- the current project and episode are shown in the top navigation
- current project / episode selection is remembered in the browser
- the Studio table itself is saved on the server and shared by project + episode
- one-click export packages the current selected render for each row into a zip archive

Frontend dev server:

```bash
cd web
npm install
npm run dev
```

The frontend dev server reads the same root `.env` for:

- `VITE_API_TARGET`
- `VITE_UI_DEV_HOST`
- `VITE_UI_DEV_PORT`

## Remote Collaboration Deployment

If you want to host `studio` on a server while continuing to run `index-tts` on your local GPU machine, the current architecture supports it.

Recommended topology:

- teammate browser -> server-hosted `studio`
- server-hosted `studio` -> your locally hosted `index-tts` Gradio service

Typical server-side settings:

```text
INDEXTTS_STUDIO_BACKEND=remote_gradio
INDEXTTS_STUDIO_HOST=0.0.0.0
INDEXTTS_STUDIO_PORT=8000
INDEXTTS_STUDIO_GRADIO_BASE_URL=http://<reachable-local-host>:7861
INDEXTTS_STUDIO_AUTH_ENABLED=true
```

Safer deployment choices:

- use `Tailscale`, `WireGuard`, or another private network so the server can reach your local `7861`
- put `studio` behind a reverse proxy such as `Nginx` or `Caddy`
- enable HTTPS and set `INDEXTTS_STUDIO_AUTH_SECURE_COOKIE=true`

Important caveats:

- across different machines, you cannot rely on “the same Docker network”; you need VPN, tunneling, or another reachable private address
- the current job queue is now file-backed and restart-safe, but it is still a single-process serial queue rather than a high-concurrency distributed worker system
- generated audio is pulled back into the server-side `studio` storage before it is previewed or exported in the UI
- even with built-in login enabled, exposing the service directly to the public internet is not recommended without a reverse proxy and additional access control

## Release Workflow

The repository now includes two GitHub Actions workflows:

- [`.github/workflows/ci.yml`](./.github/workflows/ci.yml)
  for everyday validation on pushes to `main` and pull requests
- [`.github/workflows/release.yml`](./.github/workflows/release.yml)
  for tag-driven releases that create a GitHub Release and publish GHCR images

Published image naming convention:

- `ghcr.io/<your GitHub user or org>/indextts-studio:<tag>`
- `ghcr.io/<your GitHub user or org>/indextts-upstream:<tag>`

Minimal release example:

```bash
git tag v0.2.0
git push origin v0.2.0
```

The release workflow will automatically:

- run `uv run pytest -q`
- build the `web` frontend
- validate `docker compose config`
- publish the `studio` image to GHCR
- publish the `index-tts` image to GHCR
- create the matching GitHub Release

## Data Layout

Project-scoped data is stored under `data/projects/`:

```text
data/
  projects/
    <project_id>/
      speakers.json
      refs/
      scripts/
        <episode_id>/
          studio_table.json
      outputs/
        <episode_id>/
          ...
  jobs/
  refs/
  scripts/
  outputs/
  logs/
```

Notes:

- `data/projects/...` is the primary storage used by the Web UI
- `data/jobs/...` stores the persistent async queue state, and `queued/running` jobs are recovered on service startup
- `data/scripts/...` and `data/refs/...` are still useful for script-driven CLI / API examples and legacy samples

## CLI

Run the API:

```bash
uv run indextts-studio serve
```

Synthesize a single line:

```bash
uv run indextts-studio single --speaker "主角A" --text "今天必须把事情查清楚。"
```

Run a batch script:

```bash
uv run indextts-studio batch --script data/scripts/episode1.csv
```

Run a timed SRT batch script:

```bash
uv run indextts-studio batch --script data/scripts/episode1.srt
```

Run a batch script with per-line overrides:

```bash
uv run indextts-studio batch --script data/scripts/episode1_overrides.json
```

Regenerate one script line:

```bash
uv run indextts-studio regenerate --script data/scripts/episode1.csv --line-id 2 --force
```

Merge one script into a preview WAV:

```bash
uv run indextts-studio merge --script data/scripts/episode1.csv --gap-ms 250 --force
```

Merge an SRT script on its subtitle timeline:

```bash
uv run indextts-studio merge --script data/scripts/episode1.srt --use-timeline --tail-padding-ms 250 --force
```

Notes:

- the CLI remains script-driven
- project / episode table management currently lives in the Web UI and REST API

## REST API

Start the service:

```bash
uv run indextts-studio serve
```

Interactive docs:

```text
http://127.0.0.1:8000/docs
```

Key endpoint groups:

- Health
  - `GET /health`
- Auth
  - `GET /auth/session`
  - `POST /auth/login`
  - `POST /auth/logout`
- Projects
  - `GET /projects`
  - `GET /projects/{project_id}`
  - `POST /projects`
  - `DELETE /projects/{project_id}`
  - `POST /projects/{project_id}/episodes`
  - `DELETE /projects/{project_id}/episodes/{episode_id}`
- Speakers
  - `GET /speakers`
  - `GET /speakers/profiles`
  - `GET /speakers/{speaker_name}`
  - `POST /speakers`
  - `DELETE /speakers/{speaker_name}`
- Script utilities
  - `GET /scripts`
  - `GET /scripts/preview`
- Studio table
  - `GET /scripts/table`
  - `PUT /scripts/table`
  - `GET /scripts/table/export`
- TTS
  - `POST /tts/single`
  - `POST /tts/batch`
  - `POST /tts/regenerate`
- Jobs
  - `GET /jobs/capabilities`
  - `POST /jobs`
  - `POST /jobs/from-lines`
  - `GET /jobs`
  - `GET /jobs/{job_id}`
  - `GET /jobs/{job_id}/lines`
- Audio
  - `GET /audio/capabilities`
  - `POST /audio/merge`
- File preview
  - `GET /files/audio`

Examples:

Create a project:

```bash
curl -X POST http://127.0.0.1:8000/projects ^
  -H "Content-Type: application/json" ^
  -d "{\"name\":\"示例项目\"}"
```

Create an episode:

```bash
curl -X POST http://127.0.0.1:8000/projects/<project_id>/episodes ^
  -H "Content-Type: application/json" ^
  -d "{\"name\":\"第1集\"}"
```

Load the Studio table for one project + episode:

```bash
curl "http://127.0.0.1:8000/scripts/table?project_id=<project_id>&episode_id=<episode_id>"
```

Queue an inline job from Web-style rows:

```bash
curl -X POST http://127.0.0.1:8000/jobs/from-lines ^
  -H "Content-Type: application/json" ^
  -d "{\"project_id\":\"<project_id>\",\"episode_id\":\"<episode_id>\",\"lines\":[{\"id\":\"row-1\",\"speaker\":\"主角A\",\"text\":\"今天必须把事情查清楚。\"}]}"
```

Export the current episode from the Studio table:

```bash
curl -L "http://127.0.0.1:8000/scripts/table/export?project_id=<project_id>&episode_id=<episode_id>" --output studio_export.zip
```

## Script Formats

### SRT

`.srt` scripts can be used directly for batch synthesis.

Each subtitle block must declare a speaker in one of these forms:

```text
1
00:00:00,000 --> 00:00:01,200
主角A: 今天必须把事情查清楚。
```

```text
2
00:00:01,500 --> 00:00:02,300
[旁白]
夜色渐深，真相开始浮出水面。
```

When you call `/audio/merge` with `use_timeline=true`, generated WAV files are placed according to each subtitle block's `start_ms`.

### Per-line overrides

Batch scripts can override generation parameters per line in two forms:

1. top-level CSV or JSON fields such as `temperature`, `top_p`, `top_k`, `interval_silence`, `emo_text`, `use_emo_text`, or `emo_vector`
2. a nested `override` object in JSON scripts

Supported line-level fields include:

- `emo_audio`
- `emo_alpha`
- `emo_vector`
- `emo_text`
- `use_emo_text`
- `text_split_method`
- `interval_silence`
- `temperature`
- `top_p`
- `top_k`
- `max_mel_tokens`
- `repetition_penalty`
- `length_penalty`
- `num_beams`
- `use_random`
- `max_text_tokens_per_segment`

Precedence:

- API or explicit runtime override
- line-level script override
- speaker defaults
- system defaults

## Project Layout

```text
app/
  api/
  core/
  domain/
  infra/
  services/
data/
  projects/
  refs/
  scripts/
  outputs/
  logs/
tests/
web/
```

## Testing

Backend tests:

```bash
uv run pytest
```

Frontend production build:

```bash
cd web
npm run build
```

The automated backend tests use the built-in `mock` backend, so they do not require a real IndexTTS2 model download.
