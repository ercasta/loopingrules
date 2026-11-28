"""Generate the beginner method as knowledge: stages, cases and algorithms.

    python examples/rubik/gen_method.py

Writes method.ttl next to this script (committed). Everything is written as the
beginner method writes it: white on D, in relative names (rpos:, rmv:). The
frames in geometry.ttl map them to this cube.

- A **case** is a set of needs. Each need says that the sticker at a relative position
  has the colour of a relative centre: `need:x rk:at rpos:U8 ; rk:like rpos:D5`
  means "the sticker at U8 is white" (D5 is the white centre).
- Each case has an **algorithm**: a list of relative moves, made of named nodes
  (knowledge can't contain blank nodes), each `a rk:AlgorithmStep`.
- A **stage** has a goal (needs that must hold in every frame) and a next stage.

Algorithms are found by search: the shortest sequence that solves the case's target
and leaves alone what earlier stages, and the other targets of this stage, solved.
"""

from __future__ import annotations

from pathlib import Path

from gen_geometry import facelets, move_map, move_names

HERE = Path(__file__).resolve().parent

PREFIXES = """\
@prefix rdf:   <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs:  <http://www.w3.org/2000/01/rdf-schema#> .
@prefix rk:    <https://example.org/rubik#> .
@prefix rpos:  <https://example.org/rubik/rpos#> .
@prefix rmv:   <https://example.org/rubik/rmv#> .
@prefix stage: <https://example.org/rubik/stage#> .
@prefix case:  <https://example.org/rubik/case#> .
@prefix need:  <https://example.org/rubik/need#> .
@prefix alg:   <https://example.org/rubik/alg#> .
"""

MOVES = {m: move_map(m) for m in move_names()}
INVERSE = {m: (m[0] if m.endswith("i") else m if m.endswith("2") else m + "i") for m in MOVES}

FL = facelets()
EDGE_SLOTS: list[tuple[str, str]] = []  # (facelet, facelet) of the 12 edge slots
for c in {c for c, _ in FL.values()}:
    names = [n for n, (cc, _) in FL.items() if cc == c]
    if len(names) == 2:
        EDGE_SLOTS.append(tuple(sorted(names)))
PARTNER = {a: b for a, b in EDGE_SLOTS} | {b: a for a, b in EDGE_SLOTS}


def _apply(state: tuple[str, ...], move: str) -> tuple[str, ...]:
    m = MOVES[move]
    return tuple(m[p] for p in state)


def search(start: tuple[str, ...], goal: tuple[str, ...], depth: int = 5) -> list[str]:
    """The shortest move sequence taking the tracked stickers from `start` to `goal`.

    Bidirectional breadth-first search, at most `depth` moves from each side. Two
    consecutive moves never turn the same face.
    """
    if start == goal:
        return []
    fwd = {start: []}
    bwd = {goal: []}
    fwd_frontier, bwd_frontier = [start], [goal]
    for _ in range(depth):
        for side in ("f", "b"):
            frontier = fwd_frontier if side == "f" else bwd_frontier
            seen, other = (fwd, bwd) if side == "f" else (bwd, fwd)
            nxt = []
            for state in frontier:
                path = seen[state]
                for mv in MOVES:
                    if path and path[-1][0] == mv[0]:
                        continue
                    # backwards, undo `mv`: the forward path then ends with `mv`
                    s2 = _apply(state, mv if side == "f" else INVERSE[mv])
                    if s2 in seen:
                        continue
                    seen[s2] = path + [mv]
                    nxt.append(s2)
                    if s2 in other:
                        f = seen[s2] if side == "f" else other[s2]
                        b = other[s2] if side == "f" else seen[s2]
                        return f + list(reversed(b))
            if side == "f":
                fwd_frontier = nxt
            else:
                bwd_frontier = nxt
    raise ValueError(f"no sequence within {2 * depth} moves: {start} -> {goal}")


def check(alg: list[str], start: tuple[str, ...], goal: tuple[str, ...]) -> None:
    state = start
    for mv in alg:
        state = _apply(state, mv)
    assert state == goal, (alg, start, goal)


# --- stage 1: the white cross -----------------------------------------------------
# Target: the edge white + front colour, into DF with white on D.
# Kept: the other three cross slots, sticker for sticker.

CROSS_SLOTS = (("D6", "R8"), ("D8", "B8"), ("D4", "L8"))  # the other three cross slots
FACE_WORD = {"U": "up", "D": "down", "F": "front", "B": "back", "R": "right", "L": "left"}


def cross_cases():
    for white in sorted(PARTNER):
        other = PARTNER[white]
        if (white, other) == ("D2", "F8"):
            continue
        # keep the cross slots the target isn't in, sticker for sticker
        keep = tuple(p for slot in CROSS_SLOTS if white not in slot for p in slot)
        start = (white, other) + keep
        goal = ("D2", "F8") + keep
        alg = search(start, goal)
        check(alg, start, goal)
        slot = "".join(sorted({white[0], other[0]}, key="UDFBRL".index))
        label = f"the white-front edge is at {slot}, white facing {FACE_WORD[white[0]]}"
        yield f"cross_{white}", label, [(white, "D5"), (other, "F5")], alg


def emit_case(out: list[str], stage: str, name: str, label: str, needs, alg: list[str]) -> None:
    need_names = [f"need:{name}_{i}" for i in range(len(needs))]
    first = f"alg:{name}_0" if alg else "rdf:nil"
    out.append(f"case:{name} a rk:Case ; rk:stage stage:{stage} ; rdfs:label \"{label}\" ;")
    out.append(f"  rk:need {', '.join(need_names)} ; rk:algorithm {first} .")
    for nn, (at, like) in zip(need_names, needs):
        out.append(f"{nn} rk:at rpos:{at} ; rk:like rpos:{like} .")
    for i, mv in enumerate(alg):
        rest = f"alg:{name}_{i + 1}" if i + 1 < len(alg) else "rdf:nil"
        out.append(f"alg:{name}_{i} a rk:AlgorithmStep ; rdf:first rmv:{mv} ; rdf:rest {rest} .")


def main() -> None:
    out = [PREFIXES, "# Generated by gen_method.py: do not edit by hand.\n"]
    out.append("rk:beginnerMethod a rk:Method ; rdfs:label \"beginner method (layer by layer)\" ; rk:firstStage stage:Cross .\n")

    out.append("# --- stages ------------------------------------------------------------------")
    out.append("stage:Cross a rk:Stage ; rdfs:label \"white cross\" ; rk:next stage:Done ;")
    out.append("  rk:goal need:crossGoal_0, need:crossGoal_1 .")
    out.append("need:crossGoal_0 rk:at rpos:D2 ; rk:like rpos:D5 .")
    out.append("need:crossGoal_1 rk:at rpos:F8 ; rk:like rpos:F5 .")
    out.append("stage:Done a rk:Stage ; rdfs:label \"done\" .")

    out.append("\n# --- stage 1: the white cross, one edge at a time ------------------------")
    lengths = []
    for name, label, needs, alg in cross_cases():
        emit_case(out, "Cross", name, label, needs, alg)
        lengths.append(len(alg))
    print(f"cross: {len(lengths)} cases, algorithms of {min(lengths)}-{max(lengths)} moves")

    (HERE / "method.ttl").write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
