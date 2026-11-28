"""Try the method on many scrambles in seconds, by emulating the solver's rules in Python.

    python examples/rubik/simulate.py [N]          (default: 300 scrambles)

For designing the method (gen_method.py) quickly. The rules in solver.ttl are what
actually solve the cube, and engine/tests/test_rubik.py tests them; this emulates
them, in the same order:
- a stage ends when its goal holds in every frame (that goes first);
- otherwise, among the cases of the stage whose needs hold in some frame, the
  highest rk:priority wins; ties go to the case, then the frame, in IRI order;
- a stage with rk:sameFrame plans only in the frame the cube is held in.
"""

from __future__ import annotations

import random
import sys

from gen_geometry import facelets, frames, move_map, move_names
from gen_method import stages

MOVES = {m: move_map(m) for m in move_names()}
FRAMES = frames()  # front face -> {"pos": relative -> absolute facelet, "move": relative -> absolute move}
FRAME_ORDER = sorted(FRAMES)  # frame:fB < frame:fF < frame:fL < frame:fR
SOLVED = {p: p[0] for p in facelets()}  # a colour is named by its home face


def turn(state: dict, move: str) -> dict:
    m = MOVES[move]
    return {m[p]: c for p, c in state.items()}


def holds(state: dict, frame: str, need) -> bool:
    ats, kind, centre = need
    pos = FRAMES[frame]["pos"]
    c = state[pos[centre]]
    same = [state[pos[a]] == c for a in ats]
    return any(same) if kind == "like" else not all(same)


def solve(state: dict, method, max_plans: int = 200):
    """(solved?, why, turns, plans)"""
    turns = plans = 0
    frame = None
    for st in method:
        for _ in range(max_plans):
            if all(holds(state, fr, n) for fr in FRAMES for n in st.goal):
                break
            allowed = [frame] if (st.same_frame and frame) else FRAME_ORDER
            matches = [(c, fr) for c in sorted(st.cases, key=lambda c: c.name) for fr in allowed
                       if all(holds(state, fr, n) for n in c.needs)]
            if not matches:
                return False, f"no case matches in stage {st.name}", turns, plans
            case, frame = max(matches, key=lambda m: m[0].priority)  # max keeps the first of equals
            for mv in case.alg:
                state = turn(state, FRAMES[frame]["move"][mv])
                turns += 1
            plans += 1
        else:
            return False, f"no progress in stage {st.name}", turns, plans
    return state == SOLVED, "solved" if state == SOLVED else "not solved", turns, plans


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    method = stages()
    rng = random.Random(1)
    turns, plans, failed = [], [], 0
    for i in range(n):
        state = SOLVED
        for _ in range(25):
            state = turn(state, rng.choice(list(MOVES)))
        ok, why, t, p = solve(state, method)
        turns.append(t)
        plans.append(p)
        if not ok:
            failed += 1
            if failed <= 5:
                print(f"scramble {i}: {why}")
    print(f"{n - failed}/{n} solved; turns {min(turns)}-{max(turns)} (mean {sum(turns) / n:.0f}), "
          f"plans {min(plans)}-{max(plans)} (mean {sum(plans) / n:.0f})")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
