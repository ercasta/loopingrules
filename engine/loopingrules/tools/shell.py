"""Shell tool: executes lr:ShellCall resources found in the sheet.

    ?call a lr:ShellCall ; lr:command "ls -1" ; lr:status lr:Pending .

After execution the engine writes back:

    ?call lr:status lr:Done ; lr:exitCode 0 ;
          lr:stdoutLine [ lr:index 0 ; lr:text "a.txt" ] ;
          lr:stderrLine [ lr:index 0 ; lr:text "..." ] .
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from rdflib import RDF, BNode, Graph, Literal, URIRef
from rdflib.namespace import XSD

from ..vocab import DONE, FAILED, LR, PENDING, REJECTED

Executor = Callable[[str], tuple[int, str, str]]


def find_shell() -> str:
    if env := os.environ.get("LR_SHELL"):
        return env
    if os.name == "nt":
        for candidate in (r"C:\Program Files\Git\bin\bash.exe", r"C:\Program Files (x86)\Git\bin\bash.exe"):
            if Path(candidate).exists():
                return candidate
    return shutil.which("bash") or shutil.which("sh") or "sh"


def subprocess_executor(shell: str | None = None, timeout: float = 60) -> Executor:
    sh = shell or find_shell()

    def run(command: str) -> tuple[int, str, str]:
        p = subprocess.run([sh, "-c", command], capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr

    return run


@dataclass
class PendingCall:
    iri: URIRef | BNode
    command: str

    def as_dict(self) -> dict:
        return {"id": self.iri.n3(), "tool": "shell", "command": self.command}


class ShellTool:
    def __init__(self, executor: Executor | None = None):
        self.executor = executor or subprocess_executor()

    def pending(self, g: Graph) -> list[PendingCall]:
        out = []
        for call in g.subjects(RDF.type, LR.ShellCall):
            if (call, LR.status, PENDING) in g:
                out.append(PendingCall(call, str(g.value(call, LR.command) or "")))
        return sorted(out, key=lambda c: c.iri.n3())

    def reject(self, g: Graph, call: PendingCall) -> None:
        g.set((call.iri, LR.status, REJECTED))

    def run(self, g: Graph, call: PendingCall) -> None:
        try:
            code, out, err = self.executor(call.command)
        except Exception as e:  # timeout, missing shell, ...
            g.set((call.iri, LR.status, FAILED))
            _lines(g, call.iri, LR.stderrLine, str(e))
            return
        g.set((call.iri, LR.exitCode, Literal(code, datatype=XSD.integer)))
        _lines(g, call.iri, LR.stdoutLine, out)
        _lines(g, call.iri, LR.stderrLine, err)
        g.set((call.iri, LR.status, DONE))


def _lines(g: Graph, call, prop, text: str) -> None:
    for i, line in enumerate(text.splitlines()):
        node = BNode()
        g.add((call, prop, node))
        g.add((node, LR["index"], Literal(i, datatype=XSD.integer)))
        g.add((node, LR.text, Literal(line)))
