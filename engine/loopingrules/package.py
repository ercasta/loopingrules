"""Sharing models and controllers as export files (*.lr.zip).

An export is a zip with a fixed set of files:

    package.ttl       manifest: title, version, description, creator, license,
                      and lr:mayRun: the command templates the model may ask to run
    model.ttl         SHACL shapes + operations
    controllers.ttl   controllers
    sheet.ttl         optional: an example seed sheet
    README.md         optional

Never included: the runtime state (.lr/) and trust rules (they belong to the user).

A *controller pack* declares lr:extends "<base package title>" and contains only
package.ttl, controllers.ttl and README.md. It cannot add operations or data: it
can only steer the choices the base model already offers. It is installed into an
existing project with add_layer, into layers/<title>/.

Importing is defensive: only those file names, size limits, every file must parse,
every query must pass the security check (no SERVICE / FROM), and every declared
command template must be a valid trust template. Nothing is trusted automatically.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from rdflib import RDF, Graph, Literal, Namespace, URIRef

from .controllers import load_controllers
from .operations import load_operations
from .trust import compile_template
from .vocab import LR

DCT = Namespace("http://purl.org/dc/terms/")
ALLOWED = ("package.ttl", "model.ttl", "controllers.ttl", "sheet.ttl", "README.md")
REQUIRED = ("model.ttl",)
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

    @classmethod
    def from_graph(cls, g: Graph, fallback_title: str) -> "Manifest":
        pkg = next(iter(g.subjects(RDF.type, LR.Package)), None)
        if pkg is None:
            return cls(title=fallback_title)
        v = lambda p: str(g.value(pkg, p) or "")  # noqa: E731
        return cls(title=v(DCT.title) or fallback_title, version=v(LR.version) or "0.0.0",
                   description=v(DCT.description), creator=v(DCT.creator), license=v(DCT.license),
                   may_run=sorted(str(x) for x in g.objects(pkg, LR.mayRun)),
                   extends=str(g.value(pkg, LR.extends)) if g.value(pkg, LR.extends) is not None else None)

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
        return g


def read_manifest(project: Path) -> Manifest | None:
    f = Path(project) / "package.ttl"
    if not f.exists():
        return None
    return Manifest.from_graph(Graph().parse(f, format="turtle"), Path(project).name)


def declared(manifest: Manifest | None, command: str) -> bool | None:
    """Does the package declare this command? None when there is no manifest."""
    if manifest is None:
        return None
    return any(compile_template(t).match(command.strip()) for t in manifest.may_run)


# ---------------------------------------------------------------- export

def export_project(project: str | Path, out: str | Path | None = None, sheet: str = "seed",
                   state_sheet: Graph | None = None) -> Path:
    """Write an export. sheet: "seed" (the authored sheet.ttl), "state" (state_sheet), or "none"."""
    p = Path(project)
    manifest = read_manifest(p) or Manifest(title=p.name)
    if manifest.extends:
        sheet = "none"  # a controller pack carries no data
    elif not (p / "model.ttl").exists():
        raise PackageError(f"{p} has no model.ttl")
    files: dict[str, bytes] = {}
    files["package.ttl"] = manifest.to_graph().serialize(format="turtle").encode()
    for name in ("model.ttl", "controllers.ttl", "README.md"):
        if (p / name).exists():
            files[name] = (p / name).read_bytes()
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
        if info.filename not in ALLOWED:
            raise PackageError(f"unexpected file in export: {info.filename!r} (allowed: {', '.join(ALLOWED)})")
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
    if manifest.extends:
        extra = {"model.ttl", "sheet.ttl"} & set(files)
        if extra:
            raise PackageError(f"a controller pack may only contain controllers, not {', '.join(sorted(extra))}")
        if "controllers.ttl" not in files:
            raise PackageError("a controller pack needs controllers.ttl")
    else:
        for name in REQUIRED:
            if name not in files:
                raise PackageError(f"export has no {name}")
    try:
        if "model.ttl" in graphs:
            load_operations(graphs["model.ttl"])  # includes the SERVICE / FROM check
        if "controllers.ttl" in graphs:
            load_controllers(graphs["controllers.ttl"])
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
        raise PackageError(f"{manifest.title} is a controller pack for '{manifest.extends}': "
                           f"add it to a project with: lr add-layer <file> <project>")
    d = Path(dest)
    if d.exists() and any(d.iterdir()):
        raise PackageError(f"{d} already exists and is not empty")
    d.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (d / name).write_bytes(content)
    return manifest


def add_layer(data: bytes, project: str | Path) -> Manifest:
    """Install a controller pack into an existing project, in layers/<title>/."""
    manifest, files = inspect_export(data)
    if not manifest.extends:
        raise PackageError(f"{manifest.title} is not a controller pack (it has no lr:extends)")
    p = Path(project)
    base = read_manifest(p)
    if base is None or base.title != manifest.extends:
        found = f"'{base.title}'" if base else "a project without package.ttl"
        raise PackageError(f"{manifest.title} extends '{manifest.extends}', but {p} is {found}")
    target = p / "layers" / manifest.title
    if target.exists():
        raise PackageError(f"layer {manifest.title} is already installed (delete {target} to replace it)")
    target.mkdir(parents=True)
    for name, content in files.items():
        (target / name).write_bytes(content)
    return manifest
