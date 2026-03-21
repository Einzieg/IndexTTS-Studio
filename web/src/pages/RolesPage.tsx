import { BadgeCheck, LoaderCircle, Plus, Save, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { AudioCard, EmptyState, FieldLabel, ToggleTile } from "../components";
import { requestJson, stringifyOptionList } from "../lib";
import type { Notice, ProjectConfig, SpeakerProfile } from "../types";

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

  function startCreateSpeaker() {
    setIsCreating(true);
    setActiveSpeakerName("");
    setForm(createBlankForm());
    setSelectedFile(null);
  }

  if (!props.project) {
    return (
      <div className="glass-card p-5 md:p-6">
        <EmptyState title="请先选择项目" description="先到项目配置页创建或选择一个项目，角色才会按项目独立管理。" />
      </div>
    );
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[320px,minmax(0,1fr)]">
      <aside className="glass-card p-5">
        <div className="eyebrow">项目角色</div>
        <div className="mt-4 flex items-center justify-between">
          <h2 className="font-display text-2xl font-semibold text-ink">角色列表</h2>
          <BadgeCheck className="h-5 w-5 text-slate-500" />
        </div>
        <p className="mt-2 text-sm leading-7 text-slate-600">
          当前页面只显示顶部导航栏所选项目下的角色。不同项目之间的参考音频和默认参数互不影响。
        </p>

        <button
          className="action-button action-button-secondary mt-4 w-full justify-center"
          onClick={startCreateSpeaker}
          type="button"
        >
          <Plus className="h-4 w-4" />
          新建角色
        </button>

        <div className="mt-4 space-y-3">
          {props.speakers.length === 0 ? (
            <EmptyState title="当前项目还没有角色" description="先创建一个角色并上传参考音频，文本配音页才能使用它。" />
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
        <div className="flex flex-col gap-3 border-b border-white/55 pb-5 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <div className="eyebrow">角色编辑器</div>
            <h2 className="mt-3 font-display text-2xl font-semibold text-ink">
              {activeSpeaker ? `编辑 ${activeSpeaker.name}` : "创建新角色"}
            </h2>
            <p className="mt-2 text-sm leading-7 text-slate-600">
              当前角色会保存到所选项目的独立目录里，只供该项目的文本配音使用。
            </p>
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

        <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1fr),340px]">
          <div className="space-y-5">
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
                新建角色必须上传参考音频；编辑时如果不重新上传，就会继续沿用已有音频。
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
              description={
                selectedFile
                  ? `待上传文件：${selectedFile.name}`
                  : "当前角色的参考音频会显示在这里，方便你确认项目内使用的是哪一份声音样本。"
              }
              path={activeSpeaker?.ref_audio}
              secondary={
                activeSpeaker
                  ? "修改并保存后，新的默认参数会立刻用于这个项目中的文本配音。"
                  : "创建角色后，这里会显示已经保存成功的参考音频。"
              }
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
