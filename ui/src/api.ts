export type Term = {
  n3: string;
  short: string;
  kind: "uri" | "bnode" | "literal";
  value?: string;
  datatype?: string;
};

export type Triple = {
  key: string;
  s: Term;
  p: Term;
  o: Term;
  changed: boolean;
  /** read-only knowledge (D28): "knowledge" for the project's own, otherwise the pack's title */
  source?: string;
};

export type Violation = {
  focus: string | null;
  path: string | null;
  value: string | null;
  component: string | null;
  severity: string | null;
  message: string;
};

export type Sheet = {
  version: number;
  prefixes: Record<string, string>;
  triples: Triple[];
  removed: Triple[];
  violations: Violation[];
};

export type Application = {
  id: string;
  operation: string;
  bindings: Record<string, Term>;
  deletes: Triple[];
  inserts: Triple[];
  valid: boolean;
  violations: Violation[];
  scores: Record<string, number>;
  total: number;
  /** an operation with no effects: when it wins, autopilot stops (design D21) */
  noop: boolean;
  /** the pack the operation comes from (D28) */
  layer: string | null;
};

export type PendingCall = {
  id: string;
  tool: string;
  command: string;
  suggested: string;
  /** null when the project has no package manifest */
  declared: boolean | null;
};

export type TrustRule = { id: string; template: string };

export type LogEntry = {
  n: number;
  kind: "tick" | "tool" | "edit" | "info" | "undo" | "input";
  text: string;
  tick: number;
  score?: number;
  manual?: boolean;
  approved?: boolean;
  rule?: string;
  bindings?: Record<string, string>;
};

export type Controller = { name: string; active: boolean; weight: number; query: string; layer: string | null };

export type AutopilotStatus = "idle" | "running" | "awaiting-approval" | "listening" | "done";

/** A message on lr:in or lr:out (design D25). */
export type Message = {
  id: string;
  short: string;
  channel: "in" | "out";
  order: number;
  text: string | null;
  types: string[];
  triples: Triple[];
};

export type State = {
  project: string;
  version: number;
  tick: number;
  autopilot: AutopilotStatus;
  delay_ms: number;
  pending: PendingCall[];
  operations: string[];
  controllers: Controller[];
  log: LogEntry[];
  trust: TrustRule[];
  undo: string | null;
  journal: number;
  package: { title: string; version: string } | null;
  /** false = app mode: the sheet is read-only unless unlocked (D25) */
  directEdits: boolean;
  listen: boolean;
  messages: { in: number; out: number };
};

export type Suggestion = { value: string; hint: string; status?: "missing" | "ok" | "full" };

export type ObjectConstraint = {
  kind?: "iri" | "literal" | "enum";
  class?: string;
  datatype?: string;
  nodeKind?: string;
  pattern?: string;
  full?: string;
};

export type SuggestResult = {
  items: Suggestion[];
  constraint: ObjectConstraint;
  missing: Suggestion[];
  hint: string | null;
};

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const d = body.detail;
    if (d && typeof d === "object" && "message" in d) {
      const vs = (d.violations ?? []) as Violation[];
      throw new Error([d.message, ...vs.map((v) => `${v.path ?? v.focus ?? ""} ${v.message}`.trim())].join("\n"));
    }
    throw new Error(d ?? `${res.status} ${res.statusText}`);
  }
  return res.json();
}

export const api = {
  state: () => call<State>("GET", "/state"),
  sheet: () => call<Sheet>("GET", "/sheet"),
  applications: (contains?: string) =>
    call<{ version: number; applications: Application[] }>(
      "GET",
      `/applications${contains ? `?contains=${encodeURIComponent(contains)}` : ""}`,
    ),
  suggest: (field: "s" | "p" | "o", s: string, p: string, q: string) =>
    call<SuggestResult>("GET", `/suggest?${new URLSearchParams({ field, s, p, q })}`),
  addTriple: (s: string, p: string, o: string, force = false) => call("POST", "/sheet/triples", { s, p, o, force }),
  deleteTriple: (t: Triple, force = false) =>
    call("POST", "/sheet/delete", { s: t.s.n3, p: t.p.n3, o: t.o.n3, force }),
  post: (turtle: string) => call<{ id: string; short: string }>("POST", "/in", { turtle }),
  messages: (channel: "in" | "out") => call<{ messages: Message[] }>("GET", `/messages?channel=${channel}`),
  ack: (ids?: string[]) => call<{ acked: number }>("POST", "/out/ack", ids ? { ids } : {}),
  listen: (listen: boolean) => call("POST", "/autopilot/listen", { listen }),
  apply: (id: string) => call("POST", `/apply/${id}`),
  start: (delay_ms: number, listen?: boolean) => call("POST", "/autopilot/start", { delay_ms, listen }),
  stop: () => call("POST", "/autopilot/stop"),
  step: () => call<{ status: string }>("POST", "/autopilot/step"),
  decide: (id: string, approve: boolean, remember?: string) => call("POST", "/approvals", { id, approve, remember }),
  trust: (template: string) => call("POST", "/trust", { template }),
  untrust: (id: string) => call("DELETE", `/trust/${id}`),
  toggleController: (name: string) => call("POST", `/controllers/${encodeURIComponent(name)}/toggle`),
  undo: () => call("POST", "/undo"),
  exportUrl: (sheet: "seed" | "state" | "none") => `/api/export?sheet=${sheet}`,
};

export function connectEvents(onEvent: (e: { type: string }) => void): () => void {
  let ws: WebSocket | null = null;
  let closed = false;
  const open = () => {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/api/events`);
    ws.onmessage = (m) => onEvent(JSON.parse(m.data));
    ws.onclose = () => {
      if (!closed) setTimeout(open, 1000);
    };
  };
  open();
  return () => {
    closed = true;
    ws?.close();
  };
}
