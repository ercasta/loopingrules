import { api, type Controller, type LogEntry } from "../api";

type Props = { controllers: Controller[]; log: LogEntry[]; onError: (e: unknown) => void };

export function Sidebar({ controllers, log, onError }: Props) {
  return (
    <aside className="panel side">
      <header className="panel-head">
        <h2>
          <span className="glyph">◎</span> Controllers
        </h2>
      </header>
      <div className="controllers">
        {controllers.map((c) => (
          <div key={c.name} className={`controller ${c.active ? "on" : "off"}`}>
            <button className="switch" onClick={() => api.toggleController(c.name).catch(onError)} title="toggle">
              <span />
            </button>
            <div>
              <div className="cname">{c.name}</div>
              <code className="query">{c.query.replace(/\s+/g, " ")}</code>
            </div>
          </div>
        ))}
      </div>

      <header className="panel-head">
        <h2>
          <span className="glyph">≋</span> Activity
        </h2>
      </header>
      <ol className="log">
        {[...log].reverse().map((e) => (
          <li key={e.n} className={`log-${e.kind} ${e.approved === false ? "rejected" : ""}`}>
            <span className="tick">{e.kind === "tick" ? `#${e.tick}` : ""}</span>
            <span className="icon">
              {e.kind === "tick" ? (e.manual ? "✋" : "⟳") : e.kind === "tool" ? (e.approved ? "⚙" : "⊘") : e.kind === "edit" ? "✎" : "■"}
            </span>
            <span className="text">
              {e.kind === "tool" ? <code>{e.text}</code> : e.text}
              {e.bindings && (
                <span className="lb">
                  {Object.entries(e.bindings)
                    .filter(([k]) => !["cmd", "line", "text", "path", "call"].includes(k))
                    .map(([k, v]) => `?${k}=${v}`)
                    .join(" ")}
                </span>
              )}
            </span>
            {e.score !== undefined && <span className="sc">{e.score > 0 ? `+${e.score}` : e.score}</span>}
          </li>
        ))}
        {log.length === 0 && <li className="empty">No activity yet. Apply an operation or start autopilot.</li>}
      </ol>
    </aside>
  );
}
