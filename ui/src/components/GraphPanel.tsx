import cytoscape, { type Core, type ElementDefinition, type StylesheetJson } from "cytoscape";
import { useEffect, useMemo, useRef, useState } from "react";
import type { Sheet, Term, Triple } from "../api";
import { TermView } from "./TermView";

/** The sheet as a graph (design D27). Loaded lazily: the sheet view doesn't pay for Cytoscape. */

const RDF_TYPE = "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>";
const LR_CHANNEL = "<https://loopingrules.org/ns#channel>";
const PALETTE = ["#6a5af9", "#0ea5b7", "#e8590c", "#2f9e44", "#d6336c", "#1c7ed6", "#ae3ec9", "#f59f00"];

type LinkMode = "edges" | "chips";

type NodeInfo = {
  id: string;
  term: Term;
  types: string[];
  literals: [string, string][];
  links: Triple[]; // outgoing triples whose object is a resource
  incoming: Triple[];
  subject: boolean; // has statements of its own (otherwise it's only ever an object)
  changed: boolean;
  invalid: boolean;
  message: boolean;
  prefix: string;
};

type Model = { nodes: Map<string, NodeInfo>; links: Triple[] };

function prefixOf(short: string): string {
  if (short.startsWith("<") || short.startsWith("_:")) return "";
  const i = short.indexOf(":");
  return i > 0 ? short.slice(0, i) : "";
}

function build(sheet: Sheet): Model {
  const nodes = new Map<string, NodeInfo>();
  const invalid = new Set(sheet.violations.map((v) => v.focus));
  const node = (t: Term) => {
    let n = nodes.get(t.n3);
    if (!n) {
      n = {
        id: t.n3, term: t, types: [], literals: [], links: [], incoming: [], subject: false,
        changed: false, invalid: invalid.has(t.short), message: false, prefix: prefixOf(t.short),
      };
      nodes.set(t.n3, n);
    }
    return n;
  };
  const links: Triple[] = [];
  for (const t of sheet.triples) {
    const s = node(t.s);
    s.subject = true;
    if (t.changed) s.changed = true;
    if (t.p.n3 === LR_CHANNEL) s.message = true;
    if (t.p.n3 === RDF_TYPE && t.o.kind !== "literal") s.types.push(t.o.short);
    else if (t.o.kind === "literal") s.literals.push([t.p.short, t.o.value ?? t.o.short]);
    else {
      s.links.push(t);
      node(t.o).incoming.push(t);
      links.push(t);
    }
  }
  // A class only used as a type is a badge, not a node.
  for (const [id, n] of nodes) if (!n.subject && n.incoming.length === 0) nodes.delete(id);
  return { nodes, links };
}

function colorOf(type: string | undefined): string {
  if (!type) return "#8c94aa";
  let h = 0;
  for (const c of type) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return PALETTE[h % PALETTE.length];
}

const clip = (s: string, n = 42) => (s.length > n ? s.slice(0, n - 1) + "…" : s).replace(/\s+/g, " ");

/** How a node is named: a minted node's name says nothing, so show its first value instead
 *  (e.g. a line of shell output). */
function nameOf(n: NodeInfo | undefined, fallback: Term): string {
  if (!n || n.term.kind !== "bnode") return fallback.short;
  const value = n.literals.find(([p]) => /(text|name|label|title)$/i.test(p)) ?? n.literals[0];
  return value ? `“${clip(value[1], 30)}”` : fallback.short;
}

function label(n: NodeInfo, nodes: Map<string, NodeInfo>, expanded: boolean, mode: LinkMode): string {
  const head = nameOf(n, n.term) + (n.types.length ? `\n${n.types.join(", ")}` : "");
  if (!expanded) return head;
  const lines = n.literals.map(([p, v]) => `${p}  ${clip(v)}`);
  if (mode === "chips") lines.push(...n.links.map((t) => `${t.p.short} → ${nameOf(nodes.get(t.o.n3), t.o)}`));
  return lines.length ? `${head}\n─────\n${lines.join("\n")}` : head;
}

function css(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#888";
}

