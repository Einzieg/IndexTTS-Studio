import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  FileAudio2,
  FolderKanban,
  Layers3,
  LoaderCircle,
  LogOut,
  RefreshCcw,
  Sparkles,
  UserRound,
  WifiOff,
  type LucideIcon,
} from "lucide-react";
import { startTransition, useEffect, useEffectEvent, useMemo, useRef, useState } from "react";

import { FieldLabel, MetricChip } from "./components";
import {
  AUTH_REQUIRED_EVENT,
  UnauthorizedError,
  displayStatus,
  noticeClasses,
  requestJson,
  statusClasses,
} from "./lib";
import { JobsPage } from "./pages/JobsPage";
import { LoginPage } from "./pages/LoginPage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { RolesPage } from "./pages/RolesPage";
import { StudioPage } from "./pages/StudioPage";
import type {
  AuthSessionPayload,
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
  description?: string;
  icon: LucideIcon;
};

type RefreshOverviewOptions = {
  projectId?: string;
  episodeId?: string;
  includeSpeakers?: boolean;
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

function pageHeading(page: StudioPageId): { title: string; description?: string } {
  if (page === "projects") {
      return {
        title: "项目配置",
      };
  }
  if (page === "roles") {
      return {
        title: "角色管理",
      };
  }
  if (page === "studio") {
      return {
        title: "文本配音",
      };
  }
  return {
    title: "任务管理",
  };
}

export default function App() {
  const [page, setPage] = useState<StudioPageId>(() => readPageFromHash());
  const [authSession, setAuthSession] = useState<AuthSessionPayload | null>(null);
  const [isAuthChecking, setIsAuthChecking] = useState(true);
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);
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
    message: "请先创建项目和分集。",
  });
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isJobLinesLoading, setIsJobLinesLoading] = useState(false);
  const overviewRequestId = useRef(0);
  const speakerRequestId = useRef(0);
  const jobLinesRequestId = useRef(0);

  const activeProject = useMemo(
    () => projects.find((project) => project.id === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  );
  const activeEpisode = useMemo(
    () => activeProject?.episodes.find((episode) => episode.id === selectedEpisodeId) ?? null,
    [activeProject, selectedEpisodeId],
  );
  const selectedJob = useMemo(
    () => jobs.find((job) => job.job_id === selectedJobId) ?? null,
    [jobs, selectedJobId],
  );
  const authEnabled = authSession?.enabled ?? false;
  const isAuthenticated = authSession?.authenticated ?? false;
  const header = useMemo(() => pageHeading(page), [page]);
  const navItems = useMemo<NavItem[]>(
    () => [
      {
        id: "projects",
        title: "项目配置",
        icon: FolderKanban,
      },
      {
        id: "roles",
        title: "角色管理",
        icon: UserRound,
      },
      {
        id: "studio",
        title: "文本配音",
        icon: FileAudio2,
      },
      {
        id: "jobs",
        title: "任务管理",
        icon: Layers3,
      },
    ],
    [],
  );

  const loadAuthSession = useEffectEvent(async () => {
    setIsAuthChecking(true);
    try {
      const payload = await requestJson<AuthSessionPayload>("/auth/session");
      startTransition(() => {
        setAuthSession(payload);
        setLoginError(null);
      });
    } catch (error) {
      startTransition(() => {
        setAuthSession({ enabled: false, authenticated: true, username: null });
        setLoginError(null);
      });
      setNotice({
        tone: "error",
        message: error instanceof Error ? error.message : "加载登录状态失败。",
      });
    } finally {
      setIsAuthChecking(false);
    }
  });

  useEffect(() => {
    const handleHashChange = () => setPage(readPageFromHash());
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  useEffect(() => {
    const handleAuthRequired = () => {
      startTransition(() => {
        setAuthSession((current) => ({
          enabled: current?.enabled ?? true,
          authenticated: false,
          username: null,
        }));
        setLoginError("登录已失效，请重新登录。");
      });
    };
    window.addEventListener(AUTH_REQUIRED_EVENT, handleAuthRequired);
    return () => window.removeEventListener(AUTH_REQUIRED_EVENT, handleAuthRequired);
  }, []);

  useEffect(() => {
    void loadAuthSession();
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

  const loadSpeakersForProject = useEffectEvent(async (projectId: string) => {
    const requestId = ++speakerRequestId.current;
    if (!projectId) {
      startTransition(() => setSpeakers([]));
      return;
    }

    try {
      const speakerData = await requestJson<SpeakerProfilePayload>(
        `/speakers/profiles?project_id=${encodeURIComponent(projectId)}`,
      );
      if (requestId !== speakerRequestId.current) {
        return;
      }
      startTransition(() => setSpeakers(speakerData.items));
    } catch (error) {
      if (requestId !== speakerRequestId.current || error instanceof UnauthorizedError) {
        return;
      }
      startTransition(() => setSpeakers([]));
      setNotice({
        tone: "error",
        message: error instanceof Error ? error.message : "加载角色数据失败。",
      });
    }
  });

  const refreshOverview = useEffectEvent(async (options?: RefreshOverviewOptions) => {
    const requestId = ++overviewRequestId.current;
    setIsRefreshing(true);
    try {
      const healthData = await requestJson<HealthPayload>("/health");
      if (requestId !== overviewRequestId.current) {
        return;
      }
      setHealth(healthData);

      const [projectData, jobData] = await Promise.all([
        requestJson<ProjectListPayload>("/projects"),
        requestJson<JobListPayload>("/jobs"),
      ]);
      if (requestId !== overviewRequestId.current) {
        return;
      }

      const preferredProjectId = options?.projectId ?? selectedProjectId;
      const effectiveProjectId =
        projectData.items.find((item) => item.id === preferredProjectId)?.id ??
        projectData.items[0]?.id ??
        "";
      const effectiveProject = projectData.items.find((item) => item.id === effectiveProjectId);
      const effectiveEpisodeId =
        options?.episodeId !== undefined
          ? (effectiveProject?.episodes.find((episode) => episode.id === options.episodeId)?.id ?? "")
          : undefined;

      startTransition(() => {
        setProjects(projectData.items);
        setSelectedProjectId((currentProjectId) => {
          if (options?.projectId !== undefined) {
            return effectiveProjectId;
          }
          if (projectData.items.some((item) => item.id === currentProjectId)) {
            return currentProjectId;
          }
          return effectiveProjectId;
        });
        if (effectiveEpisodeId !== undefined) {
          setSelectedEpisodeId(effectiveEpisodeId);
        }
        setJobs(jobData.items);

        if (!selectedJobId && jobData.items[0]) {
          setSelectedJobId(jobData.items[0].job_id);
        }
        if (selectedJobId && !jobData.items.some((item) => item.job_id === selectedJobId)) {
          setSelectedJobId(jobData.items[0]?.job_id ?? null);
        }
      });

      if (options?.includeSpeakers) {
        await loadSpeakersForProject(effectiveProjectId);
      }
    } catch (error) {
      if (error instanceof UnauthorizedError) {
        return;
      }
      setHealth((current) => current ?? { status: "offline" });
      setNotice({
        tone: "error",
        message: error instanceof Error ? error.message : "刷新概览失败。",
      });
    } finally {
      if (requestId === overviewRequestId.current) {
        setIsRefreshing(false);
      }
    }
  });

  const loadJobLines = useEffectEvent(async (jobId: string, showLoading = true) => {
    const requestId = ++jobLinesRequestId.current;
    if (showLoading) {
      setIsJobLinesLoading(true);
    }
    try {
      const payload = await requestJson<JobLinesPayload>(`/jobs/${jobId}/lines`);
      if (requestId !== jobLinesRequestId.current || jobId !== selectedJobId) {
        return;
      }
      startTransition(() => setJobLines(payload.items));
    } catch (error) {
      if (error instanceof UnauthorizedError) {
        return;
      }
      if (requestId === jobLinesRequestId.current) {
        setJobLines([]);
        setNotice({
          tone: "error",
          message: error instanceof Error ? error.message : "加载任务明细失败。",
        });
      }
    } finally {
      if (requestId === jobLinesRequestId.current) {
        setIsJobLinesLoading(false);
      }
    }
  });

  useEffect(() => {
    if (authSession === null || (authEnabled && !isAuthenticated)) {
      return;
    }
    void refreshOverview();
    const timer = window.setInterval(() => {
      void refreshOverview();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [authSession, authEnabled, isAuthenticated]);

  useEffect(() => {
    if (authSession === null || (authEnabled && !isAuthenticated)) {
      return;
    }
    void loadSpeakersForProject(selectedProjectId);
  }, [selectedProjectId, authSession, authEnabled, isAuthenticated]);

  useEffect(() => {
    if (!selectedJobId) {
      jobLinesRequestId.current += 1;
      setJobLines([]);
      return;
    }
    void loadJobLines(selectedJobId, true);
    if (!selectedJob || !["queued", "running"].includes(selectedJob.status)) {
      return;
    }
    let cancelled = false;
    let timer: number | null = null;
    const poll = async () => {
      await loadJobLines(selectedJobId, false);
      if (!cancelled) {
        timer = window.setTimeout(() => {
          void poll();
        }, 1200);
      }
    };
    timer = window.setTimeout(() => {
      void poll();
    }, 1200);
    return () => {
      cancelled = true;
      if (timer !== null) {
        window.clearTimeout(timer);
      }
    };
  }, [loadJobLines, selectedJob?.status, selectedJobId]);

  function navigateTo(nextPage: StudioPageId) {
    window.location.hash = `#/${nextPage}`;
  }

  const handleJobQueued = useEffectEvent(async (jobId: string) => {
    startTransition(() => setSelectedJobId(jobId));
    await refreshOverview();
    void loadJobLines(jobId);
  });

  const handleLogin = useEffectEvent(async (username: string, password: string) => {
    setIsLoggingIn(true);
    setLoginError(null);
    try {
      const response = await fetch("/auth/login", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const payload = (await response.json()) as { success: boolean; message: string; data: AuthSessionPayload };
      if (!response.ok || !payload.success) {
        throw new Error(payload.message || "登录失败。");
      }
      startTransition(() => {
        setAuthSession(payload.data);
        setLoginError(null);
      });
      setNotice({
        tone: "success",
        message: payload.data.username ? `欢迎回来，${payload.data.username}。` : "登录成功。",
      });
      await refreshOverview({ includeSpeakers: true });
    } catch (error) {
      setLoginError(error instanceof Error ? error.message : "登录失败。");
    } finally {
      setIsLoggingIn(false);
    }
  });

  const handleLogout = useEffectEvent(async () => {
    setIsLoggingOut(true);
    try {
      await fetch("/auth/logout", {
        method: "POST",
        credentials: "same-origin",
      });
    } finally {
      startTransition(() => {
        setAuthSession((current) => ({
          enabled: current?.enabled ?? true,
          authenticated: false,
          username: null,
        }));
        setLoginError(null);
      });
      setNotice({
        tone: "info",
        message: "已退出登录。",
      });
      setIsLoggingOut(false);
    }
  });

  if (isAuthChecking || authSession === null) {
    return (
      <div className="relative z-10 min-h-screen px-4 py-4 md:px-6">
        <div className="mx-auto flex min-h-[calc(100vh-2rem)] max-w-[720px] items-center justify-center">
          <div className="glass-shell flex w-full max-w-[420px] items-center justify-center gap-3 px-6 py-6 text-slate-600">
            <LoaderCircle className="h-5 w-5 animate-spin" />
            正在检查登录状态
          </div>
        </div>
      </div>
    );
  }

  if (authEnabled && !isAuthenticated) {
    return <LoginPage busy={isLoggingIn} error={loginError} onSubmit={handleLogin} />;
  }

  return (
    <div className="relative z-10 min-h-screen px-4 py-4 md:px-6">
      <div className="mx-auto grid max-w-[1680px] gap-4 xl:grid-cols-[260px,minmax(0,1fr)]">
        <aside className="glass-shell flex h-full flex-col px-4 py-4 md:px-5 md:py-5 xl:sticky xl:top-4 xl:self-start xl:h-[calc(100vh-2rem)]">
          <div className="border-b border-white/55 pb-5">
            <div className="mt-3 flex items-center gap-3">
              <h1 className="font-display text-4xl font-bold tracking-tight text-ink">
                IndexTTS
                Studio
              </h1>
            </div>
            <div className="eyebrow text-2xl">配音控制台</div>
          </div>

          <nav className="mt-5 space-y-3 xl:flex-1">
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
                  {item.description ? (
                    <div
                      className={`mt-2 text-sm leading-7 ${active ? "text-white/75" : "text-slate-500"}`}
                    >
                      {item.description}
                    </div>
                  ) : null}
                </button>
              );
            })}
          </nav>

          <div className="mt-5 grid gap-2 border-t border-white/55 pt-5 xl:mt-auto">
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
          <div className="mt-3 rounded-[28px] border border-white/70 bg-slate-100/55 px-4 py-4 shadow-inner">
            <div className="eyebrow">服务状态</div>
            <div className="mt-3 flex items-center justify-between gap-3">
              <span className={statusClasses(health?.status ?? "offline")}>
                <HealthStatusIcon status={health?.status} />
                {displayStatus(health?.status ?? "offline")}
              </span>
              <button
                className="action-button action-button-ghost px-3 py-2 text-xs"
                disabled={isRefreshing}
                onClick={() => void refreshOverview({ includeSpeakers: true })}
                type="button"
              >
                {isRefreshing ? (
                  <LoaderCircle className="h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCcw className="h-4 w-4" />
                )}
                刷新
              </button>
            </div>
            {authEnabled && authSession.username ? (
              <div className="mt-3 flex items-center justify-between gap-3 border-t border-white/60 pt-3">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                  已登录：{authSession.username}
                </div>
                <button
                  className="action-button action-button-secondary px-3 py-2 text-xs"
                  disabled={isLoggingOut}
                  onClick={() => void handleLogout()}
                  type="button"
                >
                  {isLoggingOut ? (
                    <LoaderCircle className="h-4 w-4 animate-spin" />
                  ) : (
                    <LogOut className="h-4 w-4" />
                  )}
                  退出
                </button>
              </div>
            ) : null}
          </div>
        </aside>

        <div className="space-y-3">
          <header className="glass-shell px-4 py-4 md:px-6 md:py-5">
            <div className="flex flex-col gap-4 border-b border-white/55 pb-4 xl:flex-row xl:items-start xl:justify-between">
              <div className="max-w-3xl">
                <div className="mt-3 flex flex-wrap items-center gap-3">
                  <h2 className="font-display text-3xl font-semibold text-ink md:text-4xl">
                    {header.title}
                  </h2>
                </div>
                {header.description ? (
                  <p className="mt-2 max-w-2xl text-sm leading-7 text-slate-600 md:text-base">
                    {header.description}
                  </p>
                ) : null}
              </div>

              <div className="flex flex-wrap gap-3 xl:justify-end">
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

            <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr),280px,280px]">
              <div className="rounded-[28px] border border-white/70 bg-slate-100/55 px-4 py-3 shadow-inner">
                <div className="eyebrow">当前上下文</div>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-slate-600">
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
                onRefresh={() => loadSpeakersForProject(activeProject?.id ?? "")}
                project={activeProject}
                projects={projects}
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
