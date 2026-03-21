import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  FileAudio2,
  FolderKanban,
  Layers3,
  LoaderCircle,
  RefreshCcw,
  Sparkles,
  UserRound,
  WifiOff,
  type LucideIcon,
} from "lucide-react";
import { startTransition, useEffect, useEffectEvent, useMemo, useState } from "react";

import { FieldLabel, MetricChip } from "./components";
import { displayStatus, noticeClasses, requestJson, statusClasses } from "./lib";
import { JobsPage } from "./pages/JobsPage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { RolesPage } from "./pages/RolesPage";
import { StudioPage } from "./pages/StudioPage";
import type {
  HealthPayload,
  JobLinesPayload,
  JobListPayload,
  Notice,
  ProjectConfig,
  ProjectListPayload,
  SingleResult,
  SpeakerProfile,
  SpeakerProfilePayload,
  StudioPageId,
} from "./types";

const PROJECT_STORAGE_KEY = "indextts-studio:selected-project";
const EPISODE_STORAGE_PREFIX = "indextts-studio:selected-episode";

type NavItem = {
  id: StudioPageId;
  title: string;
  description: string;
  icon: LucideIcon;
};

function HealthStatusIcon(props: { status?: string | null }) {
  const normalized = props.status?.toLowerCase() ?? "";
  if (normalized === "ok") {
    return <CheckCircle2 className="h-3.5 w-3.5" />;
  }
  if (normalized === "offline") {
    return <WifiOff className="h-3.5 w-3.5" />;
  }
  if (normalized === "failed") {
    return <AlertTriangle className="h-3.5 w-3.5" />;
  }
  if (normalized === "running") {
    return <Activity className="h-3.5 w-3.5" />;
  }
  return <CircleDashed className="h-3.5 w-3.5" />;
}

