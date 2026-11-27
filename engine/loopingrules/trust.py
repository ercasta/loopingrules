"""Approval allowlist: command templates the user trusts (design D10).

A rule is a command template where each `{}` placeholder must sit inside single
quotes, e.g.  wc -l < '{}'.  A placeholder matches any text without a single quote
or a newline, so a matching command can never break out of its quoted argument.

Trust belongs to the *user*, not to the project: rules are stored in a user-level
file (default ~/.loopingrules/trust.ttl, override with LR_TRUST) and scoped to the
project's absolute path. A shared project folder therefore cannot carry approvals.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path

from rdflib import RDF, Graph, Literal, URIRef

from .vocab import LR

PLACEHOLDER = "'{}'"


class TemplateError(ValueError):
    pass


def compile_template(template: str) -> re.Pattern:
    t = template.strip()
    if not t:
        raise TemplateError("empty template")
    if "{}" in t.replace(PLACEHOLDER, ""):
        raise TemplateError("every {} must be written inside single quotes, as '{}'")
    if "\n" in t:
        raise TemplateError("templates are a single line")
    parts = t.split(PLACEHOLDER)
    return re.compile("'([^'\\n]*)'".join(re.escape(p) for p in parts) + r"\Z")


def generalize(command: str) -> str:
    """Propose a template: every single-quoted argument becomes '{}'."""
    return re.sub(r"'[^'\n]*'", PLACEHOLDER, command.strip())


@dataclass
class Rule:
    id: str
    template: str
    pattern: re.Pattern


def default_path() -> Path:
    return Path(os.environ.get("LR_TRUST") or Path.home() / ".loopingrules" / "trust.ttl")


class TrustStore:
    def __init__(self, project_path: str | Path, path: str | Path | None = None):
        self.project = str(Path(project_path).resolve())
        self.path = Path(path) if path else default_path()
        self.graph = Graph()
        self.graph.bind("lr", LR)
        if self.path.exists():
            self.graph.parse(self.path, format="turtle")

    def rules(self) -> list[Rule]:
        out = []
        for r in self.graph.subjects(LR.project, Literal(self.project)):
            template = str(self.graph.value(r, LR.template) or "")
            try:
                out.append(Rule(_rule_id(r), template, compile_template(template)))
            except TemplateError:
                continue  # ignore broken rules rather than trusting them
        return sorted(out, key=lambda r: r.template)

    def match(self, command: str) -> Rule | None:
        return next((r for r in self.rules() if r.pattern.match(command.strip())), None)

    def add(self, template: str) -> Rule:
        template = template.strip()
        pattern = compile_template(template)
        for r in self.rules():
            if r.template == template:
                return r
        iri = URIRef(f"urn:lr:trust:{hashlib.sha1((self.project + '|' + template).encode()).hexdigest()[:16]}")
        self.graph.add((iri, RDF.type, LR.TrustRule))
        self.graph.add((iri, LR.project, Literal(self.project)))
        self.graph.add((iri, LR.template, Literal(template)))
        self._save()
        return Rule(_rule_id(iri), template, pattern)

    def remove(self, rule_id: str) -> None:
        for r in list(self.graph.subjects(LR.project, Literal(self.project))):
            if _rule_id(r) == rule_id:
                self.graph.remove((r, None, None))
                self._save()
                return
        raise KeyError(rule_id)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.graph.serialize(self.path, format="turtle")


def _rule_id(iri) -> str:
    return str(iri).rsplit(":", 1)[-1]