function stylesheet(): StylesheetJson {
  return [
    {
      selector: "node",
      style: {
        label: "data(label)", "text-wrap": "wrap", "text-max-width": "320px", "text-justification": "left",
        "text-valign": "center", "text-halign": "center", shape: "round-rectangle",
        width: "label", height: "label", padding: "10px",
        "background-color": css("--panel-2"), "background-opacity": 1,
        "border-width": 1.5, "border-color": "data(color)",
        color: css("--text"), "font-size": 11, "font-family": "JetBrains Mono, Consolas, monospace",
      },
    },
    { selector: "node.typed", style: { "border-width": 2.5 } },
    { selector: "node.object", style: { "border-style": "dashed", "font-size": 10, color: css("--muted") } },
    { selector: "node.changed", style: { "background-color": css("--good-bg"), "border-color": css("--good") } },
    { selector: "node.invalid", style: { "border-color": css("--bad"), "border-width": 3 } },
    { selector: "node:selected", style: { "border-color": css("--accent"), "border-width": 3.5 } },
    {
      selector: "edge",
      style: {
        "curve-style": "bezier", "target-arrow-shape": "triangle", width: 1.3,
        "line-color": css("--line-2"), "target-arrow-color": css("--line-2"),
        label: "data(label)", "font-size": 9, color: css("--muted"), "text-rotation": "autorotate",
        "text-background-color": css("--bg"), "text-background-opacity": 1, "text-background-padding": "2px",
        "font-family": "JetBrains Mono, Consolas, monospace",
      },
    },
    { selector: "edge.changed", style: { "line-color": css("--good"), "target-arrow-color": css("--good"), width: 2 } },
    { selector: ".dim", style: { opacity: 0.18 } },
  ];
}

type Props = {
  sheet: Sheet | null;
  theme: string;
  onShowInSheet: (subject: string) => void;
};

