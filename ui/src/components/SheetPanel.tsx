import { useEffect, useMemo, useRef, useState } from "react";
import { api, type Sheet, type Triple } from "../api";
import { TermView } from "./TermView";

type Props = { sheet: Sheet | null; onError: (e: unknown) => void };

export function SheetPanel({ sheet, onError }: Props) {
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

  // Suggestions for the add-row: every term already in the sheet.
  const suggestions = useMemo(() => {
    const pick = (f: (t: Triple) => string) => [...new Set((sheet?.triples ?? []).map(f))].sort();
    return { s: pick((t) => t.s.short), p: pick((t) => t.p.short), o: pick((t) => t.o.short) };
  }, [sheet]);

  const add = async () => {
    try {
      await api.addTriple(draft.s, draft.p, draft.o);
      setDraft({ s: draft.s, p: "", o: "" });
    } catch (e) {
      onError(e);
    }
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
                  <td className="subj" title={problems?.join("\n")}>
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
                    <button className="icon" title="Delete triple" onClick={() => api.deleteTriple(t).catch(onError)}>
                      ×
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <form
        className="add-row"
        onSubmit={(e) => {
          e.preventDefault();
          add();
        }}
      >
        {(["s", "p", "o"] as const).map((k) => (
          <span key={k} className="add-cell">
            <input
              list={`sugg-${k}`}
              placeholder={{ s: "subject  ex:thing", p: "predicate  a", o: 'object  "text" · 42 · ex:Class' }[k]}
              value={draft[k]}
              onChange={(e) => setDraft({ ...draft, [k]: e.target.value })}
            />
            <datalist id={`sugg-${k}`}>
              {suggestions[k].map((x) => (
                <option key={x} value={x} />
              ))}
            </datalist>
          </span>
        ))}
        <button className="btn primary" disabled={!draft.s || !draft.p || !draft.o}>
          + Add
        </button>
      </form>
    </section>
  );
}
