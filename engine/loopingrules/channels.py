"""Input and output channels (design D25): a convention, plus a few helpers.

A message is a resource on a channel:

    gen:m1 lr:channel lr:in ;  a cmd:AddTask ; cmd:title "write D25" .
    gen:m2 lr:channel lr:out ; a lr:Say ; lr:text "Added." ; lr:replyTo gen:m1 .

Posting to lr:in only adds triples about the post's own new nodes, so a post can
ask but never edit the state. The model's operations consume lr:in messages and
insert lr:out messages; readers acknowledge (delete) lr:out messages.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rdflib import RDF, BNode, Graph, URIRef

from .project import GEN, Project, mint
from .vocab import LR

IN, OUT = LR["in"], LR.out
CHANNELS = {"in": IN, "out": OUT}

# The only lr: terms a post may use: everything else in lr: is the engine's own
# vocabulary (tool calls, statuses, channels), which a tool must not be able to fake.
POST_ALLOWED_LR = {LR.text, LR.replyTo, LR.Say}


class PostError(ValueError):
    def __init__(self, message: str, violations: list[dict] | None = None):
        super().__init__(message)
        self.violations = violations or []


def parse_post(text: str, *prefix_sources: Graph) -> tuple[list[tuple], BNode]:
    """Parse and check a post; return its triples (with blank nodes) and the root.

    Rules (D25): every subject is a blank node of the snippet, there is exactly one
    root (a blank node that is not the object of another triple), and no lr: term
    is used except lr:text, lr:replyTo and lr:Say.
    """
    known: dict[str, str] = {}
    for src in prefix_sources:  # the first binding of a prefix wins, as in store.prologue
        for p, ns in src.namespaces():
            known.setdefault(p, str(ns))
    g = Graph()
    for p, ns in known.items():
        g.bind(p, ns, override=True)
    head = "".join(f"@prefix {p}: <{ns}> .\n" for p, ns in known.items() if p and p != "xml")
    try:
        g.parse(data=head + text, format="turtle")
    except Exception as e:
        raise PostError(f"the post does not parse as Turtle: {e}") from e
    triples = list(g)
    if not triples:
        raise PostError("the post is empty")
    bad = sorted({s.n3(g.namespace_manager) for s, _, _ in triples if not isinstance(s, BNode)})
    if bad:
        raise PostError("a post may only describe its own new nodes; write them as [ ] or _:x, "
                        f"not {', '.join(bad)}")
    for t in triples:
        for x in t:
            if isinstance(x, URIRef) and str(x).startswith(str(LR)) and x not in POST_ALLOWED_LR:
                raise PostError(f"a post may not use {x.n3(g.namespace_manager)}: "
                                "lr: terms other than lr:text, lr:replyTo and lr:Say belong to the engine")
    subjects = {s for s, _, _ in triples}
    referenced = {o for _, _, o in triples if isinstance(o, BNode)}
    roots = subjects - referenced
    if len(roots) != 1:
        raise PostError(f"a post must have exactly one root node (found {len(roots)})")
    return triples, next(iter(roots))


def mint_post(triples: list[tuple], root: BNode) -> tuple[set[tuple], URIRef]:
    """Replace the post's blank nodes with minted IRIs and put the root on lr:in."""
    names: dict[BNode, URIRef] = {}
    sub = lambda x: names.setdefault(x, mint()) if isinstance(x, BNode) else x  # noqa: E731
    out = {tuple(sub(x) for x in t) for t in triples}
    root_iri = sub(root)
    out.add((root_iri, LR.channel, IN))
    return out, root_iri


@dataclass
class Message:
    iri: URIRef
    channel: str
    order: int  # the journal transaction that put it on the channel; -1 for the seed
    triples: list[tuple] = field(default_factory=list)  # the message and its parts

    @property
    def types(self) -> list[URIRef]:
        return sorted(o for s, p, o in self.triples if s == self.iri and p == RDF.type)

    @property
    def text(self) -> str | None:
        return next((str(o) for s, p, o in self.triples if s == self.iri and p == LR.text), None)


def parts(sheet: Graph, root: URIRef) -> list[tuple]:
    """The triples of a message: about the message itself, and about its parts.

    A part is a minted (gen:) node that only the message and its other parts refer
    to, like a blank node in Turtle. A minted node anything else refers to is shared
    state, so it is not part of the message (and acknowledging won't delete it).
    """
    inside = {root}
    changed = True
    while changed:
        changed = False
        for s in list(inside):
            for o in sheet.objects(s, None):
                if (isinstance(o, URIRef) and str(o).startswith(str(GEN)) and o not in inside
                        and all(x in inside for x in sheet.subjects(None, o))):
                    inside.add(o)
                    changed = True
    return sorted(t for n in inside for t in sheet.triples((n, None, None)))


def messages(project: Project, channel: str) -> list[Message]:
    """The messages on a channel, in the order they appeared."""
    ch = CHANNELS[channel]
    sheet = project.sheet
    order: dict = {}
    for tx in project.journal:
        for s, p, o in tx.added:
            if p == LR.channel and o == ch:
                order[s] = tx.n
    out = [Message(m, channel, order.get(m, -1), parts(sheet, m))
           for m in sheet.subjects(LR.channel, ch)]
    return sorted(out, key=lambda m: (m.order, str(m.iri)))
