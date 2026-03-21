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
- 项目和分集由服务端自动生成 ID
- 角色与参考音频按项目隔离
- 文本配音表按“项目 + 分集”持久化保存到服务端
- 支持行级文本配音、行级参数覆盖、行级试听
- 支持异步任务和逐行状态轮询
- 支持普通预览合并和 SRT 时间轴合并
- 支持从文本配音表一键导出当前分集音频

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

6. 或者直接通过 CLI 执行脚本批量配音：

```bash
uv run indextts-studio batch --script data/scripts/episode1.csv
```

## 配置说明

所有运行时配置都从项目根目录的 `.env` 加载。

相关文件：

- `.env`：当前实际生效的本地配置
- `.env.example`：配置模板

常用配置项：

- `INDEXTTS_STUDIO_BACKEND`
- `INDEXTTS_STUDIO_GRADIO_BASE_URL`
- `INDEXTTS_STUDIO_HOST`
- `INDEXTTS_STUDIO_PORT`
- `INDEXTTS_STUDIO_WARMUP_ON_STARTUP`
- `INDEXTTS_STUDIO_DATA_DIR`
- `VITE_API_TARGET`
- `VITE_UI_DEV_HOST`
- `VITE_UI_DEV_PORT`

完整配置项见 [`.env.example`](./.env.example)。

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
  refs/
  scripts/
  outputs/
  logs/
```

说明：

- `data/projects/...` 是当前 Web UI 主流程使用的核心存储目录
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
