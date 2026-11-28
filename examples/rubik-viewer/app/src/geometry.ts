// The same conventions as examples/rubik/gen_geometry.py. The model is the
// authority: the viewer only needs these to place stickers and animate turns,
// and every viz:State message from the model overwrites its colours.

export type Vec = [number, number, number];
export type FaceName = "U" | "D" | "F" | "B" | "R" | "L";

// face: normal, right and down as seen from outside, and its home colour
export const FACES: Record<FaceName, { n: Vec; r: Vec; d: Vec; home: string }> = {
  U: { n: [0, 1, 0], r: [1, 0, 0], d: [0, 0, 1], home: "White" },
  D: { n: [0, -1, 0], r: [1, 0, 0], d: [0, 0, -1], home: "Yellow" },
  F: { n: [0, 0, 1], r: [1, 0, 0], d: [0, -1, 0], home: "Green" },
  B: { n: [0, 0, -1], r: [-1, 0, 0], d: [0, -1, 0], home: "Blue" },
  R: { n: [1, 0, 0], r: [0, 0, -1], d: [0, -1, 0], home: "Red" },
  L: { n: [-1, 0, 0], r: [0, 0, 1], d: [0, -1, 0], home: "Orange" },
};
export const FACE_NAMES = Object.keys(FACES) as FaceName[];

const add = (...vs: Vec[]): Vec => [0, 1, 2].map((i) => vs.reduce((s, v) => s + v[i], 0)) as Vec;
const scale = (k: number, v: Vec): Vec => [k * v[0], k * v[1], k * v[2]];
const cross = (a: Vec, b: Vec): Vec => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
export const dot = (a: Vec, b: Vec) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cw = (n: Vec, v: Vec): Vec => add(scale(-1, cross(n, v)), scale(dot(n, v), n));
const key = (c: Vec, n: Vec) => `${c}|${n}`;

export interface Facelet { name: string; cubie: Vec; normal: Vec }

export const FACELETS: Facelet[] = FACE_NAMES.flatMap((f) => {
  const { n, r, d } = FACES[f];
  return Array.from({ length: 9 }, (_, i) => {
    const row = Math.floor(i / 3), col = i % 3;
    return { name: `${f}${i + 1}`, cubie: add(n, scale(col - 1, r), scale(row - 1, d)), normal: n };
  });
});

const byKey = new Map(FACELETS.map((f) => [key(f.cubie, f.normal), f.name]));

/** For a clockwise quarter turn of `face`: facelet name -> where its colour goes. */
export const TURN: Record<FaceName, Map<string, string>> = Object.fromEntries(
  FACE_NAMES.map((f) => {
    const n = FACES[f].n;
    const m = new Map<string, string>();
    for (const fl of FACELETS) {
      if (dot(fl.cubie, n) === 1) m.set(fl.name, byKey.get(key(cw(n, fl.cubie), cw(n, fl.normal)))!);
    }
    return [f, m];
  }),
) as Record<FaceName, Map<string, string>>;

export type Colours = Map<string, string>; // facelet name -> colour name (White, Red, ...)

export function solved(): Colours {
  return new Map(FACELETS.map((f) => [f.name, FACES[f.name[0] as FaceName].home]));
}

/** A move as the model names it: "R", "Ri" (R′) or "R2". */
export interface Move { face: FaceName; quarters: 1 | 2 | 3 }

export function parseMove(local: string): Move | null {
  const m = /^([UDFBRL])(i|2)?$/.exec(local);
  if (!m) return null;
  return { face: m[1] as FaceName, quarters: m[2] === "i" ? 3 : m[2] === "2" ? 2 : 1 };
}

export const moveLabel = (local: string) => local.replace(/i$/, "′");

export function applyMove(colours: Colours, mv: Move): Colours {
  let c = colours;
  for (let q = 0; q < mv.quarters; q++) {
    const next = new Map(c);
    for (const [from, to] of TURN[mv.face]) next.set(to, c.get(from)!);
    c = next;
  }
  return c;
}

export function randomScramble(length = 20): string[] {
  const out: string[] = [];
  let last = "";
  while (out.length < length) {
    const f = FACE_NAMES[Math.floor(Math.random() * 6)];
    if (f === last) continue;
    last = f;
    out.push(f + ["", "i", "2"][Math.floor(Math.random() * 3)]);
  }
  return out;
}
