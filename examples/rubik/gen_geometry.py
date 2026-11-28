"""Generate the cube's geometry (knowledge) and the solved seed sheet.

    python examples/rubik/gen_geometry.py

Writes geometry.ttl and sheet.ttl next to this script. Both are committed; run
this again only if the conventions below change.

Conventions
- Axes: x to the right, y up, z towards the viewer (the front).
- Faces and their home colours: U white, D yellow, F green, B blue, R red, L orange.
- Facelets are numbered 1..9 in reading order, each face seen from outside:
  U with B at the top, D with F at the top, F/R/B/L with U at the top.
- A clockwise turn of a face is clockwise seen from outside that face.
"""

from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent

PREFIXES = """\
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix rk:   <https://example.org/rubik#> .
@prefix face: <https://example.org/rubik/face#> .
@prefix pos:  <https://example.org/rubik/pos#> .
@prefix slot: <https://example.org/rubik/slot#> .
@prefix mv:   <https://example.org/rubik/move#> .
@prefix map:  <https://example.org/rubik/map#> .
@prefix frame: <https://example.org/rubik/frame#> .
@prefix rpos: <https://example.org/rubik/rpos#> .
@prefix rmv:  <https://example.org/rubik/rmv#> .
"""

# face: (normal, right, down) as seen from outside, and its home colour
FACES = {
    "U": ((0, 1, 0), (1, 0, 0), (0, 0, 1), "White"),
    "D": ((0, -1, 0), (1, 0, 0), (0, 0, -1), "Yellow"),
    "F": ((0, 0, 1), (1, 0, 0), (0, -1, 0), "Green"),
    "B": ((0, 0, -1), (-1, 0, 0), (0, -1, 0), "Blue"),
    "R": ((1, 0, 0), (0, 0, -1), (0, -1, 0), "Red"),
    "L": ((-1, 0, 0), (0, 0, 1), (0, -1, 0), "Orange"),
}
ORDER = "UDFBRL"  # the order of face letters in slot names (UF, UFR, DBL, ...)


def add(*vs):
    return tuple(sum(c) for c in zip(*vs))


def scale(k, v):
    return tuple(k * c for c in v)


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cw(n, v):
    """Rotate v by -90 degrees around n (clockwise seen from the tip of n)."""
    return add(scale(-1, cross(n, v)), scale(dot(n, v), n))


def facelets():
    """{name: (cubie position, normal)} for the 54 facelets."""
    out = {}
    for f, (n, r, d, _) in FACES.items():
        for i in range(9):
            row, col = divmod(i, 3)
            out[f"{f}{i + 1}"] = (add(n, scale(col - 1, r), scale(row - 1, d)), n)
    return out


def face_of_normal(n):
    return next(f for f, (fn, *_) in FACES.items() if fn == n)


def turn_map(f: str) -> dict[str, str]:
    """A clockwise quarter turn of face f: facelet name -> where its colour goes (centre excluded)."""
    fl = facelets()
    where = {v: k for k, v in fl.items()}
    n = FACES[f][0]
    return {name: where[(cw(n, c), cw(n, normal))] for name, (c, normal) in fl.items()
            if dot(c, n) == 1 and name != f"{f}5"}


def move_names() -> list[str]:
    return [f + s for f in FACES for s in ("", "i", "2")]


def move_map(move: str) -> dict[str, str]:
    """Any move ("R", "Ri", "R2") as a permutation of the 54 positions."""
    quarters = {"": 1, "i": 3, "2": 2}[move[1:]]
    perm = {name: name for name in facelets()}
    step = turn_map(move[0])
    for _ in range(quarters):
        perm = {k: step.get(v, v) for k, v in perm.items()}
    return perm


def rotations():
    """The 24 proper rotations of the cube, as 3x3 integer matrices."""
    import itertools
    out = []
    for perm in itertools.permutations(range(3)):
        for signs in itertools.product((1, -1), repeat=3):
            m = [[0] * 3 for _ in range(3)]
            for i, (j, sgn) in enumerate(zip(perm, signs)):
                m[i][j] = sgn
            det = (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
                   + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))
            if det == 1:
                out.append(m)
    return out


def rotate(m, v):
    return tuple(sum(m[i][j] * v[j] for j in range(3)) for i in range(3))


def frames():
    """The 4 ways to hold the cube with white (absolute U) down, named by the absolute face in front.

    Each frame maps relative names (as the beginner method writes them: white on D) to absolute ones:
    {"pos": {relative facelet: absolute facelet}, "move": {relative move: absolute move}}.
    """
    fl = facelets()
    where = {v: k for k, v in fl.items()}
    out = {}
    for m in rotations():
        if rotate(m, FACES["D"][0]) != FACES["U"][0]:
            continue
        front = face_of_normal(rotate(m, FACES["F"][0]))
        pos = {name: where[(rotate(m, c), rotate(m, n))] for name, (c, n) in fl.items()}
        move = {mv: face_of_normal(rotate(m, FACES[mv[0]][0])) + mv[1:] for mv in move_names()}
        out[front] = {"pos": pos, "move": move}
    assert len(out) == 4
    return out


