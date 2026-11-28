import { useMemo, useState } from "react";
import { api, type Application } from "../api";
import { TermView, TripleLine } from "./TermView";

type Props = {
  apps: Application[];
  loading: boolean;
  operations: string[];
  contains: string;
  setContains: (s: string) => void;
  containsError: string | null;
  onError: (e: unknown) => void;
};

const HIDDEN_BINDINGS = new Set(["cmd", "line", "text", "path"]);

export function ApplicationsPanel(p: Props) {
  const [text, setText] = useState("");
  const [op, setOp] = useState("");
  const [containsDraft, setContainsDraft] = useState(p.contains);
  const [showInvalid, setShowInvalid] = useState(true);

  const sorted = useMemo(() => {
    const q = text.trim().toLowerCase();
    return [...p.apps]
      .filter((a) => !op || a.operation === op)
      .filter((a) => showInvalid || a.valid)
      .filter(
        (a) =>
          !q ||
          a.operation.toLowerCase().includes(q) ||
          Object.values(a.bindings).some((b) => b.short.toLowerCase().includes(q)),
      )
      .sort((a, b) => Number(b.valid) - Number(a.valid) || b.total - a.total);
  }, [p.apps, text, op, showInvalid]);

  // Same rule as the engine (engine.choose): highest total, ties go to the first one
  // enumerated, and a no-op must strictly beat every application that changes something.
  const top = (xs: Application[]) =>
    xs.reduce<Application | null>((m, a) => (!m || a.total > m.total ? a : m), null);
  const act = top(p.apps.filter((a) => a.valid && !a.noop));
  const stop = top(p.apps.filter((a) => a.valid && a.noop));
  const best = stop && (!act || stop.total > act.total) ? stop : act;
  const maxAbs = Math.max(1, ...p.apps.flatMap((a) => Object.values(a.scores).map(Math.abs)));

  return (
    <section className="panel apps">
      <header className="panel-head">
        <h2>
          <span className="glyph">⚡</span> Applications
        </h2>
        <div className="stats">
          <span className="stat">{p.apps.filter((a) => a.valid).length} valid</span>
          {p.apps.some((a) => !a.valid) && (
            <span className="stat muted">{p.apps.filter((a) => !a.valid).length} blocked by SHACL</span>
          )}
          {p.loading && <span className="spinner" />}
        </div>
      </header>

      <div className="filters">
        <input placeholder="Search operation or binding…" value={text} onChange={(e) => setText(e.target.value)} />
        <select value={op} onChange={(e) => setOp(e.target.value)}>
          <option value="">all operations</option>
          {p.operations.map((o) => (
            <option key={o}>{o}</option>
          ))}
        </select>
        <form
          className="contains"
          onSubmit={(e) => {
            e.preventDefault();
            p.setContains(containsDraft);
          }}
        >
          <span className="contains-label">end state ∋</span>
          <input
            className={p.containsError ? "error" : ""}
            placeholder="?f ex:lineCount ?n"
            value={containsDraft}
            onChange={(e) => setContainsDraft(e.target.value)}
            title={p.containsError ?? "SPARQL pattern the resulting state must match"}
          />
        </form>
        <label className="check">
          <input type="checkbox" checked={showInvalid} onChange={(e) => setShowInvalid(e.target.checked)} /> blocked
        </label>
      </div>

      <div className="app-list">
        {sorted.length === 0 && (
          <div className="empty">
            {p.apps.length === 0 ? "Nothing applicable. The loop has come to rest. 🌙" : "No application matches the filters."}
          </div>
        )}
        {sorted.map((a) => {
          const bindings = Object.entries(a.bindings).filter(([k]) => !HIDDEN_BINDINGS.has(k));
          return (
            <article key={a.id} className={`app ${a.valid ? "" : "blocked"} ${best?.id === a.id ? "best" : ""}`}>
              <div className="app-head">
                <span className="op">{a.operation}</span>
                {a.noop && (
                  <span className="noop" title="changes nothing: if it wins, autopilot stops">
                    ■ stop
                  </span>
                )}
                {best?.id === a.id && <span className="pick">★ autopilot pick</span>}
                <span className="total">{a.valid ? fmt(a.total) : "—"}</span>
                <button className="btn small" disabled={!a.valid} onClick={() => api.apply(a.id).catch(p.onError)}>
                  {a.noop ? "Stop" : "Apply"}
                </button>
              </div>
              <div className="bindings">
                {bindings.map(([k, v]) => (
                  <span key={k} className="chip">
                    <span className="var">?{k}</span> <TermView term={v} />
                  </span>
                ))}
              </div>
              <div className="delta">
                {a.deletes.map((t) => (
                  <div key={"-" + t.key} className="del">
                    <span className="sign">−</span>
                    <TripleLine {...t} />
                  </div>
                ))}
                {a.inserts.map((t) => (
                  <div key={"+" + t.key} className="ins">
                    <span className="sign">+</span>
                    <TripleLine {...t} />
                  </div>
                ))}
              </div>
              {a.valid ? (
                <div className="scores">
                  {Object.entries(a.scores).map(([name, v]) => (
                    <div key={name} className="score-row">
                      <span className="cname">{name}</span>
                      <span className="bar">
                        <span
                          className={v < 0 ? "neg" : "pos"}
                          style={{ width: `${(Math.abs(v) / maxAbs) * 50}%`, [v < 0 ? "right" : "left"]: "50%" }}
                        />
                      </span>
                      <span className="val">{fmt(v)}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="violations">
                  {a.violations.map((v, i) => (
                    <div key={i}>
                      🛡 {v.focus} {v.path}: {v.message || v.component}
                    </div>
                  ))}
                </div>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}

const fmt = (n: number) => (n > 0 ? `+${n}` : `${n}`);
