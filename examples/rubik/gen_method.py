"""Generate the beginner method as knowledge, for the planning pack (design D31).

    python examples/rubik/gen_method.py

Writes method.ttl next to this script (committed). Everything is written as the
beginner method writes it: white on D, in relative names (rpos:, rmv:). The
frames in geometry.ttl map them to this cube.

- A **condition** ("need") says that some sticker at relative positions has (rk:like)
  or hasn't (rk:unlike) the colour of a relative centre: `need:x rk:at rpos:U8 ;
  rk:like rpos:D5` means "the sticker at U8 is white" (D5 is the white centre). The
  rubik project answers the pack's checks of them (solver.ttl).
- A **case** (pl:Case) has conditions and a procedure; a **stage** (pl:Stage) has a
  goal (conditions that must hold in every view) and a next stage.
- A **procedure** (pl:Procedure) is a list of relative moves, procedures, and loops
  (pl:Repeat, pl:Until). Its list nodes are named: knowledge can't have blank nodes.

For stages 1-3, procedures are found by search: the shortest sequence that solves
the case's target and leaves alone what earlier stages, and the other targets of
this stage, solved. The last layer is written by hand, from the textbook.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gen_geometry import facelets, frames, move_map, move_names

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
@prefix proc:  <https://example.org/rubik/proc#> .
@prefix step:  <https://example.org/rubik/step#> .
@prefix steps: <https://example.org/rubik/steps#> .
@prefix frame: <https://example.org/rubik/frame#> .
@prefix pl:    <https://loopingrules.org/planning#> .
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


# --- the method, as data ----------------------------------------------------------
# The method is written for the planning pack (design D31): stages with goals, cases
# with conditions ("needs"), and procedures. Stages 1-3 are searched (above); the last
# layer is written by hand, as the textbook writes it: named procedures, repeated, or
# repeated until a condition holds.

def like(*ats: str, c: str) -> tuple:
    """Some sticker at `ats` has the colour of centre `c`."""
    return (ats, "like", c)


def unlike(*ats: str, c: str) -> tuple:
    """Some sticker at `ats` doesn't have the colour of centre `c`."""
    return (ats, "unlike", c)


@dataclass
class Proc:
    name: str
    label: str
    steps: list            # of moves (str), Proc, Repeat or Until


@dataclass
class Repeat:
    name: str
    times: int
    do: Proc


@dataclass
class Until:
    name: str
    until: list            # needs, checked in the view the case was planned in
    do: Proc


@dataclass
class Case:
    name: str
    label: str
    needs: list            # of (positions, "like" | "unlike", centre)
    do: Proc
    priority: int = 0      # among the stage's matching cases, the highest goes first


@dataclass
class Stage:
    name: str
    label: str
    goal: list             # needs that must hold in every view
    cases: list[Case]


# The textbook's named procedures. Moves are relative: the view a case is planned in
# says which faces they turn.
SEXY = Proc("sexy", "sexy move", "R U Ri Ui".split())
TWIST = Proc("twistCorner", "twist the front-right corner (R' D' R D)", "Ri Di R D".split())
SUNE = Proc("sune", "sune", "R U Ri U R U2 Ri".split())
TURN_TOP = Proc("turnTop", "turn the top", ["U"])
YELLOW_CROSS = Proc("yellowCross", "front, sexy move, front back", ["F", SEXY, "Fi"])
SWAP_EDGES = Proc("swapEdges", "sune, then turn the top: swaps the front and left edges", [SUNE, "U"])
CYCLE_CORNERS = Proc("cycleCorners", "cycle three corners, keeping the front-right one",
                     "U R Ui Li U Ri Ui L".split())

UFR = ("U9", "F3", "R1")  # the front-right corner of the top layer
PLACED = [like(*UFR, c="U5"), like(*UFR, c="F5"), like(*UFR, c="R5")]  # its colours, any twist

# Stage 7, as the beginner method says it: for each corner, twist it until its yellow is
# on top, then turn the top to bring the next one; at the end, turn the top into place.
ORIENT_ONE = Proc("orientOne", "orient the front-right corner, then bring the next one", [
    Until("untilYellowUp", [like("U9", c="U5")], TWIST), "U"])
ORIENT_CORNERS = Proc("orientCorners", "orient the yellow corners", [
    Repeat("fourCorners", 4, ORIENT_ONE),
    Until("untilAligned", [like("F2", c="F5")], TURN_TOP)])


def searched(cases) -> list[Case]:
    return [Case(n, label, [((at,), "like", c) for at, c in needs], Proc(n, label, alg))
            for n, label, needs, alg in cases()]


