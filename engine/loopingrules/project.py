"""A project is a folder of authored files plus runtime state.

Authored (never rewritten by the engine):
    sheet.ttl         the seed state
    model.ttl         SHACL shapes + lr:Operations
    controllers.ttl   lr:Controllers
    package.ttl       optional manifest, used when sharing (see package.py)

Runtime state, in .lr/ (delete it to reset the project):
    history.rdfp      append-only journal, one transaction per change (RDF Patch style)
    snapshot.ttl      the sheet after the first N transactions; first line "# lr:snapshot-tx N"

Loading = snapshot (or seed) + replay of the journal transactions after it.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from rdflib import BNode, Graph, Namespace

from .vocab import LR

FILES = ("sheet", "model", "controllers")
STATE_DIR = ".lr"
SNAPSHOT_EVERY = 100

# Minted names for things the engine creates (instead of blank nodes, whose
# labels do not survive a reload and so cannot be referenced by the journal).
GEN = Namespace("urn:lr:gen:")


def mint():
    return GEN[secrets.token_hex(4)]


def skolemize(g: Graph) -> None:
    """Replace every blank node in g with a minted IRI, in place."""
    mapping: dict[BNode, object] = {}
    sub = lambda t: mapping.setdefault(t, mint()) if isinstance(t, BNode) else t  # noqa: E731
    for t in [t for t in g if any(isinstance(x, BNode) for x in t)]:
        g.remove(t)
        g.add(tuple(sub(x) for x in t))


def _load(path: Path) -> Graph:
    g = Graph()
    g.bind("lr", LR)
    if path.exists():
        g.parse(path, format="turtle")
    return g


@dataclass
class Transaction:
    n: int
    added: list = field(default_factory=list)
    deleted: list = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)


def _write_tx(f, tx: Transaction) -> None:
    f.write("TX .\n")
    for k, v in tx.headers.items():
        f.write(f'H {k} "{_esc(v)}" .\n')
    for t in tx.deleted:
        f.write("D " + " ".join(x.n3() for x in t) + " .\n")
    for t in tx.added:
        f.write("A " + " ".join(x.n3() for x in t) + " .\n")
    f.write("TC .\n")


def _esc(s: str) -> str:
    return str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _unesc(s: str) -> str:
    return s.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")


def _parse_triple(rest: str):
    # rest is "<s> <p> <o> ." written by _write_tx; parse it as one N-Triples line
    g = Graph()
    g.parse(data=rest, format="nt")
    return next(iter(g))


def read_journal(path: Path) -> list[Transaction]:
    txs: list[Transaction] = []
    if not path.exists():
        return txs
    cur: Transaction | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("TX"):
            cur = Transaction(len(txs))
        elif line.startswith("TC") and cur is not None:
            txs.append(cur)
            cur = None
        elif cur is None:
            continue  # incomplete transaction at the end (crash mid-write): ignored
        elif line.startswith("H "):
            key, _, val = line[2:].partition(" ")
            cur.headers[key] = _unesc(val.rstrip(" .").strip('"'))
        elif line.startswith(("A ", "D ")):
            t = _parse_triple(line[2:])
            (cur.added if line[0] == "A" else cur.deleted).append(t)
    return txs


@dataclass
class Project:
    path: Path
    sheet: Graph
    model: Graph
    controllers: Graph
    journal: list[Transaction] = field(default_factory=list)
    snapshot_tx: int = 0
    persist: bool = True

    # --- loading ---------------------------------------------------------
    @classmethod
    def load(cls, path: str | Path, persist: bool = True) -> "Project":
        p = Path(path)
        sheet, model, controllers = (_load(p / f"{name}.ttl") for name in FILES)
        proj = cls(p, sheet, model, controllers, persist=persist)
        proj._restore()
        return proj

    @property
    def state_dir(self) -> Path:
        return self.path / STATE_DIR

    def _restore(self) -> None:
        self.sheet.bind("gen", GEN)
        snap = self.state_dir / "snapshot.ttl"
        if self.persist and snap.exists():
            first = snap.read_text(encoding="utf-8").split("\n", 1)[0]
            if first.startswith("# lr:snapshot-tx "):
                g = _load(snap)
                for prefix, ns in self.sheet.namespaces():
                    g.bind(prefix, ns, override=False)
                self.sheet = g
                self.snapshot_tx = int(first.split()[-1])
        skolemize(self.sheet)
        if not self.persist:
            return
        self.journal = read_journal(self.state_dir / "history.rdfp")
        for tx in self.journal[self.snapshot_tx:]:
            for t in tx.deleted:
                self.sheet.remove(t)
            for t in tx.added:
                self.sheet.add(t)

    # --- recording -------------------------------------------------------
    def record(self, added, deleted, **headers) -> Transaction | None:
        """Append one transaction to the journal (autosave)."""
        added, deleted = list(added), list(deleted)
        if not added and not deleted:
            return None
        tx = Transaction(len(self.journal), added, deleted,
                         {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), **headers})
        self.journal.append(tx)
        if self.persist:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            with open(self.state_dir / "history.rdfp", "a", encoding="utf-8") as f:
                _write_tx(f, tx)
            if len(self.journal) - self.snapshot_tx >= SNAPSHOT_EVERY:
                self.snapshot()
        return tx

    def snapshot(self) -> Path | None:
        """Write the current sheet to .lr/snapshot.ttl (authored files are never touched)."""
        if not self.persist:
            return None
        self.state_dir.mkdir(parents=True, exist_ok=True)
        body = self.sheet.serialize(format="turtle")
        target = self.state_dir / "snapshot.ttl"
        tmp = target.with_suffix(".tmp")
        tmp.write_text(f"# lr:snapshot-tx {len(self.journal)}\n{body}", encoding="utf-8")
        tmp.replace(target)
        self.snapshot_tx = len(self.journal)
        return target

    # --- undo ------------------------------------------------------------
    def last_undoable(self) -> Transaction | None:
        undone = {int(tx.headers["undoes"]) for tx in self.journal if "undoes" in tx.headers}
        for tx in reversed(self.journal):
            if "undoes" in tx.headers or tx.n in undone:
                continue
            return tx
        return None

    def undo(self) -> Transaction | None:
        """Revert the latest change by appending its inverse (the journal stays append-only)."""
        tx = self.last_undoable()
        if tx is None:
            return None
        for t in tx.added:
            self.sheet.remove(t)
        for t in tx.deleted:
            self.sheet.add(t)
        return self.record(tx.deleted, tx.added, kind="undo", undoes=str(tx.n),
                           label=tx.headers.get("label", ""))

