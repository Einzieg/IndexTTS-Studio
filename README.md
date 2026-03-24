# IndexTTS-Studio

[简体中文](./README.md) | [English](./README.en.md)

IndexTTS-Studio 是一个基于 `IndexTTS2` 构建的本地多角色配音工作流。

当前同时支持两套使用方式：

- 基于脚本文件的 `CLI / REST API` 流程，支持 `CSV`、`JSON`、`SRT`
- 基于项目的 Web UI 流程，用于管理项目、分集、角色、文本配音表、任务和导出

## 功能概览

- 使用 `uv` 管理 Python 项目
- 所有运行配置统一由根目录 `.env` 驱动
- 支持 `official`、`mock`、`remote_gradio` 三种后端
- 支持基于 `.env` 账号密码的登录鉴权
- 项目和分集由服务端自动生成 ID
- 角色与参考音频按项目隔离
- 文本配音表按“项目 + 分集”持久化保存到服务端
- 支持行级文本配音、行级参数覆盖、行级试听
- 支持文件持久化的串行异步任务队列，服务重启后自动恢复待处理任务
- 支持普通预览合并和 SRT 时间轴合并
- 支持从文本配音表一键导出当前分集音频
- 支持 Docker 镜像构建与 `docker compose` 运行

当前 Studio 导出文件命名格式：

```text
项目-项目名-分集-分集名-行号-角色名.wav
```

## 快速开始

1. 安装 Python 依赖：

```bash
uv sync --group dev
```

2. 如有需要，从 `.env.example` 复制并生成 `.env`。

当前示例配置已经默认指向本地 WSL 中运行的 Gradio 后端 `http://127.0.0.1:7861`：

```text
INDEXTTS_STUDIO_BACKEND=remote_gradio
INDEXTTS_STUDIO_GRADIO_BASE_URL=http://127.0.0.1:7861
```

3. 如果 `web/dist` 不存在，或者你修改过前端代码，先构建 Web UI：

```bash
cd web
npm install
npm run build
```

4. 启动后端服务：

```bash
uv run indextts-studio serve
```

5. 打开 Web UI：

```text
http://127.0.0.1:8000/ui
```

如果启用了登录鉴权，直接访问 `http://127.0.0.1:8000/` 或 `/ui` 会先进入登录页。

6. 或者直接通过 CLI 执行脚本批量配音：

```bash
uv run indextts-studio batch --script data/scripts/episode1.csv
```

## Docker

仓库现在已经提供：

- [`Dockerfile`](./Dockerfile)
- [`docker-compose.yml`](./docker-compose.yml)
- [`.env.example`](./.env.example)
- [`.github/workflows/ci.yml`](./.github/workflows/ci.yml)
- [`.github/workflows/release.yml`](./.github/workflows/release.yml)
- [`docker/index-tts/Dockerfile`](./docker/index-tts/Dockerfile)
- [`docker/index-tts/entrypoint.sh`](./docker/index-tts/entrypoint.sh)

默认的 Compose 流程会直接把 `studio` 和 `index-tts` 一起准备好，只需要拉取这个仓库，然后执行：

```bash
docker compose up --build
```

流程会自构建容器：

- `studio` 容器由当前仓库构建，负责 FastAPI 和 Web UI
- `index-tts` 容器也由当前仓库内置的 Dockerfile 构建
- 构建 `index-tts` 镜像时，会自动从官方仓库拉取上游源码
- 构建时会主动跳过上游仓库里的 LFS 示例音频，因此官方仓库的 LFS 配额超限也不会阻塞容器构建
- 首次启动 `index-tts` 容器时，如果发现模型权重不存在，会自动下载到持久化卷
- 后续重启会复用已经下载好的模型，不会每次重复下载
- `studio` 会等待 `index-tts` 健康后再启动，首次拉模型时会慢一些，这属于正常现象
- 首次拉模型期间，`index-tts` 会先显示为“启动中”；只要模型引导进程还在运行，就不会再被误判为启动失败
- 模型引导日志会定期打印当前已落盘体积、文件数和仍缺的关键文件，便于判断是在正常下载还是卡住

当前附带的 `docker-compose.yml` 已经为 `index-tts` 服务声明 `gpus: all`，默认会把可用 GPU 透传给上游模型容器。Docker 和本地运行统一共用根目录 `.env`；本地保留 `127.0.0.1` 这类地址，容器相关差异通过 `INDEXTTS_STUDIO_DOCKER_*` 变量覆盖。你可以在 [`.env`](./.env) 或 [`.env.example`](./.env.example) 里调整这些变量：

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

