"""Sharing projects and packs as export files (*.lr.zip).

An export is a flat zip:

    package.ttl       manifest: title, version, description, creator, license,
                      lr:mayRun (the command templates it may ask to run), lr:extends
    *.ttl             definitions and knowledge, sorted by type (design D28):
                      usually model.ttl, controllers.ttl, knowledge.ttl
    sheet.ttl         optional: a seed sheet (never in a pack)
    README.md         optional

Never included: the runtime state (.lr/) and trust rules (they belong to the user).

A *pack* declares lr:extends "<title>" (the base project's, or an installed pack's).
It may carry anything but a sheet: operations, shapes, controllers, knowledge. It
is installed into an existing project with add_layer, into layers/<title>/, and
refused if it conflicts with what is already there.

Importing is defensive: flat simple file names only, size limits, every file must
parse, knowledge may not use blank nodes, every query must pass the security check
(no SERVICE / FROM) and the operation subset (D23), and every declared command
template must be a valid trust template. Nothing is trusted automatically.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from rdflib import RDF, Graph, Literal, Namespace, URIRef

import re

from .controllers import load_controllers
from .definitions import source
from .operations import load_operations
from .trust import compile_template
from .vocab import LR

DCT = Namespace("http://purl.org/dc/terms/")
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}[.]ttl|README[.]md")  # flat, simple names only
MAX_FILE = 5 * 1024 * 1024
MAX_TOTAL = 20 * 1024 * 1024
SUFFIX = ".lr.zip"


class PackageError(ValueError):
    pass


@dataclass
class Manifest:
    title: str
    version: str = "0.0.0"
    description: str = ""
    creator: str = ""
    license: str = ""
    may_run: list[str] = field(default_factory=list)
    extends: str | None = None
    direct_edits: bool = True  # lr:directEdits false = app mode (D25)

    @classmethod
    def from_graph(cls, g: Graph, fallback_title: str) -> "Manifest":
        pkg = next(iter(g.subjects(RDF.type, LR.Package)), None)
        if pkg is None:
            return cls(title=fallback_title)
        v = lambda p: str(g.value(pkg, p) or "")  # noqa: E731
        return cls(title=v(DCT.title) or fallback_title, version=v(LR.version) or "0.0.0",
                   description=v(DCT.description), creator=v(DCT.creator), license=v(DCT.license),
                   may_run=sorted(str(x) for x in g.objects(pkg, LR.mayRun)),
                   extends=str(g.value(pkg, LR.extends)) if g.value(pkg, LR.extends) is not None else None,
                   direct_edits=str(g.value(pkg, LR.directEdits, default="true")).lower() != "false")

    def to_graph(self) -> Graph:
        g = Graph()
        g.bind("lr", LR)
        g.bind("dcterms", DCT)
        pkg = URIRef("urn:lr:package")
        g.add((pkg, RDF.type, LR.Package))
        g.add((pkg, DCT.title, Literal(self.title)))
        g.add((pkg, LR.version, Literal(self.version)))
        for p, val in ((DCT.description, self.description), (DCT.creator, self.creator), (DCT.license, self.license)):
            if val:
                g.add((pkg, p, Literal(val)))
        for t in self.may_run:
            g.add((pkg, LR.mayRun, Literal(t)))
        if self.extends:
            g.add((pkg, LR.extends, Literal(self.extends)))
        if not self.direct_edits:
            g.add((pkg, LR.directEdits, Literal(False)))
        return g


def read_manifest(project: Path) -> Manifest | None:
    """The lr:Package in any of the folder's *.ttl files but sheet.ttl (D28), or None."""
    g = Graph()
    for f in sorted(Path(project).glob("*.ttl")):
        if f.name != "sheet.ttl":
            g.parse(f, format="turtle")
    if next(iter(g.subjects(RDF.type, LR.Package)), None) is None:
        return None
    return Manifest.from_graph(g, Path(project).name)


def declared(manifest: "Manifest | list[Manifest | None] | None", command: str) -> bool | None:
    """Does the package (or any of the packages) declare this command? None without a manifest."""
    manifests = [m for m in (manifest if isinstance(manifest, list) else [manifest]) if m is not None]
    if not manifests:
        return None
    return any(compile_template(t).match(command.strip()) for m in manifests for t in m.may_run)


def manifests(project: str | Path) -> list[Manifest]:
    """The project's manifest and those of its installed packs."""
    p = Path(project)
    found = [read_manifest(p)]
    layers = p / "layers"
    if layers.is_dir():
        found += [read_manifest(d) for d in sorted(layers.iterdir()) if d.is_dir()]
    return [m for m in found if m is not None]


# ---------------------------------------------------------------- export

def export_project(project: str | Path, out: str | Path | None = None, sheet: str = "seed",
                   state_sheet: Graph | None = None) -> Path:
    """Write an export. sheet: "seed" (the authored sheet.ttl), "state" (state_sheet), or "none"."""
    p = Path(project)
    manifest = read_manifest(p) or Manifest(title=p.name)
    if manifest.extends:
        sheet = "none"  # a pack carries no state
    files: dict[str, bytes] = {}
    files["package.ttl"] = manifest.to_graph().serialize(format="turtle").encode()
    for f in sorted(p.glob("*.ttl")):
        if f.name not in ("package.ttl", "sheet.ttl"):
            files[f.name] = f.read_bytes()
    if (p / "README.md").exists():
        files["README.md"] = (p / "README.md").read_bytes()
    if not any(n not in ("package.ttl", "README.md", "sheet.ttl") for n in files):
        raise PackageError(f"{p} has nothing to share: no definitions or knowledge (*.ttl)")
    if sheet == "seed" and (p / "sheet.ttl").exists():
        files["sheet.ttl"] = (p / "sheet.ttl").read_bytes()
    elif sheet == "state":
        if state_sheet is None:
            raise PackageError("no state sheet given")
        files["sheet.ttl"] = state_sheet.serialize(format="turtle").encode()
    _check(files)  # never export something we would refuse to import
    target = Path(out) if out else p.parent / f"{manifest.title}-{manifest.version}{SUFFIX}"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    return target


