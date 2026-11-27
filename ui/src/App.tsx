import { useCallback, useEffect, useRef, useState } from "react";
import { api, connectEvents, type Application, type Sheet, type State } from "./api";
import { ApplicationsPanel } from "./components/ApplicationsPanel";
import { ApprovalBanner } from "./components/ApprovalBanner";
import { SheetPanel } from "./components/SheetPanel";
import { Sidebar } from "./components/Sidebar";

const STATUS_LABEL = {
  idle: "manual",
  running: "autopilot",
  "awaiting-approval": "awaiting approval",
  done: "at rest",
} as const;

export function App() {
  const [state, setState] = useState<State | null>(null);
  const [sheet, setSheet] = useState<Sheet | null>(null);
  const [apps, setApps] = useState<Application[]>([]);
  const [appsLoading, setAppsLoading] = useState(false);
  const [contains, setContains] = useState("");
  const [containsError, setContainsError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [speed, setSpeed] = useState(400);
  const refreshTimer = useRef<number | undefined>(undefined);
  const [theme, setTheme] = useState<"light" | "dark">(
    () => (localStorage.getItem("lr-theme") as "light" | "dark" | null) ?? "light",
  );

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("lr-theme", theme);
  }, [theme]);

  const flash = useCallback((msg: string) => {
    setToast(msg);
    window.setTimeout(() => setToast(null), 4000);
  }, []);
  const onError = useCallback((e: unknown) => flash(e instanceof Error ? e.message : String(e)), [flash]);

  const refresh = useCallback(async () => {
    try {
      const [st, sh] = await Promise.all([api.state(), api.sheet()]);
      setState(st);
      setSheet(sh);
      setAppsLoading(true);
      try {
        const r = await api.applications(contains || undefined);
        setApps(r.applications);
        setContainsError(null);
      } catch (e) {
        setContainsError(e instanceof Error ? e.message : String(e));
      } finally {
        setAppsLoading(false);
      }
    } catch (e) {
      onError(e);
    }
  }, [contains, onError]);

  useEffect(() => {
    refresh();
    return connectEvents(() => {
      window.clearTimeout(refreshTimer.current);
      refreshTimer.current = window.setTimeout(refresh, 60);
    });
  }, [refresh]);

  const status = state?.autopilot ?? "idle";
  const running = status === "running" || status === "awaiting-approval";
  const pending = state?.pending ?? [];

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="logo">⟳</span>
          <span className="name">
            Looping<b>Rules</b>
          </span>
          <span className="tagline">semantic spreadsheet</span>
        </div>
        <span className="project" title={`${state?.journal ?? 0} changes journaled in .lr/`}>
          ▸ {state?.project ?? "…"}
          {state?.package && <span className="pkg"> · {state.package.title} {state.package.version}</span>}
        </span>
        <div className="counters">
          <span>
            tick <b>{state?.tick ?? 0}</b>
          </span>
          <span>
            v<b>{state?.version ?? 0}</b>
          </span>
        </div>
        <span className={`status status-${status}`}>
          <span className="dot" /> {STATUS_LABEL[status]}
        </span>
        <div className="controls">
          <button className="btn" disabled={running} onClick={() => api.step().catch(onError)} title="One autopilot tick">
            ⏭ Step
          </button>
          {running ? (
            <button className="btn danger" onClick={() => api.stop().catch(onError)}>
              ■ Stop
            </button>
          ) : (
            <button className="btn primary" onClick={() => api.start(speed).catch(onError)}>
              ▶ Autopilot
            </button>
          )}
          <label className="speed" title="Delay between ticks">
            <input type="range" min={0} max={1500} step={50} value={speed} onChange={(e) => setSpeed(+e.target.value)} />
            <span>{speed} ms</span>
          </label>
          <button
            className="btn ghost"
            disabled={!state?.undo || running}
            onClick={() => api.undo().catch(onError)}
            title={state?.undo ? `Undo ${state.undo}` : "Nothing to undo"}
          >
            ↶ Undo
          </button>
          <details className="menu">
            <summary className="btn ghost" title="Download a shareable .lr.zip">
              ⇩ Export
            </summary>
            <div className="menu-list">
              <a href={api.exportUrl("seed")} download>
                Model + controllers + example sheet
                <span>what you authored: the usual way to share</span>
              </a>
              <a href={api.exportUrl("state")} download>
                Model + controllers + current state
                <span>share where you are right now</span>
              </a>
              <a href={api.exportUrl("none")} download>
                Model + controllers only
                <span>no data at all</span>
              </a>
            </div>
          </details>
          <button
            className="btn ghost theme"
            onClick={() => setTheme(theme === "light" ? "dark" : "light")}
            title={theme === "light" ? "Switch to dark theme" : "Switch to light theme"}
          >
            {theme === "light" ? "☾" : "☀"}
          </button>
        </div>
      </header>

      {pending.length > 0 && (
        <div className="approvals">
          {pending.map((c) => (
            <ApprovalBanner key={c.id} call={c} onError={onError} />
          ))}
        </div>
      )}

      <main className="layout">
        <SheetPanel sheet={sheet} onError={onError} />
        <ApplicationsPanel
          apps={apps}
          loading={appsLoading}
          operations={state?.operations ?? []}
          contains={contains}
          setContains={setContains}
          containsError={containsError}
          onError={onError}
        />
        <Sidebar controllers={state?.controllers ?? []} trust={state?.trust ?? []} log={state?.log ?? []} onError={onError} />
      </main>

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}
