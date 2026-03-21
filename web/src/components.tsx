import type { ReactNode } from "react";

import { AudioWaveform } from "lucide-react";

import { audioPreviewUrl } from "./lib";


export function MetricChip(props: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="rounded-full border border-white/70 bg-white/72 px-4 py-2 text-sm text-slate-600">
      <div className="flex items-center gap-2">
        <span className="text-slate-500">{props.icon}</span>
        <span className="font-semibold text-slate-700">{props.value}</span>
        <span className="text-slate-500">{props.label}</span>
      </div>
    </div>
  );
}


export function ToggleTile(props: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <label
      className={`flex min-h-[62px] cursor-pointer items-center justify-between rounded-[24px] border px-4 py-4 transition-all duration-200 ${
        props.checked
          ? "border-slate-900 bg-slate-900 text-white"
          : "border-white/70 bg-white/72 text-slate-700"
      } ${props.disabled ? "cursor-not-allowed opacity-50" : ""}`}
    >
      <span className="text-sm font-semibold tracking-[0.02em]">{props.label}</span>
      <input
        checked={props.checked}
        className="h-4 w-4 accent-slate-900"
        disabled={props.disabled}
        onChange={(event) => props.onChange(event.target.checked)}
        type="checkbox"
      />
    </label>
  );
}


export function AudioCard(props: {
  title: string;
  description: string;
  path?: string | null;
  secondary?: string;
}) {
  return (
    <div className="rounded-[28px] border border-white/70 bg-slate-100/55 p-4 shadow-inner">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-700">{props.title}</div>
          <div className="mt-1 text-sm text-slate-500">{props.description}</div>
        </div>
        <AudioWaveform className="mt-1 h-4 w-4 text-slate-400" />
      </div>
      {props.secondary ? (
        <div className="mt-3 text-xs leading-6 text-slate-500">{props.secondary}</div>
      ) : null}
      <div className="mt-4">
        {props.path ? (
          <>
            <audio controls src={audioPreviewUrl(props.path)} />
            <div className="mt-2 break-all text-xs text-slate-400">{props.path}</div>
          </>
        ) : (
          <div className="rounded-[20px] border border-dashed border-slate-200 bg-white/60 px-3 py-4 text-sm text-slate-400">
            还没有可播放的音频。
          </div>
        )}
      </div>
    </div>
  );
}


export function EmptyState(props: { title: string; description: string }) {
  return (
    <div className="rounded-[24px] border border-dashed border-slate-200/90 bg-white/50 px-4 py-6 text-sm text-slate-500">
      <div className="font-semibold text-slate-600">{props.title}</div>
      <div className="mt-2 leading-7">{props.description}</div>
    </div>
  );
}


export function FieldLabel(props: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-2 block text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">
        {props.label}
      </span>
      {props.children}
    </label>
  );
}
