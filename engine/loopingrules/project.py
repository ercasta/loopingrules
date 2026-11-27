"""A project is a folder with sheet.ttl, model.ttl and controllers.ttl."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rdflib import Graph

from .vocab import LR

FILES = ("sheet", "model", "controllers")


def _load(path: Path) -> Graph:
    g = Graph()
    g.bind("lr", LR)
    if path.exists():
        g.parse(path, format="turtle")
    return g


@dataclass
class Project:
    path: Path
    sheet: Graph
    model: Graph
    controllers: Graph

    @classmethod
    def load(cls, path: str | Path) -> "Project":
        p = Path(path)
        return cls(p, *(_load(p / f"{name}.ttl") for name in FILES))

    def save(self, path: str | Path | None = None) -> None:
        p = Path(path) if path else self.path
        p.mkdir(parents=True, exist_ok=True)
        for name in FILES:
            getattr(self, name).serialize(p / f"{name}.ttl", format="turtle")
