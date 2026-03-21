import {
  AlertTriangle,
  Check,
  CheckCircle2,
  CircleDashed,
  Copy,
  Download,
  LoaderCircle,
  Plus,
  Settings2,
  SkipForward,
  Trash2,
  WandSparkles,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";

import { AudioCard, EmptyState, FieldLabel, ToggleTile } from "../components";
import {
  audioPreviewUrl,
  buildOverride,
  formatClock,
  formatDuration,
  requestJson,
  statusClasses,
} from "../lib";
import type {
  GenerationOptions,
  JobLinesPayload,
  JobSummary,
  Notice,
  ProjectConfig,
  SingleResult,
  SpeakerProfile,
} from "../types";

type RenderSource = "batch" | "config";

type RowRender = {
  renderId: string;
  outputPath: string;
  durationMs: number;
  createdAt: string;
  source: RenderSource;
  usedOptions: Record<string, unknown>;
};

type StudioRow = {
  rowId: string;
  speaker: string;
  text: string;
  selected: boolean;
  override: GenerationOptions;
  renders: RowRender[];
  selectedRenderId: string | null;
  lastStatus: "idle" | "generating" | "done" | "skipped" | "failed";
  lastError: string | null;
};

type ConfigFormState = {
  temperature: string;
  topP: string;
  topK: string;
  intervalSilence: string;
  numBeams: string;
  repetitionPenalty: string;
  lengthPenalty: string;
  maxMelTokens: string;
  maxTextTokensPerSegment: string;
  emoText: string;
  textSplitMethod: string;
  emoVector: string;
  useEmoText: boolean;
  useRandom: boolean;
};

type BatchSyncState = {
  jobId: string;
  queuedRowIds: string[];
  preSkipped: number;
  preFailed: number;
};

type StudioTablePayload = {
  projectId: string;
  episodeId: string;
  rows: StudioRow[];
  updatedAt: string;
};

const LEGACY_DRAFT_PREFIX = "indextts-studio:episode-draft";

function createEmptyConfigForm(): ConfigFormState {
  return {
    temperature: "",
    topP: "",
    topK: "",
    intervalSilence: "",
    numBeams: "",
    repetitionPenalty: "",
    lengthPenalty: "",
    maxMelTokens: "",
    maxTextTokensPerSegment: "",
    emoText: "",
    textSplitMethod: "",
    emoVector: "",
    useEmoText: false,
    useRandom: true,
  };
}

function configFormFromOverride(override: GenerationOptions): ConfigFormState {
  return {
    temperature: override.temperature?.toString() ?? "",
    topP: override.top_p?.toString() ?? "",
    topK: override.top_k?.toString() ?? "",
    intervalSilence: override.interval_silence?.toString() ?? "",
    numBeams: override.num_beams?.toString() ?? "",
    repetitionPenalty: override.repetition_penalty?.toString() ?? "",
    lengthPenalty: override.length_penalty?.toString() ?? "",
    maxMelTokens: override.max_mel_tokens?.toString() ?? "",
    maxTextTokensPerSegment: override.max_text_tokens_per_segment?.toString() ?? "",
    emoText: override.emo_text ?? "",
    textSplitMethod: override.text_split_method ?? "",
    emoVector: override.emo_vector ? JSON.stringify(override.emo_vector) : "",
    useEmoText: override.use_emo_text ?? false,
    useRandom: override.use_random ?? true,
  };
}

function overrideFromConfigForm(form: ConfigFormState): GenerationOptions {
  const override = buildOverride({
    temperature: form.temperature,
    topP: form.topP,
    topK: form.topK,
    intervalSilence: form.intervalSilence,
    numBeams: form.numBeams,
    repetitionPenalty: form.repetitionPenalty,
    lengthPenalty: form.lengthPenalty,
    emoText: form.emoText,
    textSplitMethod: form.textSplitMethod,
    emoVector: form.emoVector,
    useEmoText: form.useEmoText,
    useRandom: form.useRandom,
  });

  if (form.maxMelTokens.trim()) {
    const value = Number(form.maxMelTokens);
    if (Number.isFinite(value)) {
      override.max_mel_tokens = value;
    }
  }
  if (form.maxTextTokensPerSegment.trim()) {
    const value = Number(form.maxTextTokensPerSegment);
    if (Number.isFinite(value)) {
      override.max_text_tokens_per_segment = value;
    }
  }

  return override;
}

function makeId(): string {
  if ("randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `id-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function createEmptyRow(defaultSpeaker: string, index: number): StudioRow {
  return {
    rowId: makeId(),
    speaker: defaultSpeaker,
    text: "",
    selected: index === 1,
    override: {},
    renders: [],
    selectedRenderId: null,
    lastStatus: "idle",
    lastError: null,
  };
}

function sanitizeFragment(value: string, fallback: string): string {
  const sanitized = value
    .trim()
    .replace(/[<>:"/\\|?*\x00-\x1f]/g, "_")
    .replace(/\s+/g, "_")
    .replace(/[._ ]+$/g, "");
  return sanitized || fallback;
}

function buildOutputName(row: StudioRow, source: RenderSource, episodeId: string): string {
  const stamp = `${Date.now()}_${Math.random().toString(16).slice(2, 6)}`;
  return [
    sanitizeFragment(episodeId, "episode"),
    sanitizeFragment(row.rowId, "line"),
    sanitizeFragment(row.speaker, "speaker"),
    source,
    stamp,
  ].join("_") + ".wav";
}

function displayRowStatus(status: StudioRow["lastStatus"]): string {
  if (status === "idle") {
    return "未生成";
  }
  if (status === "generating") {
    return "生成中";
  }
  if (status === "done") {
    return "已生成";
  }
  if (status === "skipped") {
    return "已跳过";
  }
  return "失败";
}

function RowStatusIcon(props: { status: StudioRow["lastStatus"] }) {
  if (props.status === "done") {
    return <CheckCircle2 className="h-3.5 w-3.5" />;
  }
  if (props.status === "generating") {
    return <LoaderCircle className="h-3.5 w-3.5 animate-spin" />;
  }
  if (props.status === "skipped") {
    return <SkipForward className="h-3.5 w-3.5" />;
  }
  if (props.status === "failed") {
    return <AlertTriangle className="h-3.5 w-3.5" />;
  }
  return <CircleDashed className="h-3.5 w-3.5" />;
}

function selectedRenderForRow(row: StudioRow): RowRender | null {
  if (row.selectedRenderId) {
    const selectedRender = row.renders.find((render) => render.renderId === row.selectedRenderId);
    if (selectedRender) {
      return selectedRender;
    }
  }
  return row.renders[row.renders.length - 1] ?? null;
}

function resolveDownloadFilename(disposition: string | null, fallback: string): string {
  if (!disposition) {
    return fallback;
  }
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    return decodeURIComponent(utf8Match[1]);
  }
  const plainMatch = disposition.match(/filename="?([^";]+)"?/i);
  return plainMatch?.[1] ?? fallback;
}

function legacyDraftStorageKey(projectId: string, episodeId: string): string {
  return `${LEGACY_DRAFT_PREFIX}:${projectId}:${episodeId}`;
}

function normalizeRows(rows: StudioRow[] | undefined, defaultSpeaker: string): StudioRow[] {
  const sourceRows = Array.isArray(rows) ? rows : [];
  if (sourceRows.length === 0) {
    return [createEmptyRow(defaultSpeaker, 1)];
  }
  return sourceRows.map((row) => ({
    rowId: row.rowId || makeId(),
    speaker: row.speaker || defaultSpeaker,
    text: row.text || "",
    selected: Boolean(row.selected),
    override: row.override || {},
    renders: Array.isArray(row.renders) ? row.renders : [],
    selectedRenderId: row.selectedRenderId ?? null,
    lastStatus: row.lastStatus ?? "idle",
    lastError: row.lastError ?? null,
  }));
}

function loadLegacyRows(projectId: string, episodeId: string, defaultSpeaker: string): StudioRow[] {
  try {
    const raw = window.localStorage.getItem(legacyDraftStorageKey(projectId, episodeId));
    if (!raw) {
      return [createEmptyRow(defaultSpeaker, 1)];
    }
    const decoded = JSON.parse(raw) as { rows?: StudioRow[] };
    return normalizeRows(decoded.rows, defaultSpeaker);
  } catch {
    return [createEmptyRow(defaultSpeaker, 1)];
  }
}

function buildEpisodeOptions(project: ProjectConfig | null): Array<{ id: string; name: string }> {
  if (!project) {
    return [];
  }
  return project.episodes.map((episode) => ({ id: episode.id, name: episode.name }));
}

export function StudioPage(props: {
  project: ProjectConfig | null;
  activeEpisodeId: string;
  speakers: SpeakerProfile[];
  setNotice: (notice: Notice) => void;
  onLatestResult: (result: SingleResult) => void;
  onJobQueued: (jobId: string) => Promise<void> | void;
}) {
  const activeProjectId = props.project?.id ?? "";
  const speakerNames = props.speakers.map((speaker) => speaker.name);
  const firstSpeaker = speakerNames[0] ?? "";
  const episodeOptions = useMemo(() => buildEpisodeOptions(props.project), [props.project]);
  const [rows, setRows] = useState<StudioRow[]>([]);
  const [existingBehavior, setExistingBehavior] = useState<"skip" | "overwrite">("skip");
  const [isGeneratingSelection, setIsGeneratingSelection] = useState(false);
  const [activeConfigRowId, setActiveConfigRowId] = useState<string | null>(null);
  const [configForm, setConfigForm] = useState<ConfigFormState>(createEmptyConfigForm);
  const [isGeneratingFromConfig, setIsGeneratingFromConfig] = useState(false);
  const [activeBatchSync, setActiveBatchSync] = useState<BatchSyncState | null>(null);
  const [isRowsLoading, setIsRowsLoading] = useState(false);
  const [isRowsHydrated, setIsRowsHydrated] = useState(false);
  const [isExporting, setIsExporting] = useState(false);

  useEffect(() => {
    if (!activeProjectId || !props.activeEpisodeId) {
      setRows([]);
      setActiveBatchSync(null);
      setIsRowsHydrated(false);
      return;
    }

    let cancelled = false;
    setIsRowsLoading(true);
    setIsRowsHydrated(false);

    const loadRows = async () => {
      try {
        const payload = await requestJson<StudioTablePayload>(
          `/scripts/table?project_id=${encodeURIComponent(activeProjectId)}&episode_id=${encodeURIComponent(props.activeEpisodeId)}`,
        );
        if (cancelled) {
          return;
        }

        let nextRows = normalizeRows(payload.rows, firstSpeaker);
        if (payload.rows.length === 0) {
          nextRows = loadLegacyRows(activeProjectId, props.activeEpisodeId, firstSpeaker);
        }

        setRows(nextRows);
        setActiveConfigRowId(null);
        setActiveBatchSync(null);
        setIsRowsHydrated(true);
      } catch (error) {
        if (cancelled) {
          return;
        }
        setRows([createEmptyRow(firstSpeaker, 1)]);
        setActiveConfigRowId(null);
        setActiveBatchSync(null);
        setIsRowsHydrated(false);
        props.setNotice({
          tone: "error",
          message: error instanceof Error ? error.message : "加载文本工作台失败。",
        });
      } finally {
        if (!cancelled) {
          setIsRowsLoading(false);
        }
      }
    };

    void loadRows();

    return () => {
      cancelled = true;
    };
  }, [activeProjectId, firstSpeaker, props.activeEpisodeId, props.setNotice]);

  useEffect(() => {
    if (!activeProjectId || !props.activeEpisodeId || !isRowsHydrated) {
      return;
    }

    let cancelled = false;
    const timer = window.setTimeout(() => {
      void requestJson<StudioTablePayload>("/scripts/table", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: activeProjectId,
          episode_id: props.activeEpisodeId,
          rows,
        }),
      })
        .then(() => {
          window.localStorage.removeItem(legacyDraftStorageKey(activeProjectId, props.activeEpisodeId));
        })
        .catch((error) => {
          if (!cancelled) {
            props.setNotice({
              tone: "error",
              message: error instanceof Error ? error.message : "保存文本工作台失败。",
            });
          }
        });
    }, 350);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [activeProjectId, isRowsHydrated, props.activeEpisodeId, props.setNotice, rows]);

  useEffect(() => {
    if (!firstSpeaker) {
      return;
    }
    setRows((current) => {
      if (current.length === 0) {
        return [createEmptyRow(firstSpeaker, 1)];
      }
      return current.map((row) => ({
        ...row,
        speaker: speakerNames.includes(row.speaker) ? row.speaker : firstSpeaker,
      }));
    });
  }, [firstSpeaker, speakerNames.join("|")]);

  useEffect(() => {
    if (activeConfigRowId && !rows.some((row) => row.rowId === activeConfigRowId)) {
      setActiveConfigRowId(null);
    }
  }, [activeConfigRowId, rows]);

  const selectedRows = useMemo(() => rows.filter((row) => row.selected), [rows]);
  const exportableRowCount = useMemo(
    () => rows.filter((row) => selectedRenderForRow(row)).length,
    [rows],
  );
  const activeConfigRow = useMemo(
    () => rows.find((row) => row.rowId === activeConfigRowId) ?? null,
    [activeConfigRowId, rows],
  );
  const activeSelectedRender =
    (activeConfigRow ? selectedRenderForRow(activeConfigRow) : null);
  const activeRenderList = activeConfigRow ? [...activeConfigRow.renders].reverse() : [];

  useEffect(() => {
    if (!activeConfigRow) {
      return;
    }
    const originalBodyOverflow = document.body.style.overflow;
    const originalHtmlOverflow = document.documentElement.style.overflow;
    document.body.style.overflow = "hidden";
    document.documentElement.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = originalBodyOverflow;
      document.documentElement.style.overflow = originalHtmlOverflow;
    };
  }, [activeConfigRow]);

  function updateRow(rowId: string, patch: Partial<StudioRow>) {
    setRows((current) =>
      current.map((row) => (row.rowId === rowId ? { ...row, ...patch } : row)),
    );
  }

  function addRow() {
    setRows((current) => [...current, createEmptyRow(firstSpeaker, current.length + 1)]);
  }

  function removeRow(rowId: string) {
    setRows((current) => {
      if (current.length === 1) {
        return current;
      }
      return current.filter((row) => row.rowId !== rowId);
    });
  }

  function removeSelectedRows() {
    setRows((current) => {
      const remaining = current.filter((row) => !row.selected);
      return remaining.length > 0 ? remaining : [createEmptyRow(firstSpeaker, 1)];
    });
  }

  function toggleSelectAll(checked: boolean) {
    setRows((current) => current.map((row) => ({ ...row, selected: checked })));
  }

  function openConfig(row: StudioRow) {
    setActiveConfigRowId(row.rowId);
    setConfigForm(configFormFromOverride(row.override));
  }

  function saveConfigToRow() {
    if (!activeConfigRow) {
      return;
    }
    updateRow(activeConfigRow.rowId, { override: overrideFromConfigForm(configForm) });
    props.setNotice({
      tone: "success",
      message: "已保存当前行的详细参数。",
    });
  }

  function setSelectedRender(rowId: string, renderId: string) {
    setRows((current) =>
      current.map((row) => (row.rowId === rowId ? { ...row, selectedRenderId: renderId } : row)),
    );
  }

  async function exportCurrentEpisode() {
    if (!props.project) {
      props.setNotice({ tone: "error", message: "请先选择一个项目。" });
      return;
    }
    if (!props.activeEpisodeId) {
      props.setNotice({ tone: "error", message: "请先选择一个分集。" });
      return;
    }

    setIsExporting(true);
    try {
      const response = await fetch(
        `/scripts/table/export?project_id=${encodeURIComponent(activeProjectId)}&episode_id=${encodeURIComponent(props.activeEpisodeId)}`,
      );
      if (!response.ok) {
        let message = "导出失败。";
        try {
          const payload = (await response.json()) as { message?: string };
          if (payload.message) {
            message = payload.message;
          }
        } catch {
          // Ignore JSON parsing failures and fall back to the default message.
        }
        throw new Error(message);
      }

      const blob = await response.blob();
      const downloadName = resolveDownloadFilename(
        response.headers.get("Content-Disposition"),
        `项目-${props.project.name}-分集-${props.activeEpisodeId}-导出.zip`,
      );
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = downloadUrl;
      link.download = downloadName;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(downloadUrl);

      const exportedCount = Number(response.headers.get("X-Exported-Count") ?? exportableRowCount);
      props.setNotice({
        tone: "success",
        message: `已导出 ${exportedCount} 条配音，下载文件已开始。`,
      });
    } catch (error) {
      props.setNotice({
        tone: "error",
        message: error instanceof Error ? error.message : "导出失败。",
      });
    } finally {
      setIsExporting(false);
    }
  }

  function duplicateRow(row: StudioRow) {
    setRows((current) => [
      ...current,
      {
        ...createEmptyRow(row.speaker, current.length + 1),
        speaker: row.speaker,
        text: row.text,
        selected: false,
        override: { ...row.override },
      },
    ]);
  }

  function buildBatchLines(
    targetRows: StudioRow[],
    options: {
      overwriteExisting: boolean;
    },
  ): {
    queuedLines: Array<{
      id: string;
      scene: string;
      speaker: string;
      text: string;
      output_name: string;
      override: GenerationOptions;
    }>;
    skippedRowIds: string[];
    failedRows: Array<{ rowId: string; error: string }>;
  } {
    const queuedLines: Array<{
      id: string;
      scene: string;
      speaker: string;
      text: string;
      output_name: string;
      override: GenerationOptions;
    }> = [];
    const skippedRowIds: string[] = [];
    const failedRows: Array<{ rowId: string; error: string }> = [];

    for (const row of targetRows) {
      const selectedRender = selectedRenderForRow(row);

      if (!row.speaker || !row.text.trim()) {
        failedRows.push({ rowId: row.rowId, error: "角色和台词都不能为空。" });
        continue;
      }

      if (!options.overwriteExisting && selectedRender) {
        skippedRowIds.push(row.rowId);
        continue;
      }

      queuedLines.push({
        id: row.rowId,
        scene: "web",
        speaker: row.speaker,
        text: row.text.trim(),
        output_name: buildOutputName(row, "batch", props.activeEpisodeId),
        override: row.override,
      });
    }

    return { queuedLines, skippedRowIds, failedRows };
  }

  function syncRowsFromLines(lines: JobLinesPayload["items"], queuedRowIds: string[]) {
    const queuedSet = new Set(queuedRowIds);
    const linesById = new Map(lines.map((line) => [line.line_id, line]));

    setRows((current) =>
      current.map((row) => {
        if (!queuedSet.has(row.rowId)) {
          return row;
        }

        const line = linesById.get(row.rowId);
        if (!line) {
          return row;
        }

        const nextStatus =
          line.status === "done" || line.status === "skipped" || line.status === "failed"
            ? line.status
            : "generating";

        let renders = row.renders;
        let selectedRenderId = row.selectedRenderId;
        if (line.output_path && (line.status === "done" || line.status === "skipped")) {
          const existingRender = row.renders.find((render) => render.outputPath === line.output_path);
          if (existingRender) {
            renders = row.renders.map((render) =>
              render.renderId === existingRender.renderId
                ? {
                    ...render,
                    durationMs: line.duration_ms,
                    usedOptions: line.override ?? render.usedOptions,
                  }
                : render,
            );
            selectedRenderId = existingRender.renderId;
          } else {
            const render: RowRender = {
              renderId: makeId(),
              outputPath: line.output_path,
              durationMs: line.duration_ms,
              createdAt: new Date().toISOString(),
              source: "batch",
              usedOptions: line.override ?? {},
            };
            renders = [...row.renders, render];
            selectedRenderId = render.renderId;
          }
        }

        return {
          ...row,
          override: (line.override as GenerationOptions) || row.override,
          renders,
          selectedRenderId,
          lastStatus: nextStatus,
          lastError: line.error ?? null,
        };
      }),
    );
  }

  useEffect(() => {
    if (!activeBatchSync) {
      return;
    }

    let cancelled = false;
    let timer: number | null = null;

    const poll = async () => {
      try {
        const [job, linesPayload] = await Promise.all([
          requestJson<JobSummary>(`/jobs/${activeBatchSync.jobId}`),
          requestJson<JobLinesPayload>(`/jobs/${activeBatchSync.jobId}/lines`),
        ]);
        if (cancelled) {
          return;
        }

        syncRowsFromLines(linesPayload.items, activeBatchSync.queuedRowIds);

        if (["completed", "completed_with_errors", "failed"].includes(job.status)) {
          const totalSkipped = activeBatchSync.preSkipped + job.skipped;
          const totalFailed = activeBatchSync.preFailed + job.failed;
          props.setNotice({
            tone:
              totalFailed > 0 || job.status === "completed_with_errors" || job.status === "failed"
                ? "error"
                : "success",
            message:
              totalFailed > 0
                ? `任务已完成，已生成 ${job.done} 行，跳过 ${totalSkipped} 行，失败 ${totalFailed} 行。`
                : `任务已完成，已生成 ${job.done} 行${totalSkipped ? `，跳过 ${totalSkipped} 行` : ""}。`,
          });
          setActiveBatchSync(null);
          return;
        }
      } catch (error) {
        if (!cancelled) {
          props.setNotice({
            tone: "error",
            message: error instanceof Error ? error.message : "同步任务进度失败。",
          });
        }
      }

      if (!cancelled) {
        timer = window.setTimeout(() => {
          void poll();
        }, 1200);
      }
    };

    void poll();

    return () => {
      cancelled = true;
      if (timer !== null) {
        window.clearTimeout(timer);
      }
    };
  }, [activeBatchSync, props.setNotice]);

  async function generateRows(
    targetRowIds: string[],
    options: {
      source: RenderSource;
      overwriteExisting: boolean;
      configOverrideRowId?: string | null;
    },
  ) {
    if (!props.project) {
      props.setNotice({ tone: "error", message: "请先选择一个项目。" });
      return;
    }
    if (!props.activeEpisodeId) {
      props.setNotice({ tone: "error", message: "请先在顶部导航栏选择一个分集。" });
      return;
    }
    if (!firstSpeaker) {
      props.setNotice({ tone: "error", message: "请先到角色管理页为当前项目创建角色。" });
      return;
    }

    const targetIdSet = new Set(targetRowIds);
    const targetRows = rows.filter((row) => targetIdSet.has(row.rowId));
    if (targetRows.length === 0) {
      props.setNotice({ tone: "error", message: "请先勾选至少一行文本。" });
      return;
    }

    const setGenerating =
      options.source === "config" ? setIsGeneratingFromConfig : setIsGeneratingSelection;
    setGenerating(true);
    setRows((current) =>
      current.map((row) =>
        targetIdSet.has(row.rowId)
          ? { ...row, lastStatus: "generating", lastError: null }
          : row,
      ),
    );

    let done = 0;
    let skipped = 0;
    let failed = 0;

    try {
      if (options.source === "batch") {
        const { queuedLines, skippedRowIds, failedRows } = buildBatchLines(targetRows, {
          overwriteExisting: options.overwriteExisting,
        });

        skipped = skippedRowIds.length;
        failed = failedRows.length;

        setRows((current) =>
          current.map((row) => {
            if (failedRows.some((item) => item.rowId === row.rowId)) {
              const failedRow = failedRows.find((item) => item.rowId === row.rowId);
              return {
                ...row,
                lastStatus: "failed",
                lastError: failedRow?.error ?? "生成失败。",
              };
            }
            if (skippedRowIds.includes(row.rowId)) {
              return {
                ...row,
                lastStatus: "skipped",
                lastError: null,
              };
            }
            if (queuedLines.some((item) => item.id === row.rowId)) {
              return {
                ...row,
                lastStatus: "generating",
                lastError: null,
              };
            }
            return row;
          }),
        );

        if (queuedLines.length === 0) {
          props.setNotice({
            tone: failed > 0 ? "error" : "success",
            message:
              failed > 0
                ? `没有可提交的任务，跳过 ${skipped} 行，失败 ${failed} 行。`
                : `没有可提交的任务，跳过 ${skipped} 行。`,
          });
          return;
        }

        const job = await requestJson<JobSummary>("/jobs/from-lines", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            project_id: props.project.id,
            episode_id: props.activeEpisodeId,
            title: `${props.project.name}-${props.activeEpisodeId}-web-batch`,
            lines: queuedLines,
            skip_existing: false,
            continue_on_error: true,
            force: options.overwriteExisting,
          }),
        });

        await props.onJobQueued(job.job_id);
        setActiveBatchSync({
          jobId: job.job_id,
          queuedRowIds: queuedLines.map((line) => line.id),
          preSkipped: skipped,
          preFailed: failed,
        });
        props.setNotice({
          tone: "info",
          message: `已提交 ${queuedLines.length} 行到任务队列${skipped ? `，跳过 ${skipped} 行` : ""}${failed ? `，失败 ${failed} 行` : ""}。`,
        });
        return;
      }

      for (const row of targetRows) {
        const selectedRender = selectedRenderForRow(row);

        if (!row.speaker || !row.text.trim()) {
          failed += 1;
          setRows((current) =>
            current.map((item) =>
              item.rowId === row.rowId
                ? { ...item, lastStatus: "failed", lastError: "角色和台词都不能为空。" }
                : item,
            ),
          );
          continue;
        }

        if (!options.overwriteExisting && selectedRender) {
          skipped += 1;
          setRows((current) =>
            current.map((item) =>
              item.rowId === row.rowId
                ? { ...item, lastStatus: "skipped", lastError: null }
                : item,
            ),
          );
          continue;
        }

        const override =
          options.configOverrideRowId === row.rowId
            ? overrideFromConfigForm(configForm)
            : row.override;

        try {
          const result = await requestJson<SingleResult>("/tts/single", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              project_id: props.project.id,
              episode_id: props.activeEpisodeId,
              speaker: row.speaker,
              text: row.text,
              output_name: buildOutputName(row, options.source, props.activeEpisodeId),
              override,
              force: true,
            }),
          });

          const render: RowRender = {
            renderId: makeId(),
            outputPath: result.output_path,
            durationMs: result.duration_ms,
            createdAt: new Date().toISOString(),
            source: options.source,
            usedOptions: result.used_options ?? {},
          };

          setRows((current) =>
            current.map((item) =>
              item.rowId === row.rowId
                ? {
                    ...item,
                    override,
                    renders: [...item.renders, render],
                    selectedRenderId: render.renderId,
                    lastStatus: "done",
                    lastError: null,
                  }
                : item,
            ),
          );
          props.onLatestResult(result);
          done += 1;
        } catch (error) {
          failed += 1;
          setRows((current) =>
            current.map((item) =>
              item.rowId === row.rowId
                ? {
                    ...item,
                    lastStatus: "failed",
                    lastError: error instanceof Error ? error.message : "生成失败。",
                  }
                : item,
            ),
          );
        }
      }

      props.setNotice({
        tone: failed > 0 ? "error" : "success",
        message:
          failed > 0
            ? `本次已生成 ${done} 行，跳过 ${skipped} 行，失败 ${failed} 行。`
            : `本次已生成 ${done} 行${skipped ? `，跳过 ${skipped} 行` : ""}。`,
      });
    } catch (error) {
      props.setNotice({
        tone: "error",
        message: error instanceof Error ? error.message : "提交或执行任务失败。",
      });
    } finally {
      setGenerating(false);
    }
  }

  const allSelected = rows.length > 0 && rows.every((row) => row.selected);

  const modal =
    activeConfigRow && typeof document !== "undefined"
      ? createPortal(
          <div className="fixed inset-0 z-[100] overflow-y-auto bg-slate-950/42 p-4 md:p-6">
            <div className="flex min-h-full items-center justify-center">
              <div className="max-h-[calc(100dvh-2rem)] w-full max-w-6xl overflow-hidden rounded-[34px] border border-white/70 bg-[#f7f3ec] shadow-[0_36px_80px_-36px_rgba(15,23,42,0.75)] md:max-h-[calc(100dvh-3rem)]">
                <div className="flex items-start justify-between gap-4 border-b border-white/60 px-5 py-5 md:px-6">
                  <div>
                    <div className="eyebrow">行级配置</div>
                    <h3 className="mt-3 font-display text-2xl font-semibold text-ink">
                      {activeConfigRow.speaker || "未选择角色"} 的详细参数
                    </h3>
                    <p className="mt-2 max-w-3xl text-sm leading-7 text-slate-600">
                      这里的配置只作用于当前行。你可以直接单行生成、试听多个版本，并选择最终采用的配音。
                    </p>
                  </div>
                  <button
                    className="shrink-0 rounded-full border border-white/70 bg-white/70 p-2 text-slate-500 transition hover:text-slate-800"
                    onClick={() => setActiveConfigRowId(null)}
                    type="button"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>

                <div className="grid max-h-[calc(100dvh-8rem)] gap-5 overflow-y-auto px-5 py-5 md:max-h-[calc(100dvh-9rem)] md:grid-cols-[minmax(0,1.15fr),360px] md:px-6">
                  <div className="space-y-5">
                    <div className="rounded-[28px] border border-white/70 bg-white/72 p-4">
                      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                        <FieldLabel label="采样温度">
                          <input className="field-shell w-full" onChange={(event) => setConfigForm((current) => ({ ...current, temperature: event.target.value }))} type="number" value={configForm.temperature} />
                        </FieldLabel>
                        <FieldLabel label="Top P">
                          <input className="field-shell w-full" onChange={(event) => setConfigForm((current) => ({ ...current, topP: event.target.value }))} type="number" value={configForm.topP} />
                        </FieldLabel>
                        <FieldLabel label="Top K">
                          <input className="field-shell w-full" onChange={(event) => setConfigForm((current) => ({ ...current, topK: event.target.value }))} type="number" value={configForm.topK} />
                        </FieldLabel>
                        <FieldLabel label="句间静音">
                          <input className="field-shell w-full" onChange={(event) => setConfigForm((current) => ({ ...current, intervalSilence: event.target.value }))} type="number" value={configForm.intervalSilence} />
                        </FieldLabel>
                        <FieldLabel label="搜索束数">
                          <input className="field-shell w-full" onChange={(event) => setConfigForm((current) => ({ ...current, numBeams: event.target.value }))} type="number" value={configForm.numBeams} />
                        </FieldLabel>
                        <FieldLabel label="重复惩罚">
                          <input className="field-shell w-full" onChange={(event) => setConfigForm((current) => ({ ...current, repetitionPenalty: event.target.value }))} type="number" value={configForm.repetitionPenalty} />
                        </FieldLabel>
                        <FieldLabel label="长度惩罚">
                          <input className="field-shell w-full" onChange={(event) => setConfigForm((current) => ({ ...current, lengthPenalty: event.target.value }))} type="number" value={configForm.lengthPenalty} />
                        </FieldLabel>
                        <FieldLabel label="最大 Mel Token">
                          <input className="field-shell w-full" onChange={(event) => setConfigForm((current) => ({ ...current, maxMelTokens: event.target.value }))} type="number" value={configForm.maxMelTokens} />
                        </FieldLabel>
                        <FieldLabel label="每段最大文本 Token">
                          <input className="field-shell w-full" onChange={(event) => setConfigForm((current) => ({ ...current, maxTextTokensPerSegment: event.target.value }))} type="number" value={configForm.maxTextTokensPerSegment} />
                        </FieldLabel>
                      </div>

                      <div className="mt-4 grid gap-4 md:grid-cols-2">
                        <FieldLabel label="情绪文本">
                          <textarea className="field-shell min-h-[112px] w-full resize-y" onChange={(event) => setConfigForm((current) => ({ ...current, emoText: event.target.value }))} value={configForm.emoText} />
                        </FieldLabel>
                        <FieldLabel label="切分策略">
                          <textarea className="field-shell min-h-[112px] w-full resize-y" onChange={(event) => setConfigForm((current) => ({ ...current, textSplitMethod: event.target.value }))} value={configForm.textSplitMethod} />
                        </FieldLabel>
                      </div>

                      <div className="mt-4">
                        <FieldLabel label="情绪向量数组">
                          <textarea className="field-shell min-h-[112px] w-full resize-y" onChange={(event) => setConfigForm((current) => ({ ...current, emoVector: event.target.value }))} placeholder="[0.1, 0.2, 0.3]" value={configForm.emoVector} />
                        </FieldLabel>
                      </div>

                      <div className="mt-4 grid gap-3 md:grid-cols-2">
                        <ToggleTile checked={configForm.useEmoText} label="启用情绪文本" onChange={(checked) => setConfigForm((current) => ({ ...current, useEmoText: checked }))} />
                        <ToggleTile checked={configForm.useRandom} label="启用随机采样" onChange={(checked) => setConfigForm((current) => ({ ...current, useRandom: checked }))} />
                      </div>

                      <div className="mt-5 flex flex-wrap gap-3">
                        <button className="action-button action-button-secondary" onClick={saveConfigToRow} type="button">
                          <Check className="h-4 w-4" />
                          保存配置
                        </button>
                        <button
                          className="action-button action-button-primary"
                          disabled={isGeneratingFromConfig}
                          onClick={() =>
                            void generateRows([activeConfigRow.rowId], {
                              source: "config",
                              overwriteExisting: true,
                              configOverrideRowId: activeConfigRow.rowId,
                            })
                          }
                          type="button"
                        >
                          {isGeneratingFromConfig ? (
                            <LoaderCircle className="h-4 w-4 animate-spin" />
                          ) : (
                            <WandSparkles className="h-4 w-4" />
                          )}
                          生成并试听
                        </button>
                      </div>
                    </div>

                    <div className="rounded-[28px] border border-white/70 bg-white/72 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <div className="eyebrow">版本记录</div>
                          <h4 className="mt-3 font-display text-xl font-semibold text-ink">当前行的历史配音</h4>
                        </div>
                        <span className="rounded-full border border-slate-200 bg-slate-100/80 px-3 py-1 text-xs font-semibold text-slate-600">
                          共 {activeConfigRow.renders.length} 个版本
                        </span>
                      </div>
                      {activeRenderList.length === 0 ? (
                        <div className="mt-4">
                          <EmptyState title="还没有版本" description="先点击“生成并试听”，这里就会出现可以切换和试听的配音版本。" />
                        </div>
                      ) : (
                        <div className="mt-4 space-y-3">
                          {activeRenderList.map((render, index) => {
                            const isSelected = render.renderId === activeConfigRow.selectedRenderId;
                            const optionCount = Object.keys(render.usedOptions || {}).length;
                            return (
                              <div
                                key={render.renderId}
                                className={`rounded-[24px] border px-4 py-4 ${
                                  isSelected
                                    ? "border-slate-900 bg-slate-900 text-white"
                                    : "border-white/70 bg-slate-100/55 text-slate-700"
                                }`}
                              >
                                <div className="flex flex-wrap items-center justify-between gap-3">
                                  <div>
                                    <div className="font-semibold">版本 {activeRenderList.length - index}</div>
                                    <div className={`mt-1 text-xs ${isSelected ? "text-white/70" : "text-slate-500"}`}>
                                      {formatClock(render.createdAt)} · {formatDuration(render.durationMs)} · {render.source === "config" ? "配置窗口" : "表格批量"}
                                    </div>
                                  </div>
                                  <button
                                    className={`rounded-full border px-3 py-1 text-xs font-semibold transition ${
                                      isSelected
                                        ? "border-white/25 bg-white/10 text-white"
                                        : "border-slate-200 bg-white/75 text-slate-700 hover:bg-white"
                                    }`}
                                    onClick={() => setSelectedRender(activeConfigRow.rowId, render.renderId)}
                                    type="button"
                                  >
                                    {isSelected ? "当前配音" : "设为当前配音"}
                                  </button>
                                </div>
                                <div className={`mt-3 text-xs leading-6 ${isSelected ? "text-white/70" : "text-slate-500"}`}>
                                  使用参数 {optionCount} 项
                                </div>
                                <audio className="mt-3 w-full" controls src={audioPreviewUrl(render.outputPath)} />
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="space-y-5">
                    <AudioCard
                      title="当前选定配音"
                      description={
                        activeSelectedRender
                          ? `${activeConfigRow.speaker} · ${formatDuration(activeSelectedRender.durationMs)}`
                          : "生成或选择一个版本后，这里会显示当前行正在使用的配音。"
                      }
                      path={activeSelectedRender?.outputPath}
                      secondary={activeConfigRow.text || "请先在表格里输入台词内容。"}
                    />

                    <div className="rounded-[28px] border border-white/70 bg-white/72 p-4 text-sm text-slate-600">
                      <div className="eyebrow">当前台词</div>
                      <div className="mt-3 rounded-[22px] border border-slate-200 bg-slate-100/70 px-4 py-4 leading-7 text-slate-700">
                        {activeConfigRow.text || "请先在表格里输入台词内容。"}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>,
          document.body,
        )
      : null;

  if (!props.project) {
    return (
      <div className="glass-card p-5 md:p-6">
        <EmptyState title="请先选择项目" description="先到项目配置页创建或选择一个项目，然后再按分集维护文本配音列表。" />
      </div>
    );
  }

  if (episodeOptions.length === 0) {
    return (
      <div className="glass-card p-5 md:p-6">
        <EmptyState title="当前项目还没有分集" description="先到项目配置页为当前项目添加分集，文本配音页才会按分集展示台词列表。" />
      </div>
    );
  }

  if (!props.activeEpisodeId) {
    return (
      <div className="glass-card p-5 md:p-6">
        <EmptyState title="请先选择分集" description="从顶部导航栏里选择当前分集后，这里会加载对应的文本配音工作台。" />
      </div>
    );
  }

  if (isRowsLoading) {
    return (
      <div className="glass-card p-5 md:p-6">
        <EmptyState title="正在加载表格" description="正在从项目分集的持久化数据中读取文本配音列表，请稍候。" />
      </div>
    );
  }

  return (
    <>
      <div>
        <section className="glass-card p-5 md:p-6">
          <div className="flex flex-col gap-4 border-b border-white/55 pb-5 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <div className="eyebrow">文本配音工作台</div>
              <h2 className="mt-3 font-display text-2xl font-semibold text-ink">表格工作台</h2>
              <p className="mt-2 max-w-3xl text-sm leading-7 text-slate-600">
                当前页面的台词表会按“项目 + 分集”独立保存。分集选择放在顶部导航栏里，这里只保留台词编排、试听和生成操作。
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <button className="action-button action-button-secondary" onClick={addRow} type="button">
                <Plus className="h-4 w-4" />
                新增一行
              </button>              <button
                className="action-button action-button-ghost"
                disabled={isExporting || exportableRowCount === 0}
                onClick={() => void exportCurrentEpisode()}
                type="button"
              >
                {isExporting ? (
                  <LoaderCircle className="h-4 w-4 animate-spin" />
                ) : (
                  <Download className="h-4 w-4" />
                )}
                一键导出
              </button>
              <button
                className="action-button action-button-ghost"
                disabled={selectedRows.length === 0}
                onClick={removeSelectedRows}
                type="button"
              >
                <Trash2 className="h-4 w-4" />
                删除选中
              </button>
              <button
                className="action-button action-button-primary"
                disabled={isGeneratingSelection || activeBatchSync !== null || selectedRows.length === 0}
                onClick={() =>
                  void generateRows(selectedRows.map((row) => row.rowId), {
                    source: "batch",
                    overwriteExisting: existingBehavior === "overwrite",
                  })
                }
                type="button"
              >
                {isGeneratingSelection ? (
                  <LoaderCircle className="h-4 w-4 animate-spin" />
                ) : (
                  <WandSparkles className="h-4 w-4" />
                )}
                生成选中行
              </button>
            </div>
          </div>

          <div className="mt-5 rounded-[30px] border border-white/70 bg-slate-100/55 p-4 shadow-inner">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <div className="text-sm font-semibold text-slate-700">已有配音处理策略</div>
                <div className="mt-2 text-sm text-slate-500">
                  如果某一行已经选定过配音，可以选择直接跳过，或者生成新版本并把最新结果设为当前配音。
                </div>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <button
                  className={`rounded-[22px] border px-4 py-3 text-left text-sm transition-all ${
                    existingBehavior === "skip"
                      ? "border-slate-900 bg-slate-900 text-white"
                      : "border-white/70 bg-white/72 text-slate-700"
                  }`}
                  onClick={() => setExistingBehavior("skip")}
                  type="button"
                >
                  <div className="font-semibold">已有配音时跳过</div>
                  <div className={`mt-1 text-xs ${existingBehavior === "skip" ? "text-white/70" : "text-slate-500"}`}>
                    适合只补齐还没生成的台词。
                  </div>
                </button>
                <button
                  className={`rounded-[22px] border px-4 py-3 text-left text-sm transition-all ${
                    existingBehavior === "overwrite"
                      ? "border-slate-900 bg-slate-900 text-white"
                      : "border-white/70 bg-white/72 text-slate-700"
                  }`}
                  onClick={() => setExistingBehavior("overwrite")}
                  type="button"
                >
                  <div className="font-semibold">已有配音时生成新版本</div>
                  <div className={`mt-1 text-xs ${existingBehavior === "overwrite" ? "text-white/70" : "text-slate-500"}`}>
                    新生成的结果会自动设为当前配音。
                  </div>
                </button>
              </div>
            </div>
          </div>

          {speakerNames.length === 0 ? (
            <div className="mt-5">
              <EmptyState title="当前项目还没有角色" description="先到角色管理页为当前项目创建角色，文本表格才能开始指定说话人。" />
            </div>
          ) : (
            <div className="mt-5 overflow-hidden rounded-[30px] border border-white/70 bg-white/70">
              <div className="overflow-x-auto">
                <table className="min-w-full text-left text-sm text-slate-700">
                  <thead className="bg-slate-100/80 text-xs uppercase tracking-[0.18em] text-slate-500">
                    <tr>
                      <th className="px-4 py-4">
                        <input checked={allSelected} className="h-4 w-4 accent-slate-900" onChange={(event) => toggleSelectAll(event.target.checked)} type="checkbox" />
                      </th>
                      <th className="px-4 py-4">行</th>
                      <th className="px-4 py-4">角色</th>
                      <th className="px-4 py-4">台词</th>
                      <th className="px-4 py-4">状态</th>
                      <th className="px-4 py-4">当前配音</th>
                      <th className="px-4 py-4">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row, index) => {
                      const selectedRender = selectedRenderForRow(row);
                      return (
                        <tr key={row.rowId} className="border-t border-white/70 align-top transition-colors hover:bg-slate-50/70">
                          <td className="px-4 py-4">
                            <input checked={row.selected} className="h-4 w-4 accent-slate-900" onChange={(event) => updateRow(row.rowId, { selected: event.target.checked })} type="checkbox" />
                          </td>
                          <td className="px-4 py-4 font-semibold text-slate-500">{index + 1}</td>
                          <td className="min-w-[180px] px-4 py-4">
                            <select className="field-shell w-full" onChange={(event) => updateRow(row.rowId, { speaker: event.target.value })} value={row.speaker}>
                              {speakerNames.map((speakerName) => (
                                <option key={speakerName} value={speakerName}>
                                  {speakerName}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td className="min-w-[360px] px-4 py-4">
                            <textarea className="field-shell min-h-[110px] w-full resize-y" onChange={(event) => updateRow(row.rowId, { text: event.target.value })} placeholder="直接填写要生成的台词。" value={row.text} />
                            <div className="mt-2 text-xs text-slate-400">当前详细参数 {Object.keys(row.override || {}).length} 项</div>
                          </td>
                          <td className="min-w-[180px] px-4 py-4">
                            <div className="flex flex-col gap-3">
                              <span
                                className={`${statusClasses(row.lastStatus)} w-fit normal-case tracking-[0.04em]`}
                              >
                                <RowStatusIcon status={row.lastStatus} />
                                {displayRowStatus(row.lastStatus)}
                              </span>
                              {row.lastError ? (
                                <div className="rounded-[18px] border border-rose-100 bg-rose-50/90 px-3 py-2 text-xs leading-6 text-rose-700">
                                  {row.lastError}
                                </div>
                              ) : (
                                <div className="text-xs leading-6 text-slate-500">已保存版本 {row.renders.length} 个</div>
                              )}
                            </div>
                          </td>
                          <td className="min-w-[280px] px-4 py-4">
                            {selectedRender ? (
                              <div className="space-y-2">
                                <audio className="w-full" controls src={audioPreviewUrl(selectedRender.outputPath)} />
                                <div className="text-xs leading-6 text-slate-500">
                                  <div>{formatDuration(selectedRender.durationMs)}</div>
                                  <div>{formatClock(selectedRender.createdAt)}</div>
                                  <div>来源：{selectedRender.source === "config" ? "配置窗口" : "表格批量"}</div>
                                </div>
                              </div>
                            ) : (
                              <div className="rounded-[18px] border border-dashed border-slate-200 bg-white/70 px-3 py-4 text-xs leading-6 text-slate-400">
                                这一行还没有可试听的配音。
                              </div>
                            )}
                          </td>
                          <td className="min-w-[230px] px-4 py-4">
                            <div className="flex flex-wrap gap-2">
                              <button className="action-button action-button-secondary" onClick={() => openConfig(row)} type="button">
                                <Settings2 className="h-4 w-4" />
                                配置
                              </button>
                              <button className="action-button action-button-ghost" onClick={() => duplicateRow(row)} type="button">
                                <Copy className="h-4 w-4" />
                                复制
                              </button>
                              <button className="action-button action-button-ghost" disabled={rows.length === 1} onClick={() => removeRow(row.rowId)} type="button">
                                <Trash2 className="h-4 w-4" />
                                删除
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </section>
      </div>
      {modal}
    </>
  );
}