说明：

- `INDEXTTS_MODEL_SOURCE=auto` 会优先尝试 Hugging Face，失败后再回退到 ModelScope
- 如果你有 Hugging Face 令牌，可以直接写到根目录 `.env` 的 `HF_TOKEN=`，这样下载更稳、限速更少
- `HF_ENDPOINT` 也统一从根目录 `.env` 配置，只有在你使用镜像站时才需要填写；留空即可
- `docker compose` 会读取同一份 `.env`，并只在容器里覆盖少量网络相关变量，所以不需要再维护第二份 `.env.docker`
- 如果你想只启动 `studio`，可以执行 `docker compose up studio`
- 如果你当前环境拉取 Docker Hub 的 CUDA 基础镜像不稳定，可以把 `INDEXTTS_CUDA_BASE_IMAGE` 改成你自己的镜像站地址
- 如果你想让 `studio` 容器直接跑 `official` 后端，则需要另外制作 CUDA 版镜像，当前这个 slim Python 镜像不适合直接跑模型
- 宿主机侧仍然需要先具备 GPU 容器运行条件，例如 Linux 上的 NVIDIA Container Toolkit，或者 Docker Desktop 对 Linux 容器的 GPU 支持

当前容器化默认配置走 `remote_gradio`，并把上游服务地址指向：

```text
http://index-tts:7861
```

也就是说，`studio` 会直接通过同一个 `indextts-studio-net` 网络中的服务名访问内置的 `index-tts` 容器。

如果你的 `index-tts` 是单独启动的容器，也可以手动让它加入这个网络，例如：

```bash
docker network create indextts-studio-net
docker run --gpus all --name index-tts --network indextts-studio-net ...
```

## 配置说明

所有运行时配置都从项目根目录的 `.env` 加载。

相关文件：

- `.env`：当前实际生效的本地配置
- `.env.example`：配置模板

其中 Docker 相关的覆盖项也放在同一份 `.env` 中，例如：

- `INDEXTTS_STUDIO_DOCKER_HOST`
- `INDEXTTS_STUDIO_DOCKER_PORT`
- `INDEXTTS_STUDIO_DOCKER_WARMUP_ON_STARTUP`
- `INDEXTTS_STUDIO_DOCKER_GRADIO_BASE_URL`
- `INDEXTTS_CUDA_BASE_IMAGE`
- `HF_TOKEN`

常用配置项：

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

完整配置项见 [`.env.example`](./.env.example)。

## 登录鉴权

Web UI 和大部分 API 现在支持基于 `.env` 的账号密码登录。

最小配置示例：

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

说明：

- 当 `INDEXTTS_STUDIO_AUTH_ENABLED=true` 时，未登录用户访问 `/ui` 会先看到登录页
- 登录页账号密码来自服务端根目录 `.env`
- `INDEXTTS_STUDIO_AUTH_SESSION_SECRET` 留空时，系统会基于项目路径和账号信息生成一个会话签名密钥；正式部署建议显式填写
- 如果你通过 HTTPS 暴露服务，建议同时设置 `INDEXTTS_STUDIO_AUTH_SECURE_COOKIE=true`
- 当前公开放行的路径主要是 `/`、`/ui`、`/health` 和 `/auth/*`

当前认证相关接口：

- `GET /auth/session`
- `POST /auth/login`
- `POST /auth/logout`

## 后端模式

### `remote_gradio`

当官方 IndexTTS2 Gradio UI 已经运行时使用，例如在 WSL 中：

```text
INDEXTTS_STUDIO_BACKEND=remote_gradio
INDEXTTS_STUDIO_GRADIO_BASE_URL=http://127.0.0.1:7861
```

这个适配器会自动走 Gradio 队列接口，并上传参考音频。

### `official`

当你希望在当前 Python 环境内直接导入上游 `indextts` 包时使用：

```text
INDEXTTS_STUDIO_BACKEND=official
INDEXTTS_STUDIO_INDEXTTS_PACKAGE_ROOT=D:\Code\index-tts
INDEXTTS_STUDIO_MODEL_DIR=D:\Code\index-tts\checkpoints
INDEXTTS_STUDIO_MODEL_CFG=D:\Code\index-tts\checkpoints\config.yaml
```

### `mock`

用于无真实模型时的烟测：

```text
INDEXTTS_STUDIO_BACKEND=mock
```

## Web UI

