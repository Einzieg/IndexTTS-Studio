import { AudioWaveform, FileAudio2, Layers3, LoaderCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { AudioCard, EmptyState } from "../components";
import { displayStatus, formatClock, formatDuration, formatTimeline, statusClasses } from "../lib";
import type { JobLine, JobSummary, SingleResult } from "../types";


export function JobsPage(props: {
  jobs: JobSummary[];
  selectedJobId: string | null;
  onSelectJob: (jobId: string) => void;
  jobLines: JobLine[];
  isJobLinesLoading: boolean;
  singleResult: SingleResult | null;
}) {
  const [selectedLineId, setSelectedLineId] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedLineId && props.jobLines[0]) {
      setSelectedLineId(props.jobLines[0].line_id);
      return;
    }
    if (
      selectedLineId &&
      !props.jobLines.some((line) => line.line_id === selectedLineId)
    ) {
      setSelectedLineId(props.jobLines[0]?.line_id ?? null);
    }
  }, [props.jobLines, selectedLineId]);

  const selectedJobLine = useMemo(
    () => props.jobLines.find((line) => line.line_id === selectedLineId) ?? null,
    [props.jobLines, selectedLineId],
  );

  return (
    <div className="grid gap-5 xl:grid-cols-[320px,minmax(0,1fr),360px]">
      <aside className="glass-card p-5">
        <div className="eyebrow">异步队列</div>
        <div className="mt-4 flex items-center justify-between">
          <h2 className="font-display text-2xl font-semibold text-ink">任务列表</h2>
          <Layers3 className="h-5 w-5 text-slate-500" />
        </div>
        <p className="mt-2 text-sm leading-7 text-slate-600">
          页面脚本和其他批量任务都会汇总在这里，方便你持续轮询进度。
        </p>

        <div className="mt-4 space-y-3">
          {props.jobs.length === 0 ? (
            <EmptyState title="还没有任务" description="去文本配音页提交一次页面脚本任务，这里就会开始显示处理状态。" />
          ) : (
            props.jobs.map((job) => {
              const active = job.job_id === props.selectedJobId;
              return (
                <button
                  key={job.job_id}
                  className={`w-full rounded-[24px] border px-4 py-4 text-left transition-all duration-200 active:scale-[0.98] ${
                    active
                      ? "border-slate-900 bg-slate-900 text-white shadow-[0_20px_40px_-26px_rgba(15,23,42,0.8)]"
                      : "border-white/70 bg-white/70 text-slate-700 hover:bg-white"
                  }`}
                  onClick={() => props.onSelectJob(job.job_id)}
                  type="button"
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-semibold">任务 {job.job_id.slice(0, 8)}</span>
                    <span className={statusClasses(job.status)}>{displayStatus(job.status)}</span>
                  </div>
                  <div className={`mt-3 text-xs ${active ? "text-white/75" : "text-slate-500"}`}>
                    {job.script_path}
                  </div>
                  <div className="mt-4 grid grid-cols-4 gap-2 text-center">
                    <SummaryPill inverse={active} label="已生成" value={job.done} />
                    <SummaryPill inverse={active} label="跳过" value={job.skipped} />
                    <SummaryPill inverse={active} label="失败" value={job.failed} />
                    <SummaryPill inverse={active} label="总计" value={job.total} />
                  </div>
                  <div className={`mt-4 text-[11px] uppercase tracking-[0.22em] ${active ? "text-white/60" : "text-slate-400"}`}>
                    {formatClock(job.created_at)}
                  </div>
                </button>
              );
            })
          )}
        </div>
      </aside>

      <section className="glass-card p-5 md:p-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="eyebrow">逐句结果</div>
            <h2 className="mt-3 font-display text-2xl font-semibold text-ink">当前任务明细</h2>
          </div>
          {props.isJobLinesLoading ? (
            <LoaderCircle className="h-5 w-5 animate-spin text-slate-500" />
          ) : (
            <FileAudio2 className="h-5 w-5 text-slate-500" />
          )}
        </div>
        <p className="mt-2 text-sm leading-7 text-slate-600">
          点击某个任务后，这里会展示逐句输出、错误信息和音频时长。
        </p>

        <div className="scroll-panel mt-5 max-h-[780px] space-y-3 overflow-auto pr-1">
          {props.jobLines.length === 0 ? (
            <EmptyState title="还没有逐句结果" description="先从左侧选择一个任务，就能查看每一句的生成状态。" />
          ) : (
            props.jobLines.map((line) => {
              const active = line.line_id === selectedLineId;
              return (
                <button
                  key={line.line_id}
                  className={`w-full rounded-[24px] border px-4 py-4 text-left transition-all duration-200 active:scale-[0.98] ${
                    active
                      ? "border-slate-900 bg-slate-900 text-white shadow-[0_20px_40px_-26px_rgba(15,23,42,0.8)]"
                      : "border-white/70 bg-white/70 text-slate-700 hover:bg-white"
                  }`}
                  onClick={() => setSelectedLineId(line.line_id)}
                  type="button"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="font-semibold">
                        第 {line.line_id} 句 / {line.speaker}
                      </div>
                      <p className={`mt-2 text-sm leading-7 ${active ? "text-white/75" : "text-slate-500"}`}>
                        {line.text}
                      </p>
                    </div>
                    <span className={statusClasses(line.status)}>{displayStatus(line.status)}</span>
                  </div>
                  <div className={`mt-3 flex flex-wrap gap-2 text-[11px] ${active ? "text-white/65" : "text-slate-400"}`}>
                    <span>{formatDuration(line.duration_ms)}</span>
                    <span>{formatTimeline(line.start_ms)}</span>
                    {Object.keys(line.override || {}).length > 0 ? (
                      <span>{Object.keys(line.override).length} 项覆盖</span>
                    ) : null}
                  </div>
                  {line.error ? (
                    <div className="mt-3 rounded-[18px] border border-rose-100 bg-rose-50/90 px-3 py-2 text-xs text-rose-700">
                      {line.error}
                    </div>
                  ) : null}
                </button>
              );
            })
          )}
        </div>
      </section>

      <aside className="space-y-5">
        <div className="glass-card p-5">
          <div className="eyebrow">输出试听</div>
          <div className="mt-4 flex items-center justify-between">
            <h2 className="font-display text-2xl font-semibold text-ink">播放区</h2>
            <AudioWaveform className="h-5 w-5 text-slate-500" />
          </div>
          <div className="mt-4 space-y-4">
            <AudioCard
              description={
                selectedJobLine
                  ? `${selectedJobLine.speaker}，${formatDuration(selectedJobLine.duration_ms)}`
                  : "选中一条任务句子后，可以在这里直接试听输出。"
              }
              path={selectedJobLine?.output_path}
              secondary={selectedJobLine?.text}
              title="任务句子试听"
            />
            <AudioCard
              description={
                props.singleResult
                  ? `${props.singleResult.speaker}，${formatDuration(props.singleResult.duration_ms)}`
                  : "最近一次单句试听结果会显示在这里。"
              }
              path={props.singleResult?.output_path}
              secondary={props.singleResult?.text}
              title="单句试听输出"
            />
          </div>
        </div>
      </aside>
    </div>
  );
}


function SummaryPill(props: { label: string; value: number; inverse?: boolean }) {
  return (
    <div
      className={`rounded-[18px] px-3 py-2 text-xs ${
        props.inverse ? "bg-white/10 text-white/85" : "bg-slate-100/80 text-slate-600"
      }`}
    >
      <div className="font-semibold">{props.value}</div>
      <div className="mt-1 uppercase tracking-[0.18em]">{props.label}</div>
    </div>
  );
}
