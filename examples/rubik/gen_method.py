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

from dataclasses import dataclass
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


# The search tracks where some stickers are: a state is a `bytes` of facelet
# indices, and a move is a translation table, so a turn is one bytes.translate.
INDEX = {name: i for i, name in enumerate(sorted(FL))}
TABLE = {}
for _mv, _m in MOVES.items():
    _t = bytearray(range(256))
    for _a, _b in _m.items():
        _t[INDEX[_a]] = INDEX[_b]
    TABLE[_mv] = bytes(_t)


def search(start: tuple[str, ...], goal, depth: int = 5) -> list[str]:
    """The shortest move sequence taking the tracked stickers from `start` to `goal`,
    or to any of several goals (a list of tuples).

    Bidirectional breadth-first search, at most `depth` moves from each side. Two
    consecutive moves never turn the same face.
    """
    goals = goal if isinstance(goal, list) else [goal]
    if start in goals:
        return []
    s0 = bytes(INDEX[p] for p in start)
    g0 = [bytes(INDEX[p] for p in g) for g in goals]
    # state -> (previous state, move), on each side; backwards, the move is the one
    # that leads from this state towards the goal
    fwd: dict[bytes, tuple] = {s0: (None, None)}
    bwd: dict[bytes, tuple] = {g: (None, None) for g in g0}
    frontiers = {"f": [s0], "b": list(g0)}

    def path(seen, s):
        out = []
        while seen[s][0] is not None:
            s, mv = seen[s]
            out.append(mv)
        return out

    for _ in range(depth):
        for side in ("f", "b"):
            seen, other = (fwd, bwd) if side == "f" else (bwd, fwd)
            nxt = []
            for state in frontiers[side]:
                last = seen[state][1]
                for mv, table in (TABLE.items() if side == "f" else INV_TABLE.items()):
                    if last is not None and last[0] == mv[0]:
                        continue
                    s2 = state.translate(table)
                    if s2 in seen:
                        continue
                    seen[s2] = (state, mv)
                    nxt.append(s2)
                    if s2 in other:
                        f = path(fwd, s2)[::-1]
                        b = path(bwd, s2)
                        return f + b
            frontiers[side] = nxt
    raise ValueError(f"no sequence within {2 * depth} moves: {start} -> {goal}")


# backwards: undoing `mv` steps from a state towards the start, and the forward
# path then takes `mv`, so the move recorded is `mv` itself
INV_TABLE = {mv: TABLE[INVERSE[mv]] for mv in MOVES}


def check(alg: list[str], start: tuple[str, ...], goal: tuple[str, ...]) -> None:
    state = start
    for mv in alg:
        state = _apply(state, mv)
    assert state in (goal if isinstance(goal, list) else [goal]), (alg, start, goal)


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


# --- stage 2: the white corners ---------------------------------------------------
# Target: the corner white + front + right colours, into DFR with white on D.
# Kept: the cross, and the other three bottom corner slots (except the one the
# target is in), sticker for sticker.

CORNER = ("D3", "F9", "R7")  # DFR, as white / front colour / right colour
CROSS = ("D2", "F8") + tuple(p for slot in CROSS_SLOTS for p in slot)
BOTTOM_CORNERS = (("D1", "F7", "L9"), ("D7", "B9", "L7"), ("D9", "B7", "R9"))


def corner_states():
    """Every place and twist of the target corner: everything moves can reach."""
    seen, frontier = {CORNER}, [CORNER]
    while frontier:
        frontier = [s2 for s in frontier for mv in MOVES
                    if (s2 := _apply(s, mv)) not in seen and not seen.add(s2)]
    return sorted(seen - {CORNER})


def corner_cases():
    for white, front, right in corner_states():
        keep = CROSS + tuple(p for slot in BOTTOM_CORNERS if white not in slot for p in slot)
        start = (white, front, right) + keep
        goal = CORNER + keep
        alg = search(start, goal)
        check(alg, start, goal)
        slot = "".join(sorted({white[0], front[0], right[0]}, key="UDFBRL".index))
        label = f"the white-front-right corner is at {slot}, white facing {FACE_WORD[white[0]]}"
        yield f"corner_{white}", label, [(white, "D5"), (front, "F5"), (right, "R5")], alg


# --- stage 3: the middle-layer edges ----------------------------------------------
# Target: the edge front + right colours, into FR (F6, R4).
# Kept: the first layer, and the other three middle slots (except the one the target
# is in), sticker for sticker.
# - Edge in the top layer: insert it (the classic 8 moves, plus a U setup if needed).
# - Edge in a wrong middle slot, or flipped in FR: inserting it directly takes ~16
#   moves, beyond the search. As in the beginner method, its algorithm only takes
#   the edge out to the top layer; the solver then plans an insertion.

