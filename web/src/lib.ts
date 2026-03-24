import type { ApiEnvelope, GenerationOptions, Tone } from "./types";

export const AUTH_REQUIRED_EVENT = "indextts-studio:auth-required";

export class UnauthorizedError extends Error {}

export async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: "same-origin",
    ...init,
  });

  let payload: ApiEnvelope<T> | null = null;
  try {
    payload = (await response.json()) as ApiEnvelope<T>;
  } catch {
    payload = null;
  }

  if (response.status === 401) {
    window.dispatchEvent(new CustomEvent(AUTH_REQUIRED_EVENT));
    throw new UnauthorizedError(payload?.message || "登录已失效，请重新登录。");
  }

  if (!response.ok || !payload?.success) {
    throw new Error(payload?.message || `请求失败：${path}`);
  }
  return payload.data;
}

export function audioPreviewUrl(path?: string | null): string | undefined {
  if (!path) {
    return undefined;
  }
  return `/files/audio?path=${encodeURIComponent(path)}`;
}

export function formatDuration(value: number | null | undefined): string {
  if (!value) {
    return "0 毫秒";
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(2)} 秒`;
  }
  return `${value} 毫秒`;
}

export function formatClock(value?: string | null): string {
  if (!value) {
    return "待开始";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function formatTimeline(value?: number | null): string {
  if (value === null || value === undefined) {
    return "无";
  }
  const hours = Math.floor(value / 3_600_000);
  const minutes = Math.floor((value % 3_600_000) / 60_000);
  const seconds = Math.floor((value % 60_000) / 1000);
  const milliseconds = value % 1000;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}.${String(milliseconds).padStart(3, "0")}`;
}

export function displayStatus(status: string): string {
  const normalized = status.toLowerCase();
  if (normalized === "ok") {
    return "正常";
  }
  if (normalized === "offline") {
    return "离线";
  }
  if (normalized === "completed") {
    return "已完成";
  }
  if (normalized === "completed_with_errors") {
    return "完成但有错误";
  }
  if (normalized === "done") {
    return "已生成";
  }
  if (normalized === "running") {
    return "进行中";
  }
  if (normalized === "queued") {
    return "排队中";
  }
  if (normalized === "pending") {
    return "待处理";
  }
  if (normalized === "skipped") {
    return "已跳过";
  }
  if (normalized === "failed") {
    return "失败";
  }
  return status;
}

export function statusClasses(status: string): string {
  const normalized = status.toLowerCase();
  if (normalized === "ok" || normalized === "completed" || normalized === "done") {
    return "status-chip bg-emerald-50/90 text-emerald-700 border-emerald-100";
  }
  if (normalized === "completed_with_errors" || normalized === "queued" || normalized === "pending") {
    return "status-chip bg-amber-50/90 text-amber-700 border-amber-100";
  }
  if (normalized === "running" || normalized === "generating") {
    return "status-chip bg-sky-50/90 text-sky-700 border-sky-100";
  }
  if (normalized === "skipped" || normalized === "idle") {
    return "status-chip bg-slate-100/90 text-slate-600 border-slate-200/90";
  }
  if (normalized === "offline" || normalized === "failed") {
    return "status-chip bg-rose-50/90 text-rose-700 border-rose-100";
  }
  return "status-chip bg-rose-50/90 text-rose-700 border-rose-100";
}

export function noticeClasses(tone: Tone): string {
  if (tone === "success") {
    return "border-emerald-100 bg-emerald-50/85 text-emerald-700";
  }
  if (tone === "error") {
    return "border-rose-100 bg-rose-50/90 text-rose-700";
  }
  return "border-slate-200/80 bg-white/70 text-slate-600";
}

export function stringifyOptionList(value?: number[]): string {
  if (!value || value.length === 0) {
    return "";
  }
  return JSON.stringify(value);
}

export function parseNumberInput(value: string): number | undefined {
  const normalized = value.trim();
  if (!normalized) {
    return undefined;
  }
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : undefined;
}

export function buildOverride(fields: {
  temperature?: string;
  topP?: string;
  topK?: string;
  intervalSilence?: string;
  numBeams?: string;
  repetitionPenalty?: string;
  lengthPenalty?: string;
  emoText?: string;
  textSplitMethod?: string;
  emoVector?: string;
  useEmoText?: boolean;
  useRandom?: boolean;
}): GenerationOptions {
  const override: GenerationOptions = {};

  if (fields.temperature?.trim()) {
    override.temperature = parseNumberInput(fields.temperature);
  }
  if (fields.topP?.trim()) {
    override.top_p = parseNumberInput(fields.topP);
  }
  if (fields.topK?.trim()) {
    const parsed = parseNumberInput(fields.topK);
    if (parsed !== undefined) {
      override.top_k = parsed;
    }
  }
  if (fields.intervalSilence?.trim()) {
    override.interval_silence = parseNumberInput(fields.intervalSilence);
  }
  if (fields.numBeams?.trim()) {
    const parsed = parseNumberInput(fields.numBeams);
    if (parsed !== undefined) {
      override.num_beams = parsed;
    }
  }
  if (fields.repetitionPenalty?.trim()) {
    override.repetition_penalty = parseNumberInput(fields.repetitionPenalty);
  }
  if (fields.lengthPenalty?.trim()) {
    override.length_penalty = parseNumberInput(fields.lengthPenalty);
  }
  if (fields.emoText?.trim()) {
    override.emo_text = fields.emoText.trim();
  }
  if (fields.textSplitMethod?.trim()) {
    override.text_split_method = fields.textSplitMethod.trim();
  }
  if (fields.emoVector?.trim()) {
    try {
      const decoded = JSON.parse(fields.emoVector);
      if (Array.isArray(decoded)) {
        override.emo_vector = decoded.map((item) => Number(item));
      }
    } catch {
      // Let the server do strict validation; the UI only best-effort parses.
    }
  }
  if (fields.useEmoText !== undefined) {
    override.use_emo_text = fields.useEmoText;
  }
  if (fields.useRandom !== undefined) {
    override.use_random = fields.useRandom;
  }

  return Object.fromEntries(
    Object.entries(override).filter(([, value]) => value !== undefined && value !== "")
  ) as GenerationOptions;
}