export default function GraphPanel({ sheet, theme, onShowInSheet }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [mode, setMode] = useState<LinkMode>("edges");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [allExpanded, setAllExpanded] = useState(false);
  const [search, setSearch] = useState("");
  const [showMessages, setShowMessages] = useState(false);
  const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(new Set());
  const [hiddenPrefixes, setHiddenPrefixes] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<string | null>(null);
  const [hops, setHops] = useState(0);

  const model = useMemo<Model>(() => (sheet ? build(sheet) : { nodes: new Map(), links: [] }), [sheet]);

  const allTypes = useMemo(() => [...new Set([...model.nodes.values()].flatMap((n) => n.types))].sort(), [model]);
  const allPrefixes = useMemo(
    () => [...new Set([...model.nodes.values()].map((n) => n.prefix).filter(Boolean))].sort(),
    [model],
  );

  // What is shown: filters, then the focus neighbourhood.
  const visible = useMemo(() => {
    const ok = new Set<string>();
    for (const n of model.nodes.values()) {
      if (n.message && !showMessages) continue;
      if (n.types.some((t) => hiddenTypes.has(t))) continue;
      if (n.prefix && hiddenPrefixes.has(n.prefix)) continue;
      ok.add(n.id);
    }
    let links = model.links.filter((t) => ok.has(t.s.n3) && ok.has(t.o.n3));
    // An object-only node with no visible link left is noise.
    const linked = new Set(links.flatMap((t) => [t.s.n3, t.o.n3]));
    for (const id of [...ok]) if (!model.nodes.get(id)!.subject && !linked.has(id)) ok.delete(id);
    if (hops > 0 && selected && ok.has(selected)) {
      const near = new Set([selected]);
      let frontier = [selected];
      for (let i = 0; i < hops; i++) {
        const next: string[] = [];
        for (const t of links) {
          for (const [a, b] of [[t.s.n3, t.o.n3], [t.o.n3, t.s.n3]]) {
            if (frontier.includes(a) && !near.has(b)) {
              near.add(b);
              next.push(b);
            }
          }
        }
        frontier = next;
      }
      for (const id of [...ok]) if (!near.has(id)) ok.delete(id);
      links = links.filter((t) => ok.has(t.s.n3) && ok.has(t.o.n3));
    }
    return { nodes: ok, links };
  }, [model, showMessages, hiddenTypes, hiddenPrefixes, hops, selected]);

  // Create Cytoscape once.
  useEffect(() => {
    const cy = cytoscape({ container: box.current, style: stylesheet(), wheelSensitivity: 0.3, minZoom: 0.1, maxZoom: 3 });
    cy.on("tap", "node", (e) => setSelected(e.target.id()));
    cy.on("tap", (e) => {
      if (e.target === cy) setSelected(null);
    });
    cy.on("dbltap", "node", (e) => {
      const id = e.target.id();
      setExpanded((s) => {
        const n = new Set(s);
        if (n.has(id)) n.delete(id);
        else n.add(id);
        return n;
      });
    });
    cyRef.current = cy;
    (window as unknown as { __lrGraph?: Core }).__lrGraph = cy; // for scripts/dev (screenshots)
    return () => cy.destroy();
  }, []);

  useEffect(() => {
    cyRef.current?.style(stylesheet());
  }, [theme]);

  // Sync the elements, keeping the positions of nodes that stay.
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    const wasEmpty = cy.nodes().length === 0;
    const els: ElementDefinition[] = [];
    for (const id of visible.nodes) {
      const n = model.nodes.get(id)!;
      const classes = [
        n.subject ? "" : "object", n.types.length ? "typed" : "", n.changed ? "changed" : "", n.invalid ? "invalid" : "",
      ].join(" ");
      els.push({
        group: "nodes",
        data: { id, label: label(n, model.nodes, allExpanded || expanded.has(id), mode), color: colorOf(n.types[0]) },
        classes,
      });
    }
    if (mode === "edges") {
      for (const t of visible.links) {
        els.push({ group: "edges", data: { id: t.key, source: t.s.n3, target: t.o.n3, label: t.p.short }, classes: t.changed ? "changed" : "" });
      }
    }
    const wanted = new Set(els.map((e) => e.data.id!));
    let added = 0;
    cy.batch(() => {
      cy.elements().forEach((el) => {
        if (!wanted.has(el.id())) el.remove();
      });
      for (const e of els) {
        const existing = cy.getElementById(e.data.id!);
        if (existing.nonempty()) {
          existing.data(e.data);
          existing.classes(e.classes as string);
          continue;
        }
        if (e.group === "nodes") {
          added++;
          // Place a new node next to a neighbour that already has a position.
          const nb = visible.links
            .filter((t) => t.s.n3 === e.data.id || t.o.n3 === e.data.id)
            .map((t) => cy.getElementById(t.s.n3 === e.data.id ? t.o.n3 : t.s.n3))
            .find((x) => x.nonempty());
          const base = nb ? nb.position() : { x: cy.width() / 2, y: cy.height() / 2 };
          cy.add({ ...e, position: { x: base.x + (Math.random() - 0.5) * 160, y: base.y + 80 + Math.random() * 60 } });
        }
      }
      for (const e of els) if (e.group === "edges" && cy.getElementById(e.data.id!).empty()) cy.add(e);
    });
    if (wasEmpty && added > 0) relayout(cy);
  }, [visible, model, mode, expanded, allExpanded]);

  // Search dims what doesn't match.
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    const q = search.trim().toLowerCase();
    cy.batch(() => {
      cy.elements().removeClass("dim");
      if (!q) return;
      cy.nodes().forEach((n) => {
        if (!String(n.data("label")).toLowerCase().includes(q)) n.addClass("dim");
      });
      cy.edges().forEach((e) => {
        if (e.source().hasClass("dim") && e.target().hasClass("dim")) e.addClass("dim");
      });
    });
  }, [search, visible, mode, expanded, allExpanded]);

  // Keep Cytoscape's selection in step with ours.
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.nodes(":selected").unselect();
    if (selected) cy.getElementById(selected).select();
  }, [selected, visible]);

  const goTo = (id: string) => {
    setSelected(id);
    const cy = cyRef.current;
    const n = cy?.getElementById(id);
    if (cy && n && n.nonempty()) cy.animate({ center: { eles: n }, zoom: Math.max(cy.zoom(), 1) }, { duration: 300 });
  };

  const toggle = (set: Set<string>, value: string, update: (s: Set<string>) => void) => {
    const n = new Set(set);
    if (n.has(value)) n.delete(value);
    else n.add(value);
    update(n);
  };

  const sel = selected ? model.nodes.get(selected) : undefined;

  return (
    <section className="panel graph">
      <header className="panel-head graph-head">
        <h2>
          <span className="glyph">◈</span> Graph
        </h2>
        <span className="stat">
          {visible.nodes.size} nodes · {visible.links.length} links
        </span>
        <div className="seg" title="How links between resources are shown">
          <button className={mode === "edges" ? "on" : ""} onClick={() => setMode("edges")}>
            edges
          </button>
          <button className={mode === "chips" ? "on" : ""} onClick={() => setMode("chips")}>
            chips
          </button>
        </div>
        <button className="btn ghost small" onClick={() => setAllExpanded(!allExpanded)} title="Show the literal properties in every node (double-click a node for just one)">
          {allExpanded ? "compact all" : "expand all"}
        </button>
        <button className="btn ghost small" onClick={() => cyRef.current && relayout(cyRef.current)}>
          re-layout
        </button>
        <button className="btn ghost small" onClick={() => cyRef.current?.fit(undefined, 30)}>
          fit
        </button>
        <input className="search" placeholder="Search nodes…" value={search} onChange={(e) => setSearch(e.target.value)} />
      </header>

      <div className="graph-filters">
        <label className="show-messages">
          <input type="checkbox" checked={showMessages} onChange={(e) => setShowMessages(e.target.checked)} />
          messages
        </label>
        {allTypes.length > 0 && <span className="flabel">types</span>}
        {allTypes.map((t) => (
          <button
            key={t}
            className={`fchip ${hiddenTypes.has(t) ? "off" : ""}`}
            style={{ borderColor: colorOf(t) }}
            onClick={() => toggle(hiddenTypes, t, setHiddenTypes)}
            title={hiddenTypes.has(t) ? "show" : "hide"}
          >
            {t}
          </button>
        ))}
        {allPrefixes.length > 1 && <span className="flabel">namespaces</span>}
        {allPrefixes.length > 1 &&
          allPrefixes.map((p) => (
            <button
              key={p}
              className={`fchip ${hiddenPrefixes.has(p) ? "off" : ""}`}
              onClick={() => toggle(hiddenPrefixes, p, setHiddenPrefixes)}
              title={hiddenPrefixes.has(p) ? "show" : "hide"}
            >
              {p}:
            </button>
          ))}
      </div>

      <div className="graph-body">
        <div className="graph-canvas" ref={box} />
        {visible.nodes.size === 0 && <div className="graph-empty">Nothing to show. Add triples, or relax the filters.</div>}
        {sel && (
          <aside className="graph-details">
            <div className="gd-head">
              <TermView term={sel.term} />
              <button className="icon" title="Close" onClick={() => setSelected(null)}>
                ×
              </button>
            </div>
            {sel.types.length > 0 && <div className="gd-types">{sel.types.join(", ")}</div>}
            <div className="gd-actions">
              <label title="Show only this node's neighbourhood">
                focus
                <select value={hops} onChange={(e) => setHops(+e.target.value)}>
                  <option value={0}>off</option>
                  <option value={1}>1 hop</option>
                  <option value={2}>2 hops</option>
                  <option value={3}>3 hops</option>
                </select>
              </label>
              <button className="btn ghost small" onClick={() => toggle(expanded, sel.id, setExpanded)}>
                {expanded.has(sel.id) ? "compact" : "expand"}
              </button>
              {sel.subject && (
                <button className="btn ghost small" onClick={() => onShowInSheet(sel.term.short)}>
                  show in sheet
                </button>
              )}
            </div>
            {sel.literals.length > 0 && (
              <dl className="gd-props">
                {sel.literals.map(([p, v], i) => (
                  <div key={i}>
                    <dt>{p}</dt>
                    <dd>{v}</dd>
                  </div>
                ))}
              </dl>
            )}
            {sel.links.length > 0 && (
              <div className="gd-links">
                <div className="flabel">links</div>
                {sel.links.map((t) => (
                  <button key={t.key} className="gd-link" onClick={() => goTo(t.o.n3)}>
                    <span>{t.p.short}</span> → <b>{nameOf(model.nodes.get(t.o.n3), t.o)}</b>
                  </button>
                ))}
              </div>
            )}
            {sel.incoming.length > 0 && (
              <div className="gd-links">
                <div className="flabel">pointed to by</div>
                {sel.incoming.map((t) => (
                  <button key={t.key} className="gd-link" onClick={() => goTo(t.s.n3)}>
                    <b>{nameOf(model.nodes.get(t.s.n3), t.s)}</b> <span>{t.p.short}</span> →
                  </button>
                ))}
              </div>
            )}
          </aside>
        )}
      </div>
    </section>
  );
}

function relayout(cy: Core) {
  cy.layout({
    name: "cose", animate: false, nodeDimensionsIncludeLabels: true, randomize: true, padding: 30,
    nodeRepulsion: () => 30000, idealEdgeLength: () => 120, nodeOverlap: 40, componentSpacing: 120,
    gravity: 0.4, numIter: 2000,
    // lay out in the panel's shape, not in a tall column
    boundingBox: { x1: 0, y1: 0, w: Math.max(cy.width(), 400), h: Math.max(cy.height(), 300) },
  } as cytoscape.LayoutOptions).run();
  cy.fit(undefined, 30);
}
