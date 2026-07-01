import { FolderPlus, Layers3, LoaderCircle, Save, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { EmptyState, FieldLabel } from "../components";
import { requestJson } from "../lib";
import type { Notice, ProjectConfig } from "../types";

type ProjectFormState = {
  name: string;
  description: string;
};

type EpisodeFormState = {
  name: string;
  description: string;
};

type RefreshProjectsOptions = {
  projectId?: string;
  episodeId?: string;
};

function createBlankProjectForm(): ProjectFormState {
  return {
    name: "",
    description: "",
  };
}

function createBlankEpisodeForm(): EpisodeFormState {
  return {
    name: "",
    description: "",
  };
}

function buildProjectForm(project?: ProjectConfig | null): ProjectFormState {
  if (!project) {
    return createBlankProjectForm();
  }
  return {
    name: project.name,
    description: project.description ?? "",
  };
}

export function ProjectsPage(props: {
  projects: ProjectConfig[];
  activeProject: ProjectConfig | null;
  selectedProjectId: string;
  setSelectedProjectId: (value: string) => void;
  setNotice: (notice: Notice) => void;
  onRefresh: (options?: RefreshProjectsOptions) => Promise<void>;
}) {
  const [isCreating, setIsCreating] = useState(props.projects.length === 0);
  const [projectForm, setProjectForm] = useState<ProjectFormState>(createBlankProjectForm);
  const [episodeForm, setEpisodeForm] = useState<EpisodeFormState>(createBlankEpisodeForm);
  const [isSavingProject, setIsSavingProject] = useState(false);
  const [isDeletingProject, setIsDeletingProject] = useState(false);
  const [isSavingEpisode, setIsSavingEpisode] = useState(false);
  const [deletingEpisodeId, setDeletingEpisodeId] = useState<string | null>(null);

  const activeProject = useMemo(
    () =>
      props.projects.find((project) => project.id === props.selectedProjectId) ?? props.activeProject,
    [props.activeProject, props.projects, props.selectedProjectId],
  );

  useEffect(() => {
    if (isCreating) {
      setProjectForm(createBlankProjectForm());
      return;
    }
    setProjectForm(buildProjectForm(activeProject));
  }, [activeProject?.id, isCreating]);

  async function saveProject() {
    if (!projectForm.name.trim()) {
      props.setNotice({ tone: "error", message: "请先填写项目名称。" });
      return;
    }

    setIsSavingProject(true);
    try {
      const project = await requestJson<ProjectConfig>("/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: isCreating ? undefined : activeProject?.id,
          name: projectForm.name.trim(),
          description: projectForm.description.trim() || undefined,
        }),
      });
      setIsCreating(false);
      props.setSelectedProjectId(project.id);
      setProjectForm(buildProjectForm(project));
      props.setNotice({
        tone: "success",
        message: `项目 ${project.name} 已保存。`,
      });
      await props.onRefresh({ projectId: project.id });
    } catch (error) {
      props.setNotice({
        tone: "error",
        message: error instanceof Error ? error.message : "保存项目失败。",
      });
    } finally {
      setIsSavingProject(false);
    }
  }

  async function deleteProject() {
    if (!activeProject) {
      return;
    }
    const confirmed = window.confirm(`确认删除项目“${activeProject.name}”吗？`);
    if (!confirmed) {
      return;
    }

    setIsDeletingProject(true);
    try {
      await requestJson<{ id: string }>(`/projects/${encodeURIComponent(activeProject.id)}`, {
        method: "DELETE",
      });
      props.setNotice({
        tone: "success",
        message: `项目 ${activeProject.name} 已删除。`,
      });
      props.setSelectedProjectId("");
      setIsCreating(true);
      setEpisodeForm(createBlankEpisodeForm());
      await props.onRefresh();
    } catch (error) {
      props.setNotice({
        tone: "error",
        message: error instanceof Error ? error.message : "删除项目失败。",
      });
    } finally {
      setIsDeletingProject(false);
    }
  }

  async function saveEpisode() {
    if (!activeProject) {
      props.setNotice({ tone: "error", message: "请先创建或选择一个项目。" });
      return;
    }
    if (!episodeForm.name.trim()) {
      props.setNotice({ tone: "error", message: "请先填写分集名称。" });
      return;
    }

    setIsSavingEpisode(true);
    try {
      const previousEpisodeIds = new Set(activeProject.episodes.map((episode) => episode.id));
      const episodeName = episodeForm.name.trim();
      const project = await requestJson<ProjectConfig>(
        `/projects/${encodeURIComponent(activeProject.id)}/episodes`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: episodeName,
            description: episodeForm.description.trim() || undefined,
          }),
        },
      );
      const savedEpisode =
        project.episodes.find((episode) => !previousEpisodeIds.has(episode.id)) ??
        project.episodes.find((episode) => episode.name === episodeName);
      setEpisodeForm(createBlankEpisodeForm());
      props.setSelectedProjectId(project.id);
      props.setNotice({
        tone: "success",
        message: `分集 ${episodeName} 已保存到项目 ${project.name}。`,
      });
      await props.onRefresh({ projectId: project.id, episodeId: savedEpisode?.id });
    } catch (error) {
      props.setNotice({
        tone: "error",
        message: error instanceof Error ? error.message : "保存分集失败。",
      });
    } finally {
      setIsSavingEpisode(false);
    }
  }

  async function deleteEpisode(episodeId: string, episodeName: string) {
    if (!activeProject) {
      return;
    }
    const confirmed = window.confirm(`确认删除分集“${episodeName}”吗？`);
    if (!confirmed) {
      return;
    }

    setDeletingEpisodeId(episodeId);
    try {
      await requestJson<ProjectConfig>(
        `/projects/${encodeURIComponent(activeProject.id)}/episodes/${encodeURIComponent(episodeId)}`,
        { method: "DELETE" },
      );
      props.setNotice({
        tone: "success",
        message: `分集 ${episodeName} 已删除。`,
      });
      await props.onRefresh();
    } catch (error) {
      props.setNotice({
        tone: "error",
        message: error instanceof Error ? error.message : "删除分集失败。",
      });
    } finally {
      setDeletingEpisodeId(null);
    }
  }

  function startCreateProject() {
    setIsCreating(true);
    setProjectForm(createBlankProjectForm());
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[320px,minmax(0,1fr)]">
      <aside className="glass-card p-5">
        <div className="eyebrow">项目管理</div>
        <div className="mt-4 flex items-center justify-between">
          <h2 className="font-display text-2xl font-semibold text-ink">项目列表</h2>
          <FolderPlus className="h-5 w-5 text-slate-500" />
        </div>

        <button
          className="action-button action-button-secondary mt-4 w-full justify-center"
          onClick={startCreateProject}
          type="button"
        >
          <FolderPlus className="h-4 w-4" />
          新建项目
        </button>

        <div className="mt-4 space-y-3">
          {props.projects.length === 0 ? (
            <EmptyState title="还没有项目" />
          ) : (
            props.projects.map((project) => {
              const active = !isCreating && project.id === props.selectedProjectId;
              return (
                <button
                  key={project.id}
                  className={`w-full rounded-[24px] border px-4 py-4 text-left transition-all duration-200 active:scale-[0.98] ${
                    active
                      ? "border-slate-900 bg-slate-900 text-white shadow-[0_20px_40px_-26px_rgba(15,23,42,0.8)]"
                      : "border-white/70 bg-white/70 text-slate-700 hover:bg-white"
                  }`}
                  onClick={() => {
                    setIsCreating(false);
                    props.setSelectedProjectId(project.id);
                  }}
                  type="button"
                >
                  <div className="font-semibold">{project.name}</div>
                  <div className={`mt-2 text-xs leading-6 ${active ? "text-white/75" : "text-slate-500"}`}>
                    项目 ID：{project.id}
                  </div>
                  <div className={`mt-1 text-xs leading-6 ${active ? "text-white/70" : "text-slate-400"}`}>
                    分集数：{project.episodes.length}
                  </div>
                </button>
              );
            })
          )}
        </div>
      </aside>

      <section className="space-y-4">
        <div className="glass-card p-5 md:p-6">
          <div className="flex flex-col gap-3 border-b border-white/55 pb-4 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <div className="eyebrow">项目信息</div>
              <h2 className="mt-3 font-display text-2xl font-semibold text-ink">
                {isCreating ? "创建新项目" : activeProject ? `编辑 ${activeProject.name}` : "选择一个项目"}
              </h2>
            </div>
            <div className="flex flex-wrap gap-3">
              {activeProject && !isCreating ? (
                <button
                  className="action-button action-button-ghost"
                  disabled={isDeletingProject}
                  onClick={() => void deleteProject()}
                  type="button"
                >
                  {isDeletingProject ? (
                    <LoaderCircle className="h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="h-4 w-4" />
                  )}
                  删除项目
                </button>
              ) : null}
              <button
                className="action-button action-button-primary"
                disabled={isSavingProject}
                onClick={() => void saveProject()}
                type="button"
              >
                {isSavingProject ? (
                  <LoaderCircle className="h-4 w-4 animate-spin" />
                ) : (
                  <Save className="h-4 w-4" />
                )}
                保存项目
              </button>
            </div>
          </div>

          <div className="mt-4 space-y-4">
            <FieldLabel label="项目名称">
              <input
                className="field-shell w-full"
                onChange={(event) =>
                  setProjectForm((current) => ({ ...current, name: event.target.value }))
                }
                placeholder="例如 第一季有声剧"
                value={projectForm.name}
              />
            </FieldLabel>

            <FieldLabel label="项目说明">
              <textarea
                className="field-shell min-h-[112px] w-full resize-y"
                onChange={(event) =>
                  setProjectForm((current) => ({ ...current, description: event.target.value }))
                }
                placeholder="可以填写用途、交付范围或角色说明。"
                value={projectForm.description}
              />
            </FieldLabel>

            {!isCreating && activeProject ? (
              <div className="rounded-[24px] border border-white/70 bg-slate-100/55 px-4 py-3 text-sm text-slate-600">
                当前项目 ID：<span className="font-semibold text-slate-800">{activeProject.id}</span>
              </div>
            ) : null}
          </div>
        </div>

        <div className="glass-card p-5 md:p-6">
          <div className="flex flex-col gap-3 border-b border-white/55 pb-4 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <div className="eyebrow">分集管理</div>
              <h2 className="mt-3 font-display text-2xl font-semibold text-ink">项目分集</h2>
            </div>
            <div className="inline-flex items-center gap-2 rounded-full border border-white/70 bg-white/72 px-4 py-2 text-sm text-slate-600">
              <Layers3 className="h-4 w-4" />
              分集数：{activeProject?.episodes.length ?? 0}
            </div>
          </div>

          {activeProject ? (
            <>
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <FieldLabel label="分集名称">
                  <input
                    className="field-shell w-full"
                    onChange={(event) =>
                      setEpisodeForm((current) => ({ ...current, name: event.target.value }))
                    }
                    placeholder="例如 第 1 集"
                    value={episodeForm.name}
                  />
                </FieldLabel>
                <FieldLabel label="分集说明">
                  <input
                    className="field-shell w-full"
                    onChange={(event) =>
                      setEpisodeForm((current) => ({ ...current, description: event.target.value }))
                    }
                    placeholder="可选"
                    value={episodeForm.description}
                  />
                </FieldLabel>
              </div>

              <button
                className="action-button action-button-primary mt-4"
                disabled={isSavingEpisode}
                onClick={() => void saveEpisode()}
                type="button"
              >
                {isSavingEpisode ? (
                  <LoaderCircle className="h-4 w-4 animate-spin" />
                ) : (
                  <Save className="h-4 w-4" />
                )}
                保存分集
              </button>

              <div className="mt-4 space-y-3">
                {activeProject.episodes.length === 0 ? (
                  <EmptyState title="当前项目还没有分集" />
                ) : (
                  activeProject.episodes.map((episode) => (
                    <div
                      key={episode.id}
                      className="flex flex-col gap-3 rounded-[24px] border border-white/70 bg-white/72 px-4 py-4 md:flex-row md:items-center md:justify-between"
                    >
                      <div>
                        <div className="font-semibold text-slate-800">{episode.name}</div>
                        <div className="mt-2 text-xs leading-6 text-slate-500">分集 ID：{episode.id}</div>
                        {episode.description ? (
                          <div className="mt-1 text-sm leading-7 text-slate-500">{episode.description}</div>
                        ) : null}
                      </div>
                      <button
                        className="action-button action-button-ghost"
                        disabled={deletingEpisodeId === episode.id}
                        onClick={() => void deleteEpisode(episode.id, episode.name)}
                        type="button"
                      >
                        {deletingEpisodeId === episode.id ? (
                          <LoaderCircle className="h-4 w-4 animate-spin" />
                        ) : (
                          <Trash2 className="h-4 w-4" />
                        )}
                        删除分集
                      </button>
                    </div>
                  ))
                )}
              </div>
            </>
          ) : (
            <div className="mt-4">
              <EmptyState title="请先选择项目" />
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