def export_bytes(project: str | Path, sheet: str = "seed", state_sheet: Graph | None = None) -> tuple[str, bytes]:
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        path = export_project(project, Path(d) / "out.zip", sheet, state_sheet)
        manifest = read_manifest(Path(project)) or Manifest(title=Path(project).name)
        return f"{manifest.title}-{manifest.version}{SUFFIX}", path.read_bytes()


# ---------------------------------------------------------------- import

def inspect_export(data: bytes) -> tuple[Manifest, dict[str, bytes]]:
    """Read and validate an export without writing anything."""
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise PackageError("not a zip file") from e
    files: dict[str, bytes] = {}
    total = 0
    for info in z.infolist():
        if info.is_dir():
            raise PackageError(f"unexpected folder in export: {info.filename}")
        if not NAME.fullmatch(info.filename):
            raise PackageError(f"unexpected file in export: {info.filename!r} "
                               "(allowed: flat *.ttl files with simple names, and README.md)")
        if info.file_size > MAX_FILE:
            raise PackageError(f"{info.filename} is too large")
        total += info.file_size
        if total > MAX_TOTAL:
            raise PackageError("export is too large")
        content = z.read(info)
        if len(content) > MAX_FILE:  # don't trust the header alone
            raise PackageError(f"{info.filename} is too large")
        files[info.filename] = content
    manifest = _check(files)
    return manifest, files


def _check(files: dict[str, bytes]) -> Manifest:
    graphs = {}
    for name, data in files.items():
        if name.endswith(".ttl"):
            try:
                graphs[name] = Graph().parse(data=data.decode("utf-8"), format="turtle")
            except Exception as e:
                raise PackageError(f"{name} does not parse: {e}") from e
    manifest = Manifest.from_graph(graphs.get("package.ttl", Graph()), "unnamed")
    content = [n for n in graphs if n not in ("package.ttl", "sheet.ttl")]
    if manifest.extends and "sheet.ttl" in files:
        raise PackageError("a pack carries no state: sheet.ttl is not allowed in a pack")
    if not content:
        raise PackageError("the export has no definitions or knowledge (*.ttl besides package.ttl)")
    merged = Graph()
    for n in content + (["package.ttl"] if "package.ttl" in graphs else []):
        for prefix, ns in graphs[n].namespaces():
            merged.bind(prefix, ns, override=False)
        merged += graphs[n]
    try:
        src = source(manifest.title, manifest.extends and manifest.title, merged)  # refuses blank-node knowledge
        load_operations(src.definitions)  # includes the SERVICE / FROM check and the D23 subset
        load_controllers(src.definitions)
    except ValueError as e:
        raise PackageError(str(e)) from e
    for t in manifest.may_run:
        try:
            compile_template(t)
        except ValueError as e:
            raise PackageError(f"declared command {t!r} is not a valid template: {e}") from e
    return manifest


def import_export(data: bytes, dest: str | Path) -> Manifest:
    manifest, files = inspect_export(data)
    if manifest.extends:
        raise PackageError(f"{manifest.title} is a pack for '{manifest.extends}': "
                           f"add it to a project with: lr add-layer <file> <project>")
    d = Path(dest)
    if d.exists() and any(d.iterdir()):
        raise PackageError(f"{d} already exists and is not empty")
    d.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (d / name).write_bytes(content)
    return manifest


def add_layer(data: bytes, project: str | Path) -> Manifest:
    """Install a pack into an existing project, in layers/<title>/ (design D28).

    The pack must extend the project or a pack already installed in it, and must not
    conflict with what is there: it is removed again if the project no longer loads.
    """
    import shutil

    from .engine import Engine
    from .project import Project

    manifest, files = inspect_export(data)
    if not manifest.extends:
        raise PackageError(f"{manifest.title} is not a pack (it has no lr:extends)")
    p = Path(project)
    base = read_manifest(p)
    installed = {m.title for m in manifests(p)} - ({base.title} if base else set())
    if (base is None or base.title != manifest.extends) and manifest.extends not in installed:
        found = f"'{base.title}'" if base else "a project without package.ttl"
        raise PackageError(f"{manifest.title} extends '{manifest.extends}', but {p} is {found}"
                           + (f" with packs {', '.join(sorted(installed))}" if installed else ""))
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_. -]{0,63}", manifest.title) or ".." in manifest.title:
        raise PackageError(f"pack title {manifest.title!r} can't be used as a folder name")
    target = p / "layers" / manifest.title
    if target.exists():
        raise PackageError(f"layer {manifest.title} is already installed (delete {target} to replace it)")
    target.mkdir(parents=True)
    for name, content in files.items():
        (target / name).write_bytes(content)
    try:
        Engine(Project.load(p, persist=False))
    except ValueError as e:
        shutil.rmtree(target)
        raise PackageError(f"{manifest.title} doesn't fit this project: {e}") from e
    return manifest
