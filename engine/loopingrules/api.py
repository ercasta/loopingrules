"""HTTP + WebSocket API around one Engine (one project per server).

All mutations go through `Session._mutate`, which bumps the version, records which
triples changed (for UI highlighting) and broadcasts a `sheet-changed` event.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from rdflib import RDF, BNode, Graph, Literal, URIRef
from rdflib.namespace import XSD
from rdflib.util import from_n3

from .engine import Engine
from .operations import Application
from .project import GEN, Project
from .store import prepared, prologue
from .package import PackageError, declared, export_bytes, read_manifest
from .security import check_query
from .suggest import Suggester
from .trust import TemplateError, TrustStore, generalize

UI_DIST = Path(__file__).resolve().parents[2] / "ui" / "dist"


# ---------------------------------------------------------------- terms

class Terms:
    """Term <-> JSON, with short stable labels for blank nodes."""

    def __init__(self, g: Graph):
        self.g = g
        self.bnodes: dict[BNode, str] = {}

    def short(self, t) -> str:
        if isinstance(t, BNode):
            return self.bnodes.setdefault(t, f"_:b{len(self.bnodes) + 1}")
        if isinstance(t, URIRef) and t == RDF.type:
            return "a"
        return t.n3(self.g.namespace_manager)

    def term(self, t) -> dict:
        minted = isinstance(t, URIRef) and str(t).startswith(str(GEN))
        kind = "bnode" if isinstance(t, BNode) or minted else "literal" if isinstance(t, Literal) else "uri"
        out = {"n3": t.n3(), "short": self.short(t), "kind": kind}
        if isinstance(t, Literal):
            out["value"] = str(t)
            if t.datatype:
                out["datatype"] = self.g.namespace_manager.normalizeUri(t.datatype)
        return out

    def typable(self, t) -> str:
        """The form a user would type to get exactly this term back from `parse`."""
        if isinstance(t, Literal):
            if t.datatype in (XSD.integer, XSD.decimal, XSD.boolean):
                return str(t).lower() if t.datatype == XSD.boolean else str(t)
            if (t.datatype in (None, XSD.string)) and not t.language:
                return json.dumps(str(t), ensure_ascii=False)
        return self.short(t)

    def triple(self, t, changed: set | None = None) -> dict:
        k = key(t)
        return {"key": k, "s": self.term(t[0]), "p": self.term(t[1]), "o": self.term(t[2]),
                "changed": bool(changed and k in changed)}

    def parse(self, text: str):
        """Parse a user-typed term: <iri>, prefix:name, a, "literal"(@lang|^^dt), number, true/false, _:bN."""
        s = text.strip()
        if not s:
            raise ValueError("empty term")
        if s == "a":
            return RDF.type
        if s.startswith("_:") and len(s) > 2:
            # user-typed blank node labels become stable minted names (journal-safe)
            return GEN["u_" + re.sub(r"[^A-Za-z0-9_-]", "_", s[2:])]
        if s.startswith("_:"):
            for node, label in self.bnodes.items():
                if label == s:
                    return node
            return from_n3(s)
        if s.startswith(("<", '"')):
            return from_n3(s, nsm=self.g.namespace_manager)
        if s in ("true", "false"):
            return Literal(s == "true")
        if re.fullmatch(r"[+-]?\d+", s):
            return Literal(int(s), datatype=XSD.integer)
        if re.fullmatch(r"[+-]?\d*\.\d+", s):
            return Literal(s, datatype=XSD.decimal)
        if ":" in s:
            try:
                return self.g.namespace_manager.expand_curie(s)
            except ValueError as e:
                raise ValueError(f"unknown prefix in {s!r}") from e
        return Literal(s)  # bare word -> plain string


def key(t) -> str:
    return " ".join(x.n3() for x in t)


# ---------------------------------------------------------------- session

class Session:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.terms = Terms(engine.sheet)
        self.version = 0
        self.tick = 0
        self.changed: set[str] = set()
        self.removed: list[dict] = []
        self.lock = asyncio.Lock()
        self.sockets: set[WebSocket] = set()
        self.autopilot_task: asyncio.Task | None = None
        self.autopilot_status = "idle"  # idle | running | awaiting-approval | done
        self.delay = 0.4
        self.approval_event = asyncio.Event()
        self.log: list[dict] = []
        self._apps: tuple[int, list[Application]] | None = None

    # --- events --------------------------------------------------------
    async def broadcast(self, event: dict) -> None:
        for ws in list(self.sockets):
            try:
                await ws.send_json(event)
            except Exception:
                self.sockets.discard(ws)

    def _log(self, kind: str, text: str, **extra) -> dict:
        entry = {"n": len(self.log) + 1, "kind": kind, "text": text, "tick": self.tick, **extra}
        self.log.append(entry)
        del self.log[:-200]
        return entry

    async def _mutate(self, fn: Callable, log: dict | None = None):
        g = self.engine.sheet
        async with self.lock:
            before = set(g)
            result = await asyncio.to_thread(fn)
            after = set(g)
        inserted, deleted = after - before, before - after
        if inserted or deleted:
            self.version += 1
            self.changed = {key(t) for t in inserted}
            self.removed = [self.terms.triple(t) for t in deleted]
        await self.broadcast({"type": "sheet-changed", "version": self.version,
                              "inserted": len(inserted), "deleted": len(deleted), "log": log})
        return result

    # --- applications --------------------------------------------------
    async def applications(self) -> list[Application]:
        if self._apps and self._apps[0] == self.version:
            return self._apps[1]
        async with self.lock:
            apps = await asyncio.to_thread(self.engine.applications)
        self._apps = (self.version, apps)
        return apps

    def app_json(self, a: Application) -> dict:
        t = self.terms
        return {
            "id": a.id, "operation": a.operation.name,
            "bindings": {k: t.term(v) for k, v in sorted(a.bindings.items())},
            "deletes": [t.triple(x) for x in sorted(a.deletes, key=key)],
            "inserts": [t.triple(x) for x in sorted(a.inserts, key=key)],
            "valid": a.valid, "violations": a.violations,
            "scores": a.scores, "total": a.total, "noop": a.noop,
        }

    # --- autopilot -----------------------------------------------------
    async def _set_status(self, status: str) -> None:
        self.autopilot_status = status
        await self.broadcast({"type": "autopilot", "status": status, "tick": self.tick})

    async def step(self) -> str:
        result = await self._mutate(self.engine.step)
        if result.status == "applied":
            self.tick += 1
            a = result.application
            entry = self._log("tick", a.operation.name, score=a.total,
                              bindings={k: self.terms.short(v) for k, v in a.bindings.items()})
            await self.broadcast({"type": "tick", "tick": self.tick, "entry": entry})
        elif result.status == "stopped":
            a = result.application
            entry = self._log("info", f"autopilot stopped: {a.operation.name} won", score=a.total,
                              bindings={k: self.terms.short(v) for k, v in a.bindings.items()})
            await self.broadcast({"type": "log", "entry": entry})
        elif result.status == "awaiting-approval":
            await self.broadcast({"type": "approval-needed"})
        return result.status

    async def _autopilot(self) -> None:
        try:
            await self._set_status("running")
            while True:
                status = await self.step()
                if status in ("done", "stopped"):
                    if status == "done":
                        self._log("info", "autopilot done: no applicable operations")
                    await self._set_status("done")
                    return
                if status == "awaiting-approval":
                    await self._set_status("awaiting-approval")
                    self.approval_event.clear()
                    await self.approval_event.wait()
                    await self._set_status("running")
                    continue
                await asyncio.sleep(self.delay)
        except asyncio.CancelledError:
            await self._set_status("idle")
            raise

    def start(self) -> None:
        if not (self.autopilot_task and not self.autopilot_task.done()):
            self.autopilot_task = asyncio.create_task(self._autopilot())

    async def stop(self) -> None:
        if self.autopilot_task and not self.autopilot_task.done():
            self.autopilot_task.cancel()
            try:
                await self.autopilot_task
            except asyncio.CancelledError:
                pass

    # --- approvals -----------------------------------------------------
    async def resolve(self, call_id: str, approve: bool) -> None:
        call = next((c for c in self.engine.pending_calls() if self.terms.short(c.iri) == call_id
                     or c.iri.n3() == call_id), None)
        if call is None:
            raise KeyError(call_id)
        entry = self._log("tool", call.command, approved=approve)
        await self._mutate(lambda: self.engine.resolve(call.iri.n3(), approve), log=entry)
        if not self.engine.pending_calls():
            self.approval_event.set()

    async def run_trusted(self) -> None:
        """Run pending calls that now match a trust rule (e.g. right after adding one)."""
        await self._mutate(self.engine.tool_phase)
        if not self.engine.pending_calls():
            self.approval_event.set()


# ---------------------------------------------------------------- app

class TripleIn(BaseModel):
    s: str
    p: str
    o: str


class Decision(BaseModel):
    id: str
    approve: bool
    remember: str | None = None  # a template to trust from now on


class TemplateIn(BaseModel):
    template: str


class AutopilotIn(BaseModel):
    delay_ms: int | None = None


def create_app(project_path: str | Path, trust_path: str | Path | None = None) -> FastAPI:
    engine = Engine(Project.load(project_path))
    session = Session(engine)
    trust = TrustStore(project_path, trust_path)
    manifest = read_manifest(Path(project_path))
    app = FastAPI(title="LoopingRules")
    app.state.session = session

    def trusted(call):
        """Approver: run calls matching a trust rule, leave the rest pending."""
        rule = trust.match(call.command)
        if rule is None:
            return None
        session._log("tool", call.command, approved=True, rule=rule.template)
        return True

    engine.approver = trusted

    def trust_json():
        return [{"id": r.id, "template": r.template} for r in trust.rules()]

    def to_triple(body: TripleIn):
        try:
            return tuple(session.terms.parse(x) for x in (body.s, body.p, body.o))
        except Exception as e:
            raise HTTPException(400, str(e))

    @app.get("/api/state")
    async def state():
        return {
            "project": str(Path(project_path).name),
            "package": None if manifest is None else {"title": manifest.title, "version": manifest.version},
            "version": session.version, "tick": session.tick,
            "autopilot": session.autopilot_status, "delay_ms": int(session.delay * 1000),
            "pending": [{"id": session.terms.short(c.iri), "tool": "shell", "command": c.command,
                         "suggested": generalize(c.command),
                         "declared": declared(manifest, c.command)}
                        for c in engine.pending_calls()],
            "trust": trust_json(),
            "operations": [o.name for o in engine.operations],
            "controllers": [{"name": c.name, "active": c.active, "weight": c.weight,
                             "query": c.query.strip(), "layer": c.layer}
                            for c in engine.controllers],
            "log": session.log[-50:],
            "undo": _undo_label(engine.project.last_undoable()),
            "journal": len(engine.project.journal),
        }

    @app.get("/api/sheet")
    async def sheet():
        g = engine.sheet
        async with session.lock:
            violations = await asyncio.to_thread(engine.sheet_violations)
        def order(t):  # named subjects first, then blank nodes in creation order
            s = t[0]
            sub = (1, int(session.terms.short(s)[3:])) if isinstance(s, BNode) else (0, session.terms.short(s))
            return (sub, session.terms.short(t[1]), key(t))

        triples = sorted(g, key=order)
        nsm = g.namespace_manager
        return {
            "version": session.version,
            "prefixes": {p: str(ns) for p, ns in nsm.namespaces() if p != "xml"},
            "triples": [session.terms.triple(t, session.changed) for t in triples],
            "removed": session.removed,
            "violations": [{**v, "focus": _short_n3(session, v["focus"])} for v in violations],
        }

    @app.get("/api/suggest")
    async def suggest(field: str, s: str = "", p: str = "", q: str = ""):
        """Autocomplete for the add-row, derived from the SHACL shapes (D15)."""
        g, t = engine.sheet, session.terms
        sug = Suggester(engine.shapes, g)

        def term_or_none(text: str):
            try:
                return t.parse(text) if text.strip() else None
            except Exception:
                return None

        subject, predicate = term_or_none(s), term_or_none(p)
        items: list[dict] = []
        constraint: dict = {}
        missing: list[dict] = []
        hint = None
        if field == "s":
            for subj in sorted(set(g.subjects()), key=lambda x: (isinstance(x, BNode), t.short(x))):
                types = ", ".join(sorted(t.short(c) for c in g.objects(subj, RDF.type)))
                items.append({"value": t.typable(subj), "hint": types or "untyped"})
        elif field == "p":
            seen = set()
            if subject is not None:
                for x in sug.predicates(subject):
                    seen.add(x["term"])
                    entry = {"value": t.typable(x["term"]), "hint": x["hint"], "status": x["status"]}
                    items.append(entry)
                    if x["status"] == "missing":
                        missing.append(entry)
            for pred in sorted(set(g.predicates()) - seen, key=t.short):
                items.append({"value": t.typable(pred), "hint": "used in the sheet"})
        elif field == "o" and predicate is not None:
            r = sug.objects(subject, predicate)
            items = [{"value": t.typable(x["term"]), "hint": x["hint"]} for x in r["values"]]
            constraint, hint = r["constraint"], r.get("hint")
        else:
            raise HTTPException(400, "field must be s, p or o (o needs p)")
        if q.strip():
            ql = q.strip().lower()
            items = [i for i in items if ql in i["value"].lower()]
        return {"items": items[:60], "constraint": constraint, "missing": missing, "hint": hint}

    @app.post("/api/sheet/triples")
    async def add_triple(body: TripleIn):
        t = to_triple(body)
        entry = session._log("edit", f"+ {' '.join(session.terms.short(x) for x in t)}")
        await session._mutate(lambda: engine.edit(add=[t]), log=entry)
        return {"version": session.version}

    @app.post("/api/sheet/delete")
    async def delete_triple(body: TripleIn):
        try:
            t = tuple(from_n3(x) for x in (body.s, body.p, body.o))
        except Exception as e:
            raise HTTPException(400, str(e))
        if t not in engine.sheet:
            raise HTTPException(404, "no such triple")
        entry = session._log("edit", f"− {' '.join(session.terms.short(x) for x in t)}")
        await session._mutate(lambda: engine.edit(remove=[t]), log=entry)
        return {"version": session.version}

    @app.get("/api/applications")
    async def applications(contains: str | None = None):
        apps = await session.applications()
        if contains and contains.strip():
            q = prologue(engine.project.model, engine.sheet) + f"ASK {{ {contains} }}"
            try:
                check_query(q, "filter")
                apps = [a for a in apps if a.valid and bool(engine.resulting_state(a).query(prepared(q)).askAnswer)]
            except Exception as e:
                raise HTTPException(400, f"bad pattern: {e}")
        return {"version": session.version, "applications": [session.app_json(a) for a in apps]}

    @app.post("/api/apply/{app_id}")
    async def apply(app_id: str):
        a = next((a for a in await session.applications() if a.id == app_id), None)
        if a is None:
            raise HTTPException(404, "application not found (sheet changed?)")
        if not a.valid:
            raise HTTPException(409, "application is invalid")
        if a.noop:  # choosing to stop: nothing changes, but the choice is logged (D21)
            entry = session._log("info", f"stop chosen: {a.operation.name}", score=a.total, manual=True,
                                 bindings={k: session.terms.short(v) for k, v in a.bindings.items()})
            await session.broadcast({"type": "log", "entry": entry})
            return {"version": session.version}
        session.tick += 1
        entry = session._log("tick", a.operation.name, score=a.total, manual=True,
                             bindings={k: session.terms.short(v) for k, v in a.bindings.items()})
        await session._mutate(lambda: engine.apply(a), log=entry)
        await session.broadcast({"type": "tick", "tick": session.tick, "entry": entry})
        return {"version": session.version}

    @app.post("/api/autopilot/start")
    async def autopilot_start(body: AutopilotIn | None = None):
        if body and body.delay_ms is not None:
            session.delay = max(0, body.delay_ms) / 1000
        session.start()
        return {"status": "running"}

    @app.post("/api/autopilot/stop")
    async def autopilot_stop():
        await session.stop()
        return {"status": session.autopilot_status}

    @app.post("/api/autopilot/step")
    async def autopilot_step():
        return {"status": await session.step()}

    @app.post("/api/approvals")
    async def decide(body: Decision):
        if body.remember:
            if not body.approve:
                raise HTTPException(400, "only approvals can be remembered")
            try:
                trust.add(body.remember)
            except TemplateError as e:
                raise HTTPException(400, str(e))
        try:
            await session.resolve(body.id, body.approve)
        except KeyError:
            raise HTTPException(404, "no such pending call")
        if body.remember:
            await session.run_trusted()
        return {"version": session.version}

    @app.get("/api/trust")
    async def trust_list():
        return {"rules": trust_json(), "file": str(trust.path)}

    @app.post("/api/trust")
    async def trust_add(body: TemplateIn):
        try:
            rule = trust.add(body.template)
        except TemplateError as e:
            raise HTTPException(400, str(e))
        await session.run_trusted()
        return {"id": rule.id, "template": rule.template}

    @app.delete("/api/trust/{rule_id}")
    async def trust_remove(rule_id: str):
        try:
            trust.remove(rule_id)
        except KeyError:
            raise HTTPException(404, "no such rule")
        await session.broadcast({"type": "trust-changed"})
        return {"rules": trust_json()}

    @app.post("/api/controllers/{name}/toggle")
    async def toggle(name: str):
        c = next((c for c in engine.controllers if c.name == name), None)
        if c is None:
            raise HTTPException(404, "no such controller")
        c.active = not c.active
        session._apps = None
        await session.broadcast({"type": "controllers-changed"})
        return {"active": c.active}

    @app.get("/api/export")
    async def export(sheet: str = "seed"):
        if sheet not in ("seed", "state", "none"):
            raise HTTPException(400, "sheet must be seed, state or none")
        try:
            name, data = export_bytes(project_path, sheet, engine.sheet if sheet == "state" else None)
        except PackageError as e:
            raise HTTPException(400, str(e))
        return Response(data, media_type="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="{name}"'})

    @app.post("/api/undo")
    async def undo():
        if session.autopilot_status in ("running", "awaiting-approval"):
            raise HTTPException(409, "stop autopilot before undoing")
        tx = engine.project.last_undoable()
        if tx is None:
            raise HTTPException(404, "nothing to undo")
        entry = session._log("undo", f"undo {tx.headers.get('kind', '')} {tx.headers.get('label', '')}".strip())
        await session._mutate(engine.undo, log=entry)
        return {"version": session.version}

    @app.post("/api/project/save")
    async def save():
        snap = engine.project.snapshot()
        return {"saved": str(snap) if snap else None, "journal": len(engine.project.journal)}

    @app.websocket("/api/events")
    async def events(ws: WebSocket):
        await ws.accept()
        session.sockets.add(ws)
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            session.sockets.discard(ws)

    if UI_DIST.exists():
        app.mount("/assets", StaticFiles(directory=UI_DIST / "assets"), name="assets")

        @app.get("/")
        async def index():
            return FileResponse(UI_DIST / "index.html")

    return app


def _undo_label(tx) -> str | None:
    if tx is None:
        return None
    return f"{tx.headers.get('kind', 'change')}: {tx.headers.get('label', '')}".strip(": ")


def _short_n3(session: Session, n3: str | None) -> str | None:
    if not n3:
        return n3
    try:
        return session.terms.short(from_n3(n3, nsm=session.engine.sheet.namespace_manager))
    except Exception:
        return n3
