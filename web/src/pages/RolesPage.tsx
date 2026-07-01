import { BadgeCheck, Copy, LoaderCircle, Plus, Save, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { AudioCard, EmptyState, FieldLabel, ToggleTile } from "../components";
import { requestJson, stringifyOptionList } from "../lib";
import type { Notice, ProjectConfig, SpeakerCopyPayload, SpeakerProfile, SpeakerProfilePayload } from "../types";

type SpeakerFormState = {
  name: string;
  temperature: string;
  topP: string;
  topK: string;
  intervalSilence: string;
  numBeams: string;
  repetitionPenalty: string;
  lengthPenalty: string;
  emoText: string;
  textSplitMethod: string;
  emoVector: string;
  useEmoText: boolean;
  useRandom: boolean;
};

function createBlankForm(): SpeakerFormState {
  return {
    name: "",
    temperature: "",
    topP: "",
    topK: "",
    intervalSilence: "",
    numBeams: "",
    repetitionPenalty: "",
    lengthPenalty: "",
    emoText: "",
    textSplitMethod: "",
    emoVector: "",
    useEmoText: false,
    useRandom: true,
  };
}

function buildForm(profile?: SpeakerProfile): SpeakerFormState {
  if (!profile) {
    return createBlankForm();
  }
  return {
    name: profile.name,
    temperature: profile.options.temperature?.toString() ?? "",
    topP: profile.options.top_p?.toString() ?? "",
    topK: profile.options.top_k?.toString() ?? "",
    intervalSilence: profile.options.interval_silence?.toString() ?? "",
    numBeams: profile.options.num_beams?.toString() ?? "",
    repetitionPenalty: profile.options.repetition_penalty?.toString() ?? "",
    lengthPenalty: profile.options.length_penalty?.toString() ?? "",
    emoText: profile.options.emo_text ?? "",
    textSplitMethod: profile.options.text_split_method ?? "",
    emoVector: stringifyOptionList(profile.options.emo_vector),
    useEmoText: profile.options.use_emo_text ?? false,
    useRandom: profile.options.use_random ?? true,
  };
}

export function RolesPage(props: {
  project: ProjectConfig | null;
  projects: ProjectConfig[];
  speakers: SpeakerProfile[];
  setNotice: (notice: Notice) => void;
  onRefresh: () => Promise<void>;
}) {
  const [activeSpeakerName, setActiveSpeakerName] = useState<string>("");
  const [isCreating, setIsCreating] = useState(false);
  const [form, setForm] = useState<SpeakerFormState>(createBlankForm);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [sourceProjectId, setSourceProjectId] = useState("");
  const [sourceSpeakerName, setSourceSpeakerName] = useState("__all__");
  const [sourceSpeakers, setSourceSpeakers] = useState<SpeakerProfile[]>([]);
  const [overwriteExisting, setOverwriteExisting] = useState(false);
  const [isSourceSpeakersLoading, setIsSourceSpeakersLoading] = useState(false);
  const [isCopyingSpeaker, setIsCopyingSpeaker] = useState(false);

  const sourceProjects = useMemo(
    () => props.projects.filter((project) => project.id !== props.project?.id),
    [props.project?.id, props.projects],
  );

  const activeSpeaker = useMemo(
    () =>
      isCreating
        ? undefined
        : props.speakers.find((speaker) => speaker.name === activeSpeakerName),
    [activeSpeakerName, isCreating, props.speakers],
  );

  useEffect(() => {
    setIsCreating(false);
    setActiveSpeakerName("");
    setSelectedFile(null);
  }, [props.project?.id]);

  useEffect(() => {
    const nextSourceProjectId = sourceProjects.find((project) => project.id === sourceProjectId)
      ?.id ?? sourceProjects[0]?.id ?? "";
    if (nextSourceProjectId !== sourceProjectId) {
      setSourceProjectId(nextSourceProjectId);
    }
  }, [sourceProjectId, sourceProjects]);

  useEffect(() => {
    let canceled = false;
    if (!sourceProjectId) {
      setSourceSpeakers([]);
      setSourceSpeakerName("__all__");
      return () => {
        canceled = true;
      };
    }

    setIsSourceSpeakersLoading(true);
    requestJson<SpeakerProfilePayload>(
      `/speakers/profiles?project_id=${encodeURIComponent(sourceProjectId)}`,
    )
      .then((payload) => {
        if (canceled) {
          return;
        }
        setSourceSpeakers(payload.items);
        setSourceSpeakerName((current) =>
          current === "__all__" || payload.items.some((speaker) => speaker.name === current)
            ? current
            : "__all__",
        );
      })
      .catch((error) => {
        if (canceled) {
          return;
        }
        setSourceSpeakers([]);
        props.setNotice({
          tone: "error",
          message: error instanceof Error ? error.message : "加载来源项目角色失败。",
        });
      })
      .finally(() => {
        if (!canceled) {
          setIsSourceSpeakersLoading(false);
        }
      });

    return () => {
      canceled = true;
    };
  }, [sourceProjectId]);

  useEffect(() => {
    if (isCreating || !props.project) {
      return;
    }
    if (!activeSpeakerName && props.speakers[0]) {
      setActiveSpeakerName(props.speakers[0].name);
    }
    if (
      activeSpeakerName &&
      !props.speakers.some((speaker) => speaker.name === activeSpeakerName)
    ) {
      setActiveSpeakerName(props.speakers[0]?.name ?? "");
    }
  }, [activeSpeakerName, isCreating, props.project, props.speakers]);

  useEffect(() => {
    if (isCreating) {
      setForm(createBlankForm());
      setSelectedFile(null);
      return;
    }
    setForm(buildForm(activeSpeaker));
    setSelectedFile(null);
  }, [activeSpeaker, isCreating]);

  async function saveSpeaker() {
    if (!props.project) {
      props.setNotice({ tone: "error", message: "请先到项目配置页选择一个项目。" });
      return;
    }
    if (!form.name.trim()) {
      props.setNotice({ tone: "error", message: "请先填写角色名称。" });
      return;
    }
    if (!selectedFile && !activeSpeaker) {
      props.setNotice({ tone: "error", message: "新建角色时必须上传参考音频。" });
      return;
    }

    setIsSaving(true);
    try {
      const payload = new FormData();
      payload.append("project_id", props.project.id);
      payload.append("name", form.name.trim());
      appendIfPresent(payload, "temperature", form.temperature);
      appendIfPresent(payload, "top_p", form.topP);
      appendIfPresent(payload, "top_k", form.topK);
      appendIfPresent(payload, "interval_silence", form.intervalSilence);
      appendIfPresent(payload, "num_beams", form.numBeams);
      appendIfPresent(payload, "repetition_penalty", form.repetitionPenalty);
      appendIfPresent(payload, "length_penalty", form.lengthPenalty);
      appendIfPresent(payload, "emo_text", form.emoText);
      appendIfPresent(payload, "text_split_method", form.textSplitMethod);
      appendIfPresent(payload, "emo_vector", form.emoVector);
      payload.append("use_emo_text", String(form.useEmoText));
      payload.append("use_random", String(form.useRandom));
      if (selectedFile) {
        payload.append("ref_audio", selectedFile);
      }

      const profile = await requestJson<SpeakerProfile>("/speakers", {
        method: "POST",
        body: payload,
      });
      setIsCreating(false);
      setActiveSpeakerName(profile.name);
      setSelectedFile(null);
      props.setNotice({
        tone: "success",
        message: `角色 ${profile.name} 已保存到项目 ${props.project.name}。`,
      });
      await props.onRefresh();
    } catch (error) {
      props.setNotice({
        tone: "error",
        message: error instanceof Error ? error.message : "保存角色失败。",
      });
    } finally {
      setIsSaving(false);
    }
  }

  async function deleteSpeaker() {
    if (!props.project || !activeSpeaker) {
      return;
    }
    const confirmed = window.confirm(`确认删除角色“${activeSpeaker.name}”吗？`);
    if (!confirmed) {
      return;
    }

    setIsDeleting(true);
    try {
      await requestJson<{ name: string }>(
        `/speakers/${encodeURIComponent(activeSpeaker.name)}?project_id=${encodeURIComponent(props.project.id)}`,
        { method: "DELETE" },
      );
      props.setNotice({
        tone: "success",
        message: `角色 ${activeSpeaker.name} 已从项目 ${props.project.name} 删除。`,
      });
      setActiveSpeakerName("");
      setIsCreating(false);
      await props.onRefresh();
    } catch (error) {
      props.setNotice({
        tone: "error",
        message: error instanceof Error ? error.message : "删除角色失败。",
      });
    } finally {
      setIsDeleting(false);
    }
  }

  async function copySpeakersFromProject() {
    if (!props.project) {
      props.setNotice({ tone: "error", message: "请先选择目标项目。" });
      return;
    }
    if (!sourceProjectId) {
      props.setNotice({ tone: "error", message: "请先选择来源项目。" });
      return;
    }
    if (sourceSpeakers.length === 0) {
      props.setNotice({ tone: "error", message: "来源项目还没有可复用角色。" });
      return;
    }

    setIsCopyingSpeaker(true);
    try {
      const payload = await requestJson<SpeakerCopyPayload>("/speakers/copy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_project_id: sourceProjectId,
          target_project_id: props.project.id,
          speaker_names: sourceSpeakerName === "__all__" ? [] : [sourceSpeakerName],
          overwrite: overwriteExisting,
        }),
      });
      setIsCreating(false);
      setActiveSpeakerName(payload.items[0]?.name ?? "");
      props.setNotice({
        tone: "success",
        message: `已复用 ${payload.items.length} 个角色到项目 ${props.project.name}。`,
      });
      await props.onRefresh();
    } catch (error) {
      props.setNotice({
        tone: "error",
        message: error instanceof Error ? error.message : "复用角色失败。",
      });
    } finally {
      setIsCopyingSpeaker(false);
    }
  }

  function startCreateSpeaker() {
    setIsCreating(true);
    setActiveSpeakerName("");
    setForm(createBlankForm());
    setSelectedFile(null);
  }

  if (!props.project) {
    return (
      <div className="glass-card p-5 md:p-6">
        <EmptyState title="请先选择项目" />
      </div>
    );
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[320px,minmax(0,1fr)]">
      <aside className="glass-card p-5">
        <div className="eyebrow">项目角色</div>
        <div className="mt-4 flex items-center justify-between">
          <h2 className="font-display text-2xl font-semibold text-ink">角色列表</h2>
          <BadgeCheck className="h-5 w-5 text-slate-500" />
        </div>

        <button
          className="action-button action-button-secondary mt-4 w-full justify-center"
          onClick={startCreateSpeaker}
          type="button"
        >
          <Plus className="h-4 w-4" />
          新建角色
        </button>

        <div className="mt-4 rounded-[24px] border border-white/70 bg-slate-100/55 p-4 shadow-inner">
          <div className="flex items-center justify-between gap-3">
            <div className="eyebrow">复用角色</div>
            <Copy className="h-4 w-4 text-slate-500" />
          </div>
          <div className="mt-4 space-y-3">
            <FieldLabel label="来源项目">
              <select
                className="field-shell w-full"
                disabled={sourceProjects.length === 0}
                onChange={(event) => setSourceProjectId(event.target.value)}
                value={sourceProjectId}
              >
                {sourceProjects.length === 0 ? (
                  <option value="">暂无其他项目</option>
                ) : null}
                {sourceProjects.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.name}
                  </option>
                ))}
              </select>
            </FieldLabel>
            <FieldLabel label="来源角色">
              <select
                className="field-shell w-full"
                disabled={!sourceProjectId || sourceSpeakers.length === 0 || isSourceSpeakersLoading}
                onChange={(event) => setSourceSpeakerName(event.target.value)}
                value={sourceSpeakerName}
              >
                <option value="__all__">
                  {isSourceSpeakersLoading ? "加载中" : "全部角色"}
                </option>
                {sourceSpeakers.map((speaker) => (
                  <option key={speaker.name} value={speaker.name}>
                    {speaker.name}
                  </option>
                ))}
              </select>
            </FieldLabel>
            <label className="flex items-center gap-2 text-sm font-semibold text-slate-600">
              <input
                checked={overwriteExisting}
                className="h-4 w-4 accent-slate-900"
                onChange={(event) => setOverwriteExisting(event.target.checked)}
                type="checkbox"
              />
              覆盖当前项目同名角色
            </label>
            <button
              className="action-button action-button-secondary w-full justify-center"
              disabled={
                isCopyingSpeaker ||
                isSourceSpeakersLoading ||
                !sourceProjectId ||
                sourceSpeakers.length === 0
              }
              onClick={() => void copySpeakersFromProject()}
              type="button"
            >
              {isCopyingSpeaker ? (
                <LoaderCircle className="h-4 w-4 animate-spin" />
              ) : (
                <Copy className="h-4 w-4" />
              )}
              复用到当前项目
            </button>
          </div>
        </div>

        <div className="mt-4 space-y-3">
          {props.speakers.length === 0 ? (
            <EmptyState title="当前项目还没有角色" />
          ) : (
            props.speakers.map((speaker) => {
              const active = !isCreating && speaker.name === activeSpeakerName;
              return (
                <button
                  key={speaker.name}
                  className={`w-full rounded-[24px] border px-4 py-4 text-left transition-all duration-200 active:scale-[0.98] ${
                    active
                      ? "border-slate-900 bg-slate-900 text-white shadow-[0_20px_40px_-26px_rgba(15,23,42,0.8)]"
                      : "border-white/70 bg-white/70 text-slate-700 hover:bg-white"
                  }`}
                  onClick={() => {
                    setIsCreating(false);
                    setActiveSpeakerName(speaker.name);
                  }}
                  type="button"
                >
                  <div className="text-sm font-semibold">{speaker.name}</div>
                  <div className={`mt-2 text-xs leading-6 ${active ? "text-white/75" : "text-slate-500"}`}>
                    {speaker.ref_audio}
                  </div>
                </button>
              );
            })
          )}
        </div>
      </aside>

      <section className="glass-card p-5 md:p-6">
        <div className="flex flex-col gap-3 border-b border-white/55 pb-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <div className="eyebrow">角色编辑器</div>
            <h2 className="mt-3 font-display text-2xl font-semibold text-ink">
              {activeSpeaker ? `编辑 ${activeSpeaker.name}` : "创建新角色"}
            </h2>
          </div>
          <div className="flex flex-wrap gap-3">
            {activeSpeaker ? (
              <button
                className="action-button action-button-ghost"
                disabled={isDeleting}
                onClick={() => void deleteSpeaker()}
                type="button"
              >
                {isDeleting ? (
                  <LoaderCircle className="h-4 w-4 animate-spin" />
                ) : (
                  <Trash2 className="h-4 w-4" />
                )}
                删除角色
              </button>
            ) : null}
            <button
              className="action-button action-button-primary"
              disabled={isSaving}
              onClick={() => void saveSpeaker()}
              type="button"
            >
              {isSaving ? (
                <LoaderCircle className="h-4 w-4 animate-spin" />
              ) : (
                <Save className="h-4 w-4" />
              )}
              保存角色
            </button>
          </div>
        </div>

        <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr),340px]">
          <div className="space-y-4">
            <div className="rounded-[30px] border border-white/70 bg-slate-100/55 p-4 shadow-inner">
              <div className="eyebrow">基础信息</div>
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <FieldLabel label="角色名称">
                  <input
                    className="field-shell w-full"
                    onChange={(event) =>
                      setForm((current) => ({ ...current, name: event.target.value }))
                    }
                    placeholder="例如 主角A"
                    value={form.name}
                  />
                </FieldLabel>
                <FieldLabel label="参考音频">
                  <input
                    accept=".wav,.mp3,audio/wav,audio/mpeg"
                    className="field-shell w-full file:mr-3 file:rounded-full file:border-0 file:bg-slate-900 file:px-3 file:py-2 file:text-sm file:font-semibold file:text-white"
                    onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
                    type="file"
                  />
                </FieldLabel>
              </div>
              <p className="mt-3 text-xs leading-6 text-slate-500">
                新建时需上传；编辑时不上传则沿用现有音频。
              </p>
            </div>

            <div className="rounded-[30px] border border-white/70 bg-slate-100/55 p-4 shadow-inner">
              <div className="eyebrow">默认参数</div>
              <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                <FieldLabel label="采样温度">
                  <input className="field-shell w-full" onChange={(event) => setForm((current) => ({ ...current, temperature: event.target.value }))} type="number" value={form.temperature} />
                </FieldLabel>
                <FieldLabel label="Top P">
                  <input className="field-shell w-full" onChange={(event) => setForm((current) => ({ ...current, topP: event.target.value }))} type="number" value={form.topP} />
                </FieldLabel>
                <FieldLabel label="Top K">
                  <input className="field-shell w-full" onChange={(event) => setForm((current) => ({ ...current, topK: event.target.value }))} type="number" value={form.topK} />
                </FieldLabel>
                <FieldLabel label="句间静音">
                  <input className="field-shell w-full" onChange={(event) => setForm((current) => ({ ...current, intervalSilence: event.target.value }))} type="number" value={form.intervalSilence} />
                </FieldLabel>
                <FieldLabel label="搜索束数">
                  <input className="field-shell w-full" onChange={(event) => setForm((current) => ({ ...current, numBeams: event.target.value }))} type="number" value={form.numBeams} />
                </FieldLabel>
                <FieldLabel label="重复惩罚">
                  <input className="field-shell w-full" onChange={(event) => setForm((current) => ({ ...current, repetitionPenalty: event.target.value }))} type="number" value={form.repetitionPenalty} />
                </FieldLabel>
                <FieldLabel label="长度惩罚">
                  <input className="field-shell w-full" onChange={(event) => setForm((current) => ({ ...current, lengthPenalty: event.target.value }))} type="number" value={form.lengthPenalty} />
                </FieldLabel>
                <FieldLabel label="情绪文本">
                  <input className="field-shell w-full" onChange={(event) => setForm((current) => ({ ...current, emoText: event.target.value }))} value={form.emoText} />
                </FieldLabel>
                <FieldLabel label="切分策略">
                  <input className="field-shell w-full" onChange={(event) => setForm((current) => ({ ...current, textSplitMethod: event.target.value }))} value={form.textSplitMethod} />
                </FieldLabel>
              </div>

              <div className="mt-4">
                <FieldLabel label="情绪向量数组">
                  <textarea
                    className="field-shell min-h-[92px] w-full resize-y"
                    onChange={(event) =>
                      setForm((current) => ({ ...current, emoVector: event.target.value }))
                    }
                    placeholder="[0.1, 0.2, 0.3]"
                    value={form.emoVector}
                  />
                </FieldLabel>
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-2">
                <ToggleTile
                  checked={form.useEmoText}
                  label="启用情绪文本"
                  onChange={(checked) =>
                    setForm((current) => ({ ...current, useEmoText: checked }))
                  }
                />
                <ToggleTile
                  checked={form.useRandom}
                  label="启用随机采样"
                  onChange={(checked) =>
                    setForm((current) => ({ ...current, useRandom: checked }))
                  }
                />
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <AudioCard
              title="参考音频预览"
              description={selectedFile ? `待上传：${selectedFile.name}` : undefined}
              path={activeSpeaker?.ref_audio}
              secondary={activeSpeaker?.ref_audio ? undefined : "保存后可在这里试听"}
            />
          </div>
        </div>
      </section>
    </div>
  );
}

function appendIfPresent(payload: FormData, key: string, value: string) {
  if (!value.trim()) {
    return;
  }
  payload.append(key, value.trim());
}
