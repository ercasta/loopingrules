// The only LoopingRules endpoints the viewer uses: the D25 channels, plus
// starting a listening autopilot. It never edits the sheet.

export interface Term { n3: string; short: string; kind: string; value?: string }
export interface Triple { s: Term; p: Term; o: Term }
export interface Message { id: string; order: number; text: string | null; types: string[]; triples: Triple[] }

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const r = await fetch(path, {
    method,
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${method} ${path}: ${r.status} ${await r.text()}`);
  return r.json() as Promise<T>;
}

export const post = (turtle: string) => call<{ id: string }>("POST", "/api/in", { turtle });
export const outbox = () => call<{ messages: Message[] }>("GET", "/api/messages?channel=out").then((r) => r.messages);
export const ack = (ids: string[]) => call("POST", "/api/out/ack", { ids });
export const listen = () => call("POST", "/api/autopilot/start", { listen: true, delay_ms: 0 });

/** The local name of an IRI, a prefixed name or an n3 term: "mv:Ri" -> "Ri". */
export const local = (t: string) => t.replace(/[<>]/g, "").split(/[#/:]/).pop() ?? t;

/** The objects of `subject`'s triples whose predicate has this local name. */
export function values(m: Message, subject: string, predicate: string): Term[] {
  return m.triples.filter((t) => t.s.n3 === subject && local(t.p.n3) === predicate).map((t) => t.o);
}

export function onChange(fn: () => void): void {
  const connect = () => {
    const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/events`);
    ws.onmessage = (e) => {
      const ev = JSON.parse(e.data);
      if (ev.type === "sheet-changed" && ev.inserted) fn();
    };
    ws.onopen = () => fn();
    ws.onclose = () => setTimeout(connect, 1000);
  };
  connect();
}
