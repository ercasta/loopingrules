import { type Message, ack, listen, local, onChange, outbox, post, values } from "./api";
import { CubeView } from "./cube";
import { type Colours, applyMove, moveLabel, parseMove, randomScramble } from "./geometry";

const $ = <T extends HTMLElement>(sel: string) => document.querySelector(sel) as T;
const view = new CubeView($("#stage"));

// --- what the viewer knows ------------------------------------------------------
let colours: Colours | null = null; // null until the first viz:State
let shown: number | null = null;    // the seq of the last turn on screen
const turns = new Map<number, { id: string; move: string }>();
let pendingState: { id: string; turns: number; colours: Colours } | null = null;
const seen = new Set<string>();
const resets = new Set<string>();
let syncAsked = false;

// --- the page --------------------------------------------------------------------
function say(text: string, kind = "") {
  const li = document.createElement("li");
  li.textContent = text;
  if (kind) li.className = kind;
  const log = $("#log");
  log.prepend(li);
  while (log.children.length > 12) log.lastChild!.remove();
}

function showMove(move: string, seq: number) {
  const span = document.createElement("span");
  span.textContent = moveLabel(move);
  span.title = `turn ${seq}`;
  const strip = $("#moves");
  strip.append(span);
  while (strip.children.length > 40) strip.firstChild!.remove();
  $("#count").textContent = String(seq);
}

const speed = () => Number(($("#speed") as HTMLInputElement).value);

async function send(turtle: string): Promise<string | null> {
  try {
    return (await post(turtle)).id;
  } catch (e) {
    say(String(e), "error");
    return null;
  }
}

async function sync() {
  syncAsked = true;
  await send("[] a viz:Sync .");
}

$("#scramble").onclick = () => {
  const moves = randomScramble(20);
  say(`scramble: ${moves.map(moveLabel).join(" ")}`, "me");
  void send(`[] a rk:Scramble ; rk:moves ( ${moves.map((m) => "mv:" + m).join(" ")} ) .`);
};
$("#reset").onclick = async () => {
  say("reset", "me");
  const id = await send("[] a rk:Reset .");
  if (id) resets.add(id);
};
$("#sync").onclick = () => void sync();

// --- reading lr:out ------------------------------------------------------------------
function read(m: Message) {
  const kinds = m.types.map(local);
  if (kinds.includes("Turn")) {
    const seq = Number(values(m, m.id, "seq")[0]?.value);
    const move = local(values(m, m.id, "move")[0]?.n3 ?? "");
    turns.set(seq, { id: m.id, move });
  } else if (kinds.includes("State")) {
    const c: Colours = new Map();
    for (const part of values(m, m.id, "facelet")) {
      const pos = values(m, part.n3, "pos")[0], col = values(m, part.n3, "colour")[0];
      if (pos && col) c.set(local(pos.n3), local(col.n3));
    }
    pendingState = { id: m.id, turns: Number(values(m, m.id, "turns")[0]?.value), colours: c };
  } else if (kinds.includes("Say")) {
    if (m.text) say(m.text);
    const to = values(m, m.id, "replyTo")[0]?.n3;
    void ack([m.id]);
    if (to && resets.has(to)) {
      resets.delete(to);
      void sync(); // the colours changed without turns
    }
  }
}

let refreshing = false, again = false;
async function refresh() {
  if (refreshing) return void (again = true);
  refreshing = true;
  try {
    do {
      again = false;
      for (const m of await outbox()) {
        if (seen.has(m.id)) continue;
        seen.add(m.id);
        read(m);
      }
      void pump();
    } while (again);
  } catch (e) {
    $("#status").textContent = "not connected: is `lr serve` running on port 8765?";
  } finally {
    refreshing = false;
  }
}

// --- showing turns, in order, one at a time ---------------------------------------
let pumping = false;
async function pump() {
  if (pumping) return;
  pumping = true;
  try {
    for (;;) {
      if (pendingState) {
        const st = pendingState;
        pendingState = null;
        colours = st.colours;
        shown = st.turns;
        syncAsked = false;
        view.paint(colours);
        $("#count").textContent = String(shown);
        await ack([st.id]);
        continue;
      }
      if (shown === null || colours === null) break; // waiting for the first state
      const stale = [...turns].filter(([seq]) => seq <= shown!);
      if (stale.length) {
        for (const [seq] of stale) turns.delete(seq);
        await ack(stale.map(([, t]) => t.id));
      }
      const next = turns.get(shown + 1);
      if (next) {
        const mv = parseMove(next.move);
        if (mv) {
          await view.turn(mv, speed());
          colours = applyMove(colours, mv);
          view.paint(colours);
        }
        shown += 1;
        turns.delete(shown);
        showMove(next.move, shown);
        await ack([next.id]); // "displayed": a pacing policy may be waiting for this
        continue;
      }
      if (turns.size && !syncAsked) await sync(); // a gap: someone else acknowledged turns
      break;
    }
  } finally {
    pumping = false;
  }
  $("#status").textContent = shown === null ? "waiting for the cube's state…" : "connected";
}

// --- start ---------------------------------------------------------------------------
view.paint(new Map());
// for scripts/dev/shot.py: what the viewer shows, to compare with the model
(window as unknown as { __rubik: unknown }).__rubik = { colours: () => colours && Object.fromEntries(colours), shown: () => shown };
onChange(() => void refresh());
listen().catch((e) => say(String(e), "error"));
void sync();
// Events can be lost (a dropped socket, a dev-server reload): poll slowly as well,
// and ask again for the state if it hasn't come.
setInterval(() => void refresh(), 2000);
setInterval(() => { if (shown === null) void sync(); }, 5000);
