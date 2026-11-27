export type Term = {
  n3: string;
  short: string;
  kind: "uri" | "bnode" | "literal";
  value?: string;
  datatype?: string;
};

export type Triple = { key: string; s: Term; p: Term; o: Term; changed: boolean };

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
};

export type PendingCall = { id: string; tool: string; command: string };

export type LogEntry = {
  n: number;
  kind: "tick" | "tool" | "edit" | "info";
  text: string;
  tick: number;
  score?: number;
  manual?: boolean;
  approved?: boolean;
  bindings?: Record<string, string>;
};

export type Controller = { name: string; active: boolean; query: string };

export type AutopilotStatus = "idle" | "running" | "awaiting-approval" | "done";

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
};

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `${res.status} ${res.statusText}`);
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
  addTriple: (s: string, p: string, o: string) => call("POST", "/sheet/triples", { s, p, o }),
  deleteTriple: (t: Triple) => call("POST", "/sheet/delete", { s: t.s.n3, p: t.p.n3, o: t.o.n3 }),
  apply: (id: string) => call("POST", `/apply/${id}`),
  start: (delay_ms: number) => call("POST", "/autopilot/start", { delay_ms }),
  stop: () => call("POST", "/autopilot/stop"),
  step: () => call<{ status: string }>("POST", "/autopilot/step"),
  decide: (id: string, approve: boolean) => call("POST", "/approvals", { id, approve }),
  toggleController: (name: string) => call("POST", `/controllers/${encodeURIComponent(name)}/toggle`),
  save: () => call<{ saved: string }>("POST", "/project/save"),
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
