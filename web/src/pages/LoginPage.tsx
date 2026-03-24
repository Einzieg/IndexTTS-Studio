import {
  ArrowRight,
  Layers3,
  LoaderCircle,
  LockKeyhole,
  ShieldCheck,
  Sparkles,
  UserRound,
} from "lucide-react";
import { FormEvent, useState } from "react";

type LoginPageProps = {
  busy: boolean;
  error?: string | null;
  onSubmit: (username: string, password: string) => Promise<void>;
};

export function LoginPage(props: LoginPageProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await props.onSubmit(username.trim(), password);
  }

  return (
    <div className="relative z-10 min-h-screen px-4 py-4 md:px-6">
      <div className="mx-auto grid min-h-[calc(100vh-2rem)] max-w-[1680px] gap-4 lg:grid-cols-[minmax(0,1.14fr),420px]">
        <section className="glass-shell relative flex min-h-[460px] items-center overflow-hidden px-7 py-9 md:px-12 md:py-12 lg:min-h-full lg:px-14">

          <div className="relative max-w-2xl">
            <div className="eyebrow">协作配音工作台</div>
            <h1 className="mt-5 font-display text-5xl font-bold tracking-tight text-ink md:text-7xl">
              IndexTTS
              <span className="block text-[#2563eb]">Studio</span>
            </h1>
            <p className="mt-5 max-w-xl text-base leading-8 text-slate-600 md:text-lg">
              用统一的工作台管理项目、角色、分集台词和批量生成任务，把配音流程收进同一套轻量界面。
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <div className="inline-flex items-center gap-2 rounded-full border border-white/70 bg-white/72 px-4 py-2 text-sm font-semibold text-slate-600">
                <Sparkles className="h-4 w-4 text-slate-500" />
                项目化管理
              </div>
              <div className="inline-flex items-center gap-2 rounded-full border border-white/70 bg-white/72 px-4 py-2 text-sm font-semibold text-slate-600">
                <Layers3 className="h-4 w-4 text-slate-500" />
                批量任务追踪
              </div>
              <div className="inline-flex items-center gap-2 rounded-full border border-white/70 bg-white/72 px-4 py-2 text-sm font-semibold text-slate-600">
                <ShieldCheck className="h-4 w-4 text-slate-500" />
                登录后进入工作台
              </div>
            </div>

            <div className="mt-8 grid max-w-[42rem] gap-3 md:grid-cols-3">
              <div className="glass-card px-4 py-4">
                <div className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">
                  项目
                </div>
                <div className="mt-3 text-lg font-semibold text-slate-800">项目与分集隔离管理</div>
                <div className="mt-2 text-sm leading-7 text-slate-500">同一工作台中切换项目、分集和配置。</div>
              </div>
              <div className="glass-card px-4 py-4">
                <div className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">
                  角色
                </div>
                <div className="mt-3 text-lg font-semibold text-slate-800">角色配置与音频版本</div>
                <div className="mt-2 text-sm leading-7 text-slate-500">集中管理参考音频、参数和试听结果。</div>
              </div>
              <div className="glass-card px-4 py-4">
                <div className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">
                  任务
                </div>
                <div className="mt-3 text-lg font-semibold text-slate-800">批量生成与结果回填</div>
                <div className="mt-2 text-sm leading-7 text-slate-500">生成后直接回到表格工作流继续调整。</div>
              </div>
            </div>
          </div>
        </section>

        <section className="glass-shell flex items-center px-4 py-4 md:px-5 md:py-5 lg:min-h-full">
          <div className="w-full">
            <div className="glass-card px-5 py-6 md:px-6 md:py-7">
              <div className="eyebrow">安全登录</div>
              <h2 className="mt-3 font-display text-3xl font-semibold text-ink">进入工作台</h2>

              {props.error ? (
                <div className="mt-5 rounded-[24px] border border-rose-100 bg-rose-50/90 px-4 py-3 text-sm font-medium text-rose-700">
                  {props.error}
                </div>
              ) : null}

              <form className="mt-6 space-y-4" onSubmit={(event) => void handleSubmit(event)}>
                <label className="block">
                  <span className="mb-2 block text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">
                    账号
                  </span>
                  <div className="field-shell flex items-center gap-3">
                    <UserRound className="h-4 w-4 text-slate-400" />
                    <input
                      autoComplete="username"
                      className="w-full border-0 bg-transparent p-0 outline-none"
                      disabled={props.busy}
                      onChange={(event) => setUsername(event.target.value)}
                      placeholder="请输入账号"
                      value={username}
                    />
                  </div>
                </label>

                <label className="block">
                  <span className="mb-2 block text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">
                    密码
                  </span>
                  <div className="field-shell flex items-center gap-3">
                    <LockKeyhole className="h-4 w-4 text-slate-400" />
                    <input
                      autoComplete="current-password"
                      className="w-full border-0 bg-transparent p-0 outline-none"
                      disabled={props.busy}
                      onChange={(event) => setPassword(event.target.value)}
                      placeholder="请输入密码"
                      type="password"
                      value={password}
                    />
                  </div>
                </label>

                <button
                  className="action-button action-button-primary mt-2 w-full justify-center"
                  disabled={props.busy || username.trim().length === 0 || password.length === 0}
                  type="submit"
                >
                  {props.busy ? (
                    <LoaderCircle className="h-4 w-4 animate-spin" />
                  ) : (
                    <ArrowRight className="h-4 w-4" />
                  )}
                  进入工作台
                </button>
              </form>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