def stages() -> list[Stage]:
    def goal(*pairs):
        return [((at,), "like", c) for at, c in pairs]
    return [
        Stage("Cross", "white cross", goal(("D2", "D5"), ("F8", "F5")), searched(cross_cases)),
        # the corners keep the cross, so their goal needs only the corners
        Stage("Corners", "white corners", goal(("D3", "D5"), ("F9", "F5"), ("R7", "R5")), searched(corner_cases)),
        Stage("Middle", "middle layer", goal(("F6", "F5"), ("R4", "R5")), searched(middle_cases)),
        Stage("YellowCross", "yellow cross", [like("U8", c="U5")], [
            Case("yc_dot", "no yellow edge on top", [unlike(e, c="U5") for e in ("U2", "U4", "U6", "U8")],
                 YELLOW_CROSS),
            Case("yc_l", "an L: yellow edges at the back and on the left",
                 [like("U2", c="U5"), like("U4", c="U5"), unlike("U6", c="U5"), unlike("U8", c="U5")],
                 YELLOW_CROSS),
            Case("yc_line", "a line: yellow edges on the left and on the right",
                 [like("U4", c="U5"), like("U6", c="U5"), unlike("U2", c="U5")], YELLOW_CROSS),
        ]),
        Stage("YellowEdges", "yellow edges", [like("F2", c="F5")], [
            Case("ye_adjacent", "the back and right edges match, the front one doesn't",
                 [like("B2", c="B5"), like("R2", c="R5"), unlike("F2", c="F5")], SWAP_EDGES),
            Case("ye_opposite", "the front and back edges match, the right one doesn't",
                 [like("F2", c="F5"), like("B2", c="B5"), unlike("R2", c="R5")], SWAP_EDGES),
            Case("ye_turn", "fewer than two edges match: turn the top", [], TURN_TOP, priority=-1),
        ]),
        Stage("CornersPlaced", "yellow corners placed", PLACED, [
            Case("cp_one", "the front-right corner is in place, twisted or not", PLACED, CYCLE_CORNERS),
            Case("cp_none", "no corner is in place", [], CYCLE_CORNERS, priority=-1),
        ]),
        # the whole cube: the corners' twists also put the bottom back
        Stage("CornersOriented", "yellow corners oriented",
              [like("U8", c="U5"), like("U9", c="U5"), like("D2", c="D5"), like("D3", c="D5")]
              + [like(f"F{i}", c="F5") for i in (1, 2, 3, 4, 6, 7, 8, 9)], [
            Case("co_all", "orient every corner, then align the top", [], ORIENT_CORNERS),
        ]),
    ]


# --- output -----------------------------------------------------------------------

def emit_need(out: list[str], name: str, need) -> None:
    ats, kind, centre = need
    out.append(f"{name} rk:at {', '.join('rpos:' + a for a in ats)} ; rk:{kind} rpos:{centre} .")


def emit_needs(out: list[str], owner: str, prop: str, needs) -> str:
    """Emit `owner`'s needs, named after it; returns the property clause, or ""."""
    names = [f"need:{owner}_{i}" for i in range(len(needs))]
    for nn, need in zip(names, needs):
        emit_need(out, nn, need)
    return f" {prop} {', '.join(names)} ;" if names else ""


def emit_proc(out: list[str], proc: Proc, done: set) -> None:
    """A procedure, and the procedures and loops it uses (each once)."""
    if proc.name in done:
        return
    done.add(proc.name)
    items = []
    for i, step in enumerate(proc.steps):
        if isinstance(step, str):
            items.append(f"rmv:{step}")
        elif isinstance(step, Proc):
            emit_proc(out, step, done)
            items.append(f"proc:{step.name}")
        elif isinstance(step, Repeat):
            emit_proc(out, step.do, done)
            out.append(f"step:{step.name} a pl:Repeat ; pl:times {step.times} ; pl:do proc:{step.do.name} .")
            items.append(f"step:{step.name}")
        else:
            emit_proc(out, step.do, done)
            when = emit_needs(out, step.name, "pl:until", step.until)
            out.append(f"step:{step.name} a pl:Until ;{when} pl:do proc:{step.do.name} .")
            items.append(f"step:{step.name}")
    # the list nodes are named, since knowledge can't have blank nodes
    first = f"steps:{proc.name}_0" if items else "rdf:nil"
    out.append(f"proc:{proc.name} a pl:Procedure ; rdfs:label \"{proc.label}\" ; pl:steps {first} .")
    for i, item in enumerate(items):
        rest = f"steps:{proc.name}_{i + 1}" if i + 1 < len(items) else "rdf:nil"
        out.append(f"steps:{proc.name}_{i} rdf:first {item} ; rdf:rest {rest} .")


def main() -> None:
    all_stages = stages()
    out = [PREFIXES, "# Generated by gen_method.py: do not edit by hand.\n"]
    views = ", ".join(f"frame:f{f}" for f in sorted(frames()))
    out.append(f"rk:beginnerMethod a pl:Method ; rdfs:label \"beginner method (layer by layer)\" ;\n"
               f"  pl:firstStage stage:{all_stages[0].name} ; pl:view {views} .\n")

    out.append("# --- stages ------------------------------------------------------------------")
    for i, st in enumerate(all_stages):
        nxt = f" pl:next stage:{all_stages[i + 1].name} ;" if i + 1 < len(all_stages) else ""
        goal = emit_needs(out, f"{st.name}Goal", "pl:goal", st.goal)
        out.append(f"stage:{st.name} a pl:Stage ; rdfs:label \"{st.label}\" ;{nxt}{goal[:-2]} .")

    done: set = set()
    for i, st in enumerate(all_stages):
        title = f"stage {i + 1}: {st.label}"
        out.append(f"\n# --- {title} " + "-" * (72 - len(title)))
        for case in st.cases:
            emit_proc(out, case.do, done)
            when = emit_needs(out, case.name, "pl:when", case.needs)
            prio = f" pl:priority {case.priority} ;" if case.priority else ""
            out.append(f"case:{case.name} a pl:Case ; pl:stage stage:{st.name} ; rdfs:label \"{case.label}\" ;"
                       f"{when}{prio} pl:do proc:{case.do.name} .")
        print(f"{st.name}: {len(st.cases)} cases")

    (HERE / "method.ttl").write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