def main() -> None:
    fl = facelets()
    where = {v: k for k, v in fl.items()}
    out = [PREFIXES, "# Generated by gen_geometry.py: do not edit by hand.\n"]

    out.append("# --- colours and faces ---------------------------------------------------")
    for f, (*_, colour) in FACES.items():
        out.append(f"rk:{colour} a rk:Colour ; rdfs:label \"{colour.lower()}\" .")
    for f, (*_, colour) in FACES.items():
        out.append(f"face:{f} a rk:Face ; rdfs:label \"{f}\" ; rk:homeColour rk:{colour} .")

    out.append("\n# --- facelet positions -----------------------------------------------------")
    for name in fl:
        out.append(f"pos:{name} a rk:Position ; rk:face face:{name[0]} ; rk:index {name[1:]} .")
    for f in FACES:
        out.append(f"face:{f} rk:centre pos:{f}5 .")

    out.append("\n# --- slots: where edge and corner pieces sit; facelets in name order ------")
    cubies: dict[tuple, list[str]] = {}
    for name, (c, _) in fl.items():
        cubies.setdefault(c, []).append(name)
    for c, names in sorted(cubies.items(), key=lambda kv: sorted(kv[1])):
        if len(names) < 2:
            continue
        names.sort(key=lambda nm: ORDER.index(nm[0]))
        sname = "".join(nm[0] for nm in names)
        kind = "rk:EdgeSlot" if len(names) == 2 else "rk:CornerSlot"
        parts = " ; ".join(f"rk:f{i + 1} pos:{nm}" for i, nm in enumerate(names))
        out.append(f"slot:{sname} a {kind} ; {parts} .")

    out.append("\n# --- turns: each clockwise quarter turn of a face moves 20 facelets ------")
    for f, (n, *_rest) in FACES.items():
        k = 0
        for name, (c, normal) in fl.items():
            if dot(c, n) != 1 or name == f"{f}5":
                continue
            k += 1
            target = where[(cw(n, c), cw(n, normal))]
            out.append(f"map:{f}{k:02d} rk:of face:{f} ; rk:from pos:{name} ; rk:to pos:{target} .")
        assert k == 20, (f, k)

    out.append("\n# --- moves: quarter (X), prime (Xi) and double (X2) turns ---------------")
    for f in FACES:
        out.append(f"mv:{f} a rk:Move ; rdfs:label \"{f}\" ; rk:face face:{f} ; rk:dir rk:cw ; rk:inverse mv:{f}i .")
        out.append(f"mv:{f}i a rk:Move ; rdfs:label \"{f}'\" ; rk:face face:{f} ; rk:dir rk:ccw ; rk:inverse mv:{f} .")
        out.append(f"mv:{f}2 a rk:Move ; rdfs:label \"{f}2\" ; rk:face face:{f} ; rk:dir rk:cw ; rk:twice true ; rk:inverse mv:{f}2 .")

    out.append("\n# --- frames: the 4 ways to hold the cube with white down ----------------")
    out.append("# The beginner method is written with white on D. A frame maps its relative")
    out.append("# positions (rpos:) and moves (rmv:) to the absolute ones of this cube.")
    for name in fl:
        out.append(f"rpos:{name} a rk:RelPosition .")
    for mv in move_names():
        label = mv.replace("i", "'")
        out.append(f"rmv:{mv} a rk:RelMove ; rdfs:label \"{label}\" .")
    for front, fr in frames().items():
        out.append(f"frame:f{front} a rk:Frame ; rdfs:label \"white down, {FACES[front][3].lower()} in front\" ;")
        pairs = [f"rpos:{a} pos:{b}" for a, b in fr["pos"].items()] + [f"rmv:{a} mv:{b}" for a, b in fr["move"].items()]
        out.append("  " + " ;\n  ".join(pairs) + " .")

    (HERE / "geometry.ttl").write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")

    sheet = [PREFIXES, "# A solved cube: white up, green front. Generated by gen_geometry.py.\n",
             "rk:cube a rk:Cube ; rk:plan rdf:nil ; rk:turns 0 .\n"]
    for name in fl:
        sheet.append(f"pos:{name} rk:colour rk:{FACES[name[0]][3]} .")
    (HERE / "sheet.ttl").write_text("\n".join(sheet) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