FIRST_LAYER = CROSS + CORNER + tuple(p for slot in BOTTOM_CORNERS for p in slot)
EDGE = ("F6", "R4")  # FR, as front colour / right colour
MIDDLE_SLOTS = (("F4", "L6"), ("B4", "R6"), ("B6", "L4"))  # FL, BR, BL: the others
TOP_EDGES = [s for s in EDGE_SLOTS if any(p[0] == "U" for p in s)]


def reachable(stickers: tuple[str, ...]) -> set[tuple[str, ...]]:
    seen, frontier = {stickers}, [stickers]
    while frontier:
        frontier = [s2 for s in frontier for mv in MOVES
                    if (s2 := _apply(s, mv)) not in seen and not seen.add(s2)]
    return seen


def middle_cases():
    for front, right in sorted(reachable(EDGE) - {EDGE}):
        if front[0] in "D" or right[0] in "D":
            continue  # a bottom slot: the cross is there once the first layer is solved
        keep = FIRST_LAYER + tuple(p for slot in MIDDLE_SLOTS if front not in slot for p in slot)
        start = (front, right) + keep
        slot = "".join(sorted({front[0], right[0]}, key="UDFBRL".index))
        if "U" in slot:
            goal, what = EDGE + keep, "insert it"
        else:  # take it out to the top layer, either way round
            goal = [(a, b) + keep for top in TOP_EDGES for a, b in (top, top[::-1])]
            what = "take it out"
        alg = search(start, goal)
        check(alg, start, goal)
        label = f"the front-right edge is at {slot}, front colour facing {FACE_WORD[front[0]]}: {what}"
        yield f"middle_{front}", label, [(front, "F5"), (right, "R5")], alg


# --- stages 4-7: the last layer, textbook algorithms written by hand --------------
# The beginner method's last layer is iterative: a few algorithms, applied to the
# case at hand, then look again. Needs here also say what must NOT be ("unlike"),
# or that any of several stickers will do (several positions in one need).

def like(*ats: str, c: str) -> tuple:
    """Some sticker at `ats` has the colour of centre `c`."""
    return (ats, "like", c)


def unlike(*ats: str, c: str) -> tuple:
    """Some sticker at `ats` doesn't have the colour of centre `c`."""
    return (ats, "unlike", c)


FRURUF = "F R U Ri Ui Fi".split()          # yellow cross: dot -> L -> line -> cross
SUNE_U = "R U Ri U R U2 Ri U".split()      # yellow edges: swaps the front and left edges
NIKLAS = "U R Ui Li U Ri Ui L".split()     # corners: cycles three, keeps the front-right one
RDRD = "Ri Di R D".split()                 # twists the front-right corner; repeated, it comes back

UFR = ("U9", "F3", "R1")  # the front-right corner of the top layer
PLACED = [like(*UFR, c="U5"), like(*UFR, c="F5"), like(*UFR, c="R5")]  # its colours, any twist


@dataclass
class Case:
    name: str
    label: str
    needs: list            # of (positions, "like" | "unlike", centre)
    alg: list[str]
    priority: int = 0      # among the stage's matching cases, the highest goes first


@dataclass
class Stage:
    name: str
    label: str
    goal: list             # needs that must hold in every frame
    cases: list[Case]
    same_frame: bool = False  # plan only in the frame the cube is held in


def searched(cases) -> list[Case]:
    return [Case(n, label, [((at,), "like", c) for at, c in needs], alg) for n, label, needs, alg in cases()]