function readPageFromHash(): StudioPageId {
  const raw = window.location.hash.replace(/^#\/?/, "");
  if (raw === "projects" || raw === "roles" || raw === "studio" || raw === "jobs") {
    return raw;
  }
  return "projects";
}

function readStoredProjectId(): string {
  return window.localStorage.getItem(PROJECT_STORAGE_KEY) ?? "";
}

function selectedEpisodeStorageKey(projectId: string): string {
  return `${EPISODE_STORAGE_PREFIX}:${projectId}`;
}

function readStoredEpisodeId(projectId: string): string {
  return window.localStorage.getItem(selectedEpisodeStorageKey(projectId)) ?? "";
}

function pageHeading(page: StudioPageId): { title: string; description: string } {
  if (page === "projects") {
    return {
      title: "项目配置",
      description: "在独立页面里创建项目、维护说明，并为项目添加分集。",
    };
  }
  if (page === "roles") {
    return {
      title: "角色管理",
      description: "为当前项目维护参考音频和默认参数，角色之间按项目隔离。",
    };
  }
  if (page === "studio") {
    return {
      title: "文本配音",
      description: "围绕当前项目和分集维护台词表，单句试听与多选批量生成合并在同一工作台中。",
    };
  }
  return {
    title: "任务试听",
    description: "查看异步任务、逐句结果和最近一次试听输出。",
  };
}

export default function App() {
  const [page, setPage] = useState<StudioPageId>(() => readPageFromHash());
  const [health, setHealth] = useState<HealthPayload | null>(null);
  const [projects, setProjects] = useState<ProjectConfig[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>(readStoredProjectId);
  const [selectedEpisodeId, setSelectedEpisodeId] = useState("");
  const [speakers, setSpeakers] = useState<SpeakerProfile[]>([]);
  const [jobs, setJobs] = useState<JobListPayload["items"]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [jobLines, setJobLines] = useState<JobLinesPayload["items"]>([]);
  const [singleResult, setSingleResult] = useState<SingleResult | null>(null);
  const [notice, setNotice] = useState<Notice>({
    tone: "info",
    message: "先到项目配置页创建项目和分集，再进入角色管理和文本配音页面。",
  });
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isJobLinesLoading, setIsJobLinesLoading] = useState(false);

  const activeProject = useMemo(
    () => projects.find((project) => project.id === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  );
  const activeEpisode = useMemo(
    () => activeProject?.episodes.find((episode) => episode.id === selectedEpisodeId) ?? null,
    [activeProject, selectedEpisodeId],
  );
  const header = useMemo(() => pageHeading(page), [page]);
  const navItems = useMemo<NavItem[]>(
    () => [
      {
        id: "projects",
        title: "项目配置",
        description: "创建项目与分集",
        icon: FolderKanban,
      },
      {
        id: "roles",
        title: "角色管理",
        description: "上传参考音频与角色参数",
        icon: UserRound,
      },
      {
        id: "studio",
        title: "文本配音",
        description: "表格化编排并批量生成",
        icon: FileAudio2,
      },
      {
        id: "jobs",
        title: "任务试听",
        description: "查看任务状态与输出",
        icon: Layers3,
      },
    ],
    [],
  );

  useEffect(() => {
    const handleHashChange = () => setPage(readPageFromHash());
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  useEffect(() => {
    if (selectedProjectId) {
      window.localStorage.setItem(PROJECT_STORAGE_KEY, selectedProjectId);
      return;
    }
    window.localStorage.removeItem(PROJECT_STORAGE_KEY);
  }, [selectedProjectId]);

  useEffect(() => {
    if (!activeProject) {
      if (selectedEpisodeId) {
        setSelectedEpisodeId("");
      }
      return;
    }

    const storedEpisodeId = readStoredEpisodeId(activeProject.id);
    const nextEpisodeId =
      activeProject.episodes.find((episode) => episode.id === selectedEpisodeId)?.id ??
      activeProject.episodes.find((episode) => episode.id === storedEpisodeId)?.id ??
      activeProject.episodes[0]?.id ??
      "";

    if (nextEpisodeId !== selectedEpisodeId) {
      setSelectedEpisodeId(nextEpisodeId);
    }
  }, [activeProject, selectedEpisodeId]);

  useEffect(() => {
    if (!activeProject) {
      return;
    }
    const key = selectedEpisodeStorageKey(activeProject.id);
    if (selectedEpisodeId) {
      window.localStorage.setItem(key, selectedEpisodeId);
      return;
    }
    window.localStorage.removeItem(key);
  }, [activeProject, selectedEpisodeId]);

  const refreshOverview = useEffectEvent(async () => {
    setIsRefreshing(true);
    try {
      const [healthData, projectData, jobData] = await Promise.all([
        requestJson<HealthPayload>("/health"),
        requestJson<ProjectListPayload>("/projects"),
        requestJson<JobListPayload>("/jobs"),
      ]);

      const effectiveProjectId =
        projectData.items.find((item) => item.id === selectedProjectId)?.id ??
        projectData.items[0]?.id ??
        "";

      const speakerData = effectiveProjectId
        ? await requestJson<SpeakerProfilePayload>(
            `/speakers/profiles?project_id=${encodeURIComponent(effectiveProjectId)}`,
          )
        : { items: [] };

      startTransition(() => {
        setHealth(healthData);
        setProjects(projectData.items);
        setSelectedProjectId(effectiveProjectId);
        setSpeakers(speakerData.items);
        setJobs(jobData.items);

        if (!selectedJobId && jobData.items[0]) {
          setSelectedJobId(jobData.items[0].job_id);
        }
        if (selectedJobId && !jobData.items.some((item) => item.job_id === selectedJobId)) {
          setSelectedJobId(jobData.items[0]?.job_id ?? null);
        }
      });
    } catch (error) {
      setHealth({ status: "offline" });
      setNotice({
        tone: "error",
        message: error instanceof Error ? error.message : "刷新概览失败。",
      });
    } finally {
      setIsRefreshing(false);
    }
  });

  const loadJobLines = useEffectEvent(async (jobId: string) => {
    setIsJobLinesLoading(true);
    try {
      const payload = await requestJson<JobLinesPayload>(`/jobs/${jobId}/lines`);
      startTransition(() => setJobLines(payload.items));
    } catch (error) {
      setJobLines([]);
      setNotice({
        tone: "error",
        message: error instanceof Error ? error.message : "加载任务明细失败。",
      });
    } finally {
      setIsJobLinesLoading(false);
    }
  });

  useEffect(() => {
    void refreshOverview();
    const timer = window.setInterval(() => {
      void refreshOverview();
    }, 3000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    void refreshOverview();
  }, [selectedProjectId]);

  useEffect(() => {
    if (!selectedJobId) {
      setJobLines([]);
      return;
    }
    void loadJobLines(selectedJobId);
  }, [selectedJobId]);

  function navigateTo(nextPage: StudioPageId) {
    window.location.hash = `#/${nextPage}`;
  }

  const handleJobQueued = useEffectEvent(async (jobId: string) => {
    startTransition(() => setSelectedJobId(jobId));
    await refreshOverview();
    void loadJobLines(jobId);
  });

  return (
    <div className="relative z-10 min-h-screen px-4 py-4 md:px-6">
      <div className="mx-auto grid max-w-[1680px] gap-4 xl:grid-cols-[260px,minmax(0,1fr)]">
        <aside className="glass-shell h-full px-4 py-4 md:px-5 md:py-5">
          <div className="border-b border-white/55 pb-5">
            <div className="mt-3 flex items-center gap-3">
              <h1 className="font-display text-4xl font-bold tracking-tight text-ink">
                IndexTTS
                Studio
              </h1>
            </div>
            <div className="eyebrow text-2xl">配音控制台</div>
          </div>

          <nav className="mt-5 space-y-3">
            {navItems.map((item) => {
              const active = item.id === page;
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  className={`w-full rounded-[24px] border px-4 py-4 text-left transition-all duration-200 active:scale-[0.98] ${
                    active
                      ? "border-slate-900 bg-slate-900 text-white shadow-[0_20px_40px_-26px_rgba(15,23,42,0.8)]"
                      : "border-white/70 bg-white/72 text-slate-700 hover:bg-white"
                  }`}
                  onClick={() => navigateTo(item.id)}
                  type="button"
                >
                  <div className="flex items-center gap-3">
                    <Icon className="h-4 w-4" />
                    <span className="font-semibold">{item.title}</span>
                  </div>
                  <div className={`mt-2 text-sm leading-7 ${active ? "text-white/75" : "text-slate-500"}`}>
                    {item.description}
                  </div>
                </button>
              );
            })}
          </nav>

          <div className="mt-5 grid gap-2">
            <MetricChip
              icon={<FolderKanban className="h-4 w-4" />}
              label="项目"
              value={String(projects.length)}
            />
            <MetricChip
              icon={<UserRound className="h-4 w-4" />}
              label="角色"
              value={String(speakers.length)}
            />
            <MetricChip
              icon={<Layers3 className="h-4 w-4" />}
              label="任务"
              value={String(jobs.length)}
            />
          </div>
        </aside>

        <div className="space-y-4">
          <header className="glass-shell px-4 py-4 md:px-6 md:py-5">
            <div className="flex flex-col gap-5 border-b border-white/55 pb-5 xl:flex-row xl:items-start xl:justify-between">
              <div className="max-w-3xl">
                <div className="mt-3 flex flex-wrap items-center gap-3">
                  <h2 className="font-display text-3xl font-semibold text-ink md:text-4xl">
                    {header.title}
                  </h2>
                  <span className={statusClasses(health?.status ?? "offline")}>
                    <HealthStatusIcon status={health?.status} />
                    {displayStatus(health?.status ?? "offline")}
                  </span>
                </div>
                <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-600 md:text-base">
                  {header.description}
                </p>
              </div>

              <div className="flex flex-wrap gap-3 xl:justify-end">
                <button
                  className="action-button action-button-ghost"
                  disabled={isRefreshing}
                  onClick={() => void refreshOverview()}
                  type="button"
                >
                  {isRefreshing ? (
                    <LoaderCircle className="h-4 w-4 animate-spin" />
                  ) : (
                    <RefreshCcw className="h-4 w-4" />
                  )}
                  刷新
                </button>
                <a
                  className="action-button action-button-secondary"
                  href="/docs"
                  rel="noreferrer"
                  target="_blank"
                >
                  <Sparkles className="h-4 w-4" />
                  接口文档
                </a>
              </div>
            </div>

            <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,1fr),280px,280px]">
              <div className="rounded-[28px] border border-white/70 bg-slate-100/55 px-4 py-4 shadow-inner">
                <div className="eyebrow">当前上下文</div>
                <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-slate-600">
                  <span className="rounded-full border border-white/70 bg-white/72 px-3 py-2 font-semibold text-slate-700">
                    项目：{activeProject?.name ?? "未选择"}
                  </span>
                  <span className="rounded-full border border-white/70 bg-white/72 px-3 py-2 font-semibold text-slate-700">
                    分集：{activeEpisode?.name ?? "未选择"}
                  </span>
                </div>
              </div>

              <FieldLabel label="当前项目">
                <select
                  className="field-shell w-full"
                  onChange={(event) => setSelectedProjectId(event.target.value)}
                  value={selectedProjectId}
                >
                  {projects.length === 0 ? (
                    <option value="">请先创建项目</option>
                  ) : null}
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.name}
                    </option>
                  ))}
                </select>
              </FieldLabel>

              <FieldLabel label="当前分集">
                <select
                  className="field-shell w-full"
                  disabled={!activeProject || activeProject.episodes.length === 0}
                  onChange={(event) => setSelectedEpisodeId(event.target.value)}
                  value={selectedEpisodeId}
                >
                  {!activeProject ? (
                    <option value="">请先选择项目</option>
                  ) : activeProject.episodes.length === 0 ? (
                    <option value="">请先创建分集</option>
                  ) : null}
                  {activeProject?.episodes.map((episode) => (
                    <option key={episode.id} value={episode.id}>
                      {episode.name}
                    </option>
                  ))}
                </select>
              </FieldLabel>
            </div>
          </header>

          <div
            className={`rounded-[26px] border px-4 py-3 text-sm font-medium ${noticeClasses(
              notice.tone,
            )}`}
          >
            {notice.message}
          </div>

          <main>
            {page === "projects" ? (
              <ProjectsPage
                activeProject={activeProject}
                onRefresh={refreshOverview}
                projects={projects}
                selectedProjectId={selectedProjectId}
                setNotice={setNotice}
                setSelectedProjectId={setSelectedProjectId}
              />
            ) : null}

            {page === "roles" ? (
              <RolesPage
                onRefresh={refreshOverview}
                project={activeProject}
                setNotice={setNotice}
                speakers={speakers}
              />
            ) : null}

            {page === "studio" ? (
              <StudioPage
                activeEpisodeId={selectedEpisodeId}
                onJobQueued={handleJobQueued}
                onLatestResult={setSingleResult}
                project={activeProject}
                setNotice={setNotice}
                speakers={speakers}
              />
            ) : null}

            {page === "jobs" ? (
              <JobsPage
                isJobLinesLoading={isJobLinesLoading}
                jobLines={jobLines}
                jobs={jobs}
                onSelectJob={setSelectedJobId}
                selectedJobId={selectedJobId}
                singleResult={singleResult}
              />
            ) : null}
          </main>
        </div>
      </div>
    </div>
  );
}
