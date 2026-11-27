import { api, type Controller, type LogEntry, type TrustRule } from "../api";

type Props = { controllers: Controller[]; trust: TrustRule[]; log: LogEntry[]; onError: (e: unknown) => void };

export function Sidebar({ controllers, trust, log, onError }: Props) {
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
              <div className="cname">
                {c.name}
                {c.layer && (
                  <span className="layer" title={`from the ${c.layer} controller pack (layers/${c.layer}/)`}>
                    ⧉ {c.layer}
                  </span>
                )}
              </div>
              <code className="query">{c.query.replace(/\s+/g, " ")}</code>
            </div>
          </div>
        ))}
      </div>

      <header className="panel-head">
        <h2>
          <span className="glyph">★</span> Trusted commands
        </h2>
      </header>
      <div className="trust">
        {trust.length === 0 && <div className="trust-empty">Every tool call asks first.</div>}
        {trust.map((r) => (
          <div key={r.id} className="trust-rule">
            <code>{r.template}</code>
            <button className="icon" title="Stop trusting" onClick={() => api.untrust(r.id).catch(onError)}>
              ×
            </button>
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
              {e.kind === "tick" ? (e.manual ? "✋" : "⟳") : e.kind === "tool" ? (e.approved ? "⚙" : "⊘") : e.kind === "edit" ? "✎" : e.kind === "undo" ? "↶" : "■"}
            </span>
            <span className="text">
              {e.kind === "tool" ? <code>{e.text}</code> : e.text}
              {e.rule && <span className="trusted">trusted</span>}
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