def stages() -> list[Stage]:
    def goal(*pairs):
        return [((at,), "like", c) for at, c in pairs]
    return [
        Stage("Cross", "white cross", goal(("D2", "D5"), ("F8", "F5")), searched(cross_cases)),
        # the corners keep the cross, so their goal needs only the corners
        Stage("Corners", "white corners", goal(("D3", "D5"), ("F9", "F5"), ("R7", "R5")), searched(corner_cases)),
        Stage("Middle", "middle layer", goal(("F6", "F5"), ("R4", "R5")), searched(middle_cases)),
        Stage("YellowCross", "yellow cross", [like("U8", c="U5")], [
            Case("yc_dot", "no yellow edge on top", [unlike(e, c="U5") for e in ("U2", "U4", "U6", "U8")], FRURUF),
            Case("yc_l", "an L: yellow edges at the back and on the left",
                 [like("U2", c="U5"), like("U4", c="U5"), unlike("U6", c="U5"), unlike("U8", c="U5")], FRURUF),
            Case("yc_line", "a line: yellow edges on the left and on the right",
                 [like("U4", c="U5"), like("U6", c="U5"), unlike("U2", c="U5")], FRURUF),
        ]),
        Stage("YellowEdges", "yellow edges", [like("F2", c="F5")], [
            Case("ye_adjacent", "the back and right edges match, the front one doesn't",
                 [like("B2", c="B5"), like("R2", c="R5"), unlike("F2", c="F5")], SUNE_U),
            Case("ye_opposite", "the front and back edges match, the right one doesn't",
                 [like("F2", c="F5"), like("B2", c="B5"), unlike("R2", c="R5")], SUNE_U),
            Case("ye_turn", "fewer than two edges match: turn the top", [], ["U"], priority=-1),
        ]),
        Stage("CornersPlaced", "yellow corners placed", PLACED, [
            Case("cp_one", "the front-right corner is in place, twisted or not", PLACED, NIKLAS),
            Case("cp_none", "no corner is in place", [], NIKLAS, priority=-1),
        ]),
        # The cube is held still: R' D' R D twists the front-right corner and, repeated,
        # puts the bottom back, so every repetition must use the same R and D.
        Stage("CornersOriented", "yellow corners oriented",
              [like("U8", c="U5"), like("U9", c="U5"), like("D2", c="D5"), like("D3", c="D5")]
              + [like(f"F{i}", c="F5") for i in (1, 2, 3, 4, 6, 7, 8, 9)], [
            Case("co_twist", "the front-right corner's yellow isn't on top", [unlike("U9", c="U5")], RDRD),
            Case("co_next", "it is, but another corner's isn't: bring that one round",
                 [like("U9", c="U5"), unlike("U1", "U3", "U7", c="U5")], ["U"]),
            Case("co_align", "the top is yellow but turned: turn it into place",
                 [like(c, c="U5") for c in ("U1", "U3", "U7", "U9")] + [unlike("F2", c="F5")], ["U"]),
        ], same_frame=True),
    ]


# --- output -----------------------------------------------------------------------

def emit_need(out: list[str], name: str, need) -> None:
    ats, kind, centre = need
    out.append(f"{name} rk:at {', '.join('rpos:' + a for a in ats)} ; rk:{kind} rpos:{centre} .")


def emit_case(out: list[str], stage: str, case: Case) -> None:
    need_names = [f"need:{case.name}_{i}" for i in range(len(case.needs))]
    first = f"alg:{case.name}_0" if case.alg else "rdf:nil"
    out.append(f"case:{case.name} a rk:Case ; rk:stage stage:{stage} ; rdfs:label \"{case.label}\" ;")
    if need_names:
        out.append(f"  rk:need {', '.join(need_names)} ;")
    if case.priority:
        out.append(f"  rk:priority {case.priority} ;")
    out.append(f"  rk:algorithm {first} .")
    for nn, need in zip(need_names, case.needs):
        emit_need(out, nn, need)
    for i, mv in enumerate(case.alg):
        rest = f"alg:{case.name}_{i + 1}" if i + 1 < len(case.alg) else "rdf:nil"
        out.append(f"alg:{case.name}_{i} a rk:AlgorithmStep ; rdf:first rmv:{mv} ; rdf:rest {rest} .")


def main() -> None:
    all_stages = stages()
    out = [PREFIXES, "# Generated by gen_method.py: do not edit by hand.\n"]
    out.append(f"rk:beginnerMethod a rk:Method ; rdfs:label \"beginner method (layer by layer)\" ; "
               f"rk:firstStage stage:{all_stages[0].name} .\n")

    out.append("# --- stages ------------------------------------------------------------------")
    for i, st in enumerate(all_stages):
        nxt = all_stages[i + 1].name if i + 1 < len(all_stages) else "Done"
        goals = [f"need:{st.name}Goal_{j}" for j in range(len(st.goal))]
        out.append(f"stage:{st.name} a rk:Stage ; rdfs:label \"{st.label}\" ; rk:next stage:{nxt} ;"
                   + (" rk:sameFrame true ;" if st.same_frame else ""))
        out.append(f"  rk:goal {', '.join(goals)} .")
        for g, need in zip(goals, st.goal):
            emit_need(out, g, need)
    out.append("stage:Done a rk:Stage ; rdfs:label \"done\" .")

    for i, st in enumerate(all_stages):
        title = f"stage {i + 1}: {st.label}"
        out.append(f"\n# --- {title} " + "-" * (72 - len(title)))
        for case in st.cases:
            emit_case(out, st.name, case)
        lengths = [len(c.alg) for c in st.cases]
        print(f"{st.name}: {len(lengths)} cases, algorithms of {min(lengths)}-{max(lengths)} moves")

    (HERE / "method.ttl").write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
