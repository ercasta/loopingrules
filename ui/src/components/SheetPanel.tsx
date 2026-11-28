import { useEffect, useMemo, useRef, useState } from "react";
import { api, type ObjectConstraint, type Sheet, type Suggestion } from "../api";
import { Combobox } from "./Combobox";
import { TermView } from "./TermView";

type Props = {
  sheet: Sheet | null;
  onError: (e: unknown) => void;
  /** app mode (D25): the model turned direct edits off */
  appMode?: boolean;
  /** the user unlocked editing for this session, despite app mode */
  unlocked?: boolean;
  onUnlock?: (unlocked: boolean) => void;
};

export function SheetPanel({ sheet, onError, appMode = false, unlocked = false, onUnlock }: Props) {
  const locked = appMode && !unlocked;
  const [query, setQuery] = useState("");
  const [draft, setDraft] = useState({ s: "", p: "", o: "" });
  const wrapRef = useRef<HTMLDivElement>(null);

  // Bring the rows changed by the last tick into view.
  useEffect(() => {
    wrapRef.current?.querySelector("tr.changed")?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [sheet?.version]);

  const violationsBySubject = useMemo(() => {
    const m = new Map<string, string[]>();
    for (const v of sheet?.violations ?? []) {
      if (!v.focus) continue;
      m.set(v.focus, [...(m.get(v.focus) ?? []), v.message || `${v.path}: ${v.component}`]);
    }
    return m;
  }, [sheet]);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const all = sheet?.triples ?? [];
    return q ? all.filter((t) => `${t.s.short} ${t.p.short} ${t.o.short}`.toLowerCase().includes(q)) : all;
  }, [sheet, query]);

  // --- SHACL-driven editing (D15) -------------------------------------
  const pRef = useRef<HTMLInputElement>(null);
  const oRef = useRef<HTMLInputElement>(null);
  const [missing, setMissing] = useState<Suggestion[]>([]);
  const [objInfo, setObjInfo] = useState<{ constraint: ObjectConstraint; hint: string | null } | null>(null);

  useEffect(() => {
    if (!draft.s.trim()) return setMissing([]);
    const t = window.setTimeout(() => {
      api.suggest("p", draft.s, "", "").then((r) => setMissing(r.missing), () => setMissing([]));
    }, 150);
    return () => window.clearTimeout(t);
  }, [draft.s, sheet?.version]);

  useEffect(() => {
    if (!draft.p.trim()) return setObjInfo(null);
    const t = window.setTimeout(() => {
      api.suggest("o", draft.s, draft.p, "").then((r) => setObjInfo(r), () => setObjInfo(null));
    }, 150);
    return () => window.clearTimeout(t);
  }, [draft.s, draft.p, sheet?.version]);

  const objectProblem = checkObject(draft.o, objInfo?.constraint);

  const add = async () => {
    try {
      await api.addTriple(draft.s, draft.p, draft.o, appMode);
      setDraft({ s: draft.s, p: "", o: "" });
      pRef.current?.focus();
    } catch (e) {
      onError(e);
    }
  };

  const editSubject = (s: string) => {
    setDraft({ s, p: "", o: "" });
    pRef.current?.focus();
  };

  let group = 0;
  let prevSubject = "";
  const changedCount = sheet?.triples.filter((t) => t.changed).length ?? 0;

  return (
    <section className="panel sheet">
      <header className="panel-head">
        <h2>
          <span className="glyph">▦</span> Sheet
        </h2>
        <div className="stats">
          <span className="stat">{sheet?.triples.length ?? 0} triples</span>
          {changedCount > 0 && <span className="stat good">+{changedCount} last tick</span>}
          {sheet && sheet.violations.length > 0 ? (
            <span className="stat bad">⚠ {sheet.violations.length} violations</span>
          ) : (
            <span className="stat good">✓ valid</span>
          )}
        </div>
        <input
          className="search"
          placeholder="Filter triples…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </header>

      <div className="grid-wrap" ref={wrapRef}>
        <table className="grid">
          <thead>
            <tr>
              <th className="rownum">#</th>
              <th>subject</th>
              <th>predicate</th>
              <th>object</th>
              <th className="act" />
            </tr>
          </thead>
          <tbody>
            {rows.map((t, i) => {
              const first = t.s.short !== prevSubject;
              if (first) group++;
              prevSubject = t.s.short;
              const problems = violationsBySubject.get(t.s.short);
              return (
                <tr
                  key={t.key}
                  className={[
                    group % 2 ? "odd" : "even",
                    first ? "first" : "",
                    t.changed ? "changed" : "",
                    problems ? "invalid" : "",
                  ].join(" ")}
                >
                  <td className="rownum">{i + 1}</td>
                  <td className="subj" title={problems?.join("\n") ?? "click to add a property"} onClick={() => !locked && editSubject(t.s.short === "a" ? "" : t.s.short)}>
                    {first && (
                      <>
                        <TermView term={t.s} />
                        {problems && <span className="warn">⚠</span>}
                      </>
                    )}
                  </td>
                  <td>
                    <TermView term={t.p} />
                  </td>
                  <td>
                    <TermView term={t.o} />
                    {t.changed && <span className="new-tag">new</span>}
                  </td>
                  <td className="act">
                    {!locked && (
                      <button className="icon" title="Delete triple" onClick={() => api.deleteTriple(t, appMode).catch(onError)}>
                        ×
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {appMode && (
        <div className={`app-mode ${locked ? "" : "unlocked"}`}>
          {locked ? (
            <span>
              <b>App mode:</b> this model takes input as messages. Send them in the Messages panel.
            </span>
          ) : (
            <span>
              <b>Editing unlocked:</b> direct edits bypass the model's commands.
            </span>
          )}
          <button
            className="btn ghost small"
            onClick={() => {
              if (locked && !window.confirm("Edit the sheet directly? This model expects input as messages; direct edits can leave it in a state its operations don't expect.")) return;
              onUnlock?.(locked);
            }}
          >
            {locked ? "Unlock editing" : "Lock again"}
          </button>
        </div>
      )}

      <div className="add-zone" hidden={locked}>
        {missing.length > 0 && (
          <div className="assist missing">
            <span className="label">
              <TermLike text={draft.s} /> still needs
            </span>
            {missing.map((m) => (
              <button
                key={m.value}
                className="need"
                title={m.hint}
                onClick={() => {
                  setDraft({ ...draft, p: m.value, o: "" });
                  oRef.current?.focus();
                }}
              >
                + {m.value}
              </button>
            ))}
          </div>
        )}
        {objInfo && describe(objInfo.constraint, objInfo.hint) && (
          <div className={`assist expect ${objInfo.constraint.full ? "warn" : ""}`}>
            <span className="label">{draft.p} expects</span> {describe(objInfo.constraint, objInfo.hint)}
          </div>
        )}
        <form
          className="add-row"
          onSubmit={(e) => {
            e.preventDefault();
            add();
          }}
        >
          <Combobox
            value={draft.s}
            onChange={(v) => setDraft((d) => ({ ...d, s: v }))}
            load={(q) => api.suggest("s", "", "", q).then((r) => r.items)}
            contextKey=""
            placeholder="subject  ex:thing"
            onPicked={() => pRef.current?.focus()}
          />
          <Combobox
            ref={pRef}
            value={draft.p}
            onChange={(v) => setDraft((d) => ({ ...d, p: v }))}
            load={(q) => api.suggest("p", draft.s, "", q).then((r) => r.items)}
            contextKey={draft.s}
            placeholder="predicate  a"
            onPicked={() => oRef.current?.focus()}
          />
          <Combobox
            ref={oRef}
            value={draft.o}
            onChange={(v) => setDraft((d) => ({ ...d, o: v }))}
            load={(q) => (draft.p ? api.suggest("o", draft.s, draft.p, q).then((r) => r.items) : Promise.resolve([]))}
            contextKey={draft.s + "|" + draft.p}
            placeholder={'object  "text" · 42 · ex:Class'}
            invalid={objectProblem}
          />
          <button className="btn primary" disabled={!draft.s || !draft.p || !draft.o}>
            + Add
          </button>
        </form>
        {objectProblem && <div className="assist problem">⚠ {objectProblem}</div>}
      </div>
    </section>
  );
}

function TermLike({ text }: { text: string }) {
  return <code className="termlike">{text}</code>;
}

/** One-line summary of what the object should look like, from the shape. */
function describe(c: ObjectConstraint, hint: string | null): string {
  const parts: string[] = [];
  if (c.kind === "enum") parts.push("one of the listed values");
  if (c.class) parts.push(`an instance of ${c.class}`);
  if (c.datatype) parts.push(`a literal of ${c.datatype}`);
  if (c.pattern) parts.push(`matching /${c.pattern}/`);
  if (hint) parts.push(`(${hint})`);
  if (c.full) parts.push(`— ${c.full}`);
  return parts.join(" ");
}

/** Client-side check of the typed object against the shape, before sending. */
function checkObject(o: string, c?: ObjectConstraint): string | null {
  const v = o.trim();
  if (!v || !c) return null;
  const quoted = v.startsWith('"');
  if (c.datatype === "xsd:integer" && !/^[+-]?\d+$/.test(v)) return "expects an integer, e.g. 42";
  if (c.datatype === "xsd:boolean" && !/^(true|false)$/.test(v)) return "expects true or false";
  if ((c.kind === "iri" || c.class) && quoted) return `expects a resource${c.class ? ` (${c.class})` : ""}, not a string`;
  if (c.pattern && quoted) {
    try {
      const text = JSON.parse(v) as string;
      if (!new RegExp(c.pattern).test(text)) return `does not match /${c.pattern}/`;
    } catch {
      return null;
    }
  }
  return null;
}