Web UI 位于 `web/`，执行 `npm run build` 后由 FastAPI 挂载到 `/ui`。

当前页面结构：

- `#/projects`：创建、删除项目和分集
- `#/roles`：管理当前项目下的角色，上传参考音频，设置默认参数，删除角色
- `#/studio`：维护当前项目 + 分集的文本配音表，配置行参数，生成选中行，跳过或覆盖已有配音，试听单句，并导出当前分集
- `#/jobs`：查看异步任务和逐行结果

当前行为：

- 项目 ID 和分集 ID 由服务端自动生成
- 当前项目和分集显示在顶部导航栏
- 当前项目 / 分集选择会保存在浏览器本地
- 文本配音表保存到服务端，并按项目 + 分集共享
- 一键导出会把每一行“当前选中的配音版本”打包成 zip

前端开发模式：

```bash
cd web
npm install
npm run dev
```

前端开发服务器会从同一个根目录 `.env` 读取：

- `VITE_API_TARGET`
- `VITE_UI_DEV_HOST`
- `VITE_UI_DEV_PORT`

## 远程协作部署

如果你希望把 `studio` 部署到服务器，同时继续使用你本地机器的 GPU 跑 `index-tts`，当前架构是支持的。

推荐拓扑：

- 浏览器 -> 服务器上的 `studio`
- 服务器上的 `studio` -> 你本地机器上的 `index-tts` Gradio 服务

服务器侧常见配置：

```text
INDEXTTS_STUDIO_BACKEND=remote_gradio
INDEXTTS_STUDIO_HOST=0.0.0.0
INDEXTTS_STUDIO_PORT=8000
INDEXTTS_STUDIO_GRADIO_BASE_URL=http://<你的本地机器可达地址>:7861
INDEXTTS_STUDIO_AUTH_ENABLED=true
```

更稳妥的做法：

- 使用 `Tailscale`、`WireGuard` 或其他内网组网方式，让服务器安全访问你本地的 `7861`
- 给 `studio` 再套一层反向代理，例如 `Nginx` 或 `Caddy`
- 对外开放时启用 HTTPS，并把 `INDEXTTS_STUDIO_AUTH_SECURE_COOKIE=true`

需要注意：

- 跨服务器时不能依赖“同一个 Docker 网络”，必须依赖 VPN、隧道或可达的内网地址
- 当前任务队列已经支持文件持久化和重启恢复，但本质上仍然是单进程序列队列，更适合小团队协作，不适合高并发公共服务
- 当前生成结果会先由服务器端 `studio` 拉回本地存储，再供前端试听和导出
- 如果直接裸露公网，即使启用了登录，也仍然建议额外加反向代理和访问控制

## 发布流程

仓库现在内置了两条 GitHub Actions 工作流：

- [`.github/workflows/ci.yml`](./.github/workflows/ci.yml)
  用于日常提交校验，会执行后端测试、前端构建和 `docker compose config`
- [`.github/workflows/release.yml`](./.github/workflows/release.yml)
  当推送版本标签 `v*` 时，会自动执行校验、创建 GitHub Release，并发布 GHCR 镜像

当前发布的镜像命名约定：

- `ghcr.io/<你的 GitHub 用户名或组织名>/indextts-studio:<tag>`
- `ghcr.io/<你的 GitHub 用户名或组织名>/indextts-upstream:<tag>`

一个最小发布示例：

```bash
git tag v0.2.0
git push origin v0.2.0
```

工作流会自动完成：

- `uv run pytest -q`
- `web` 前端构建
- `docker compose config`
- `studio` 镜像发布到 GHCR
- `index-tts` 镜像发布到 GHCR
- GitHub Release 创建

## 数据目录

按项目隔离的数据位于 `data/projects/`：

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

说明：

- `data/projects/...` 是当前 Web UI 主流程使用的核心存储目录
- `data/jobs/...` 用于持久化异步任务队列和任务状态，服务重启后会自动恢复 `queued/running` 任务
- `data/scripts/...` 和 `data/refs/...` 依然适合 CLI / API 示例脚本和历史样例

## CLI

启动 API：

```bash
uv run indextts-studio serve
```

单句合成：

```bash
uv run indextts-studio single --speaker "主角A" --text "今天必须把事情查清楚。"
```

运行一个批量脚本：

```bash
uv run indextts-studio batch --script data/scripts/episode1.csv
```

运行一个带时间轴的 SRT 批量脚本：

```bash
uv run indextts-studio batch --script data/scripts/episode1.srt
```

运行一个带逐行 override 的批量脚本：

```bash
uv run indextts-studio batch --script data/scripts/episode1_overrides.json
```

重生某一条脚本行：

```bash
uv run indextts-studio regenerate --script data/scripts/episode1.csv --line-id 2 --force
```

把一个脚本合并成预览 WAV：

```bash
uv run indextts-studio merge --script data/scripts/episode1.csv --gap-ms 250 --force
```

按 SRT 时间轴合并预览：

```bash
uv run indextts-studio merge --script data/scripts/episode1.srt --use-timeline --tail-padding-ms 250 --force
```

说明：

- CLI 目前仍然是基于脚本文件驱动
- 项目 / 分集的文本配音表管理目前主要在 Web UI 和 REST API 中使用

## REST API

启动服务：

```bash
uv run indextts-studio serve
```

在线接口文档：

```text
http://127.0.0.1:8000/docs
```

主要接口分组：

- 健康检查
  - `GET /health`
- 认证
  - `GET /auth/session`
  - `POST /auth/login`
  - `POST /auth/logout`
- 项目
  - `GET /projects`
  - `GET /projects/{project_id}`
  - `POST /projects`
  - `DELETE /projects/{project_id}`
  - `POST /projects/{project_id}/episodes`
  - `DELETE /projects/{project_id}/episodes/{episode_id}`
- 角色
  - `GET /speakers`
  - `GET /speakers/profiles`
  - `GET /speakers/{speaker_name}`
  - `POST /speakers`
  - `DELETE /speakers/{speaker_name}`
- 脚本工具
  - `GET /scripts`
  - `GET /scripts/preview`
- 文本配音表
  - `GET /scripts/table`
  - `PUT /scripts/table`
  - `GET /scripts/table/export`
- TTS
  - `POST /tts/single`
  - `POST /tts/batch`
  - `POST /tts/regenerate`
- 任务
  - `GET /jobs/capabilities`
  - `POST /jobs`
  - `POST /jobs/from-lines`
  - `GET /jobs`
  - `GET /jobs/{job_id}`
  - `GET /jobs/{job_id}/lines`
- 音频
  - `GET /audio/capabilities`
  - `POST /audio/merge`
- 文件预览
  - `GET /files/audio`

示例：

创建项目：

```bash
curl -X POST http://127.0.0.1:8000/projects ^
  -H "Content-Type: application/json" ^
  -d "{\"name\":\"示例项目\"}"
```

创建分集：

```bash
curl -X POST http://127.0.0.1:8000/projects/<project_id>/episodes ^
  -H "Content-Type: application/json" ^
  -d "{\"name\":\"第1集\"}"
```

读取某个项目 + 分集的文本配音表：

```bash
curl "http://127.0.0.1:8000/scripts/table?project_id=<project_id>&episode_id=<episode_id>"
```

按 Web UI 行数据提交一个内联异步任务：

```bash
curl -X POST http://127.0.0.1:8000/jobs/from-lines ^
  -H "Content-Type: application/json" ^
  -d "{\"project_id\":\"<project_id>\",\"episode_id\":\"<episode_id>\",\"lines\":[{\"id\":\"row-1\",\"speaker\":\"主角A\",\"text\":\"今天必须把事情查清楚。\"}]}"
```

导出当前分集的文本配音表音频：

```bash
curl -L "http://127.0.0.1:8000/scripts/table/export?project_id=<project_id>&episode_id=<episode_id>" --output studio_export.zip
```

## 脚本格式

### SRT

`.srt` 可以直接作为批量配音脚本使用。

每个字幕块都需要用以下两种形式之一声明说话人：

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

当调用 `/audio/merge` 且 `use_timeline=true` 时，生成的 WAV 会按照每个字幕块的 `start_ms` 放置到时间轴上。

### 逐行参数覆盖

批量脚本支持两种逐行参数覆盖方式：

1. 在 CSV 或 JSON 顶层直接写 `temperature`、`top_p`、`top_k`、`interval_silence`、`emo_text`、`use_emo_text`、`emo_vector` 等字段
2. 在 JSON 中提供一个嵌套的 `override` 对象

支持的逐行字段包括：

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

优先级：

- API 或运行时显式传入的 override
- 脚本逐行 override
- 角色默认参数
- 系统默认参数

## 项目结构

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

## 测试

后端测试：

```bash
uv run pytest
```

前端生产构建：

```bash
cd web
npm run build
```

自动化后端测试默认使用内置 `mock` 后端，因此不需要真实下载 IndexTTS2 模型。
