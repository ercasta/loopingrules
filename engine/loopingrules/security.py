"""Keep models and controllers pure data (design D9).

SPARQL can reach the network: `SERVICE <url> { ... }` makes rdflib call a remote
endpoint, and `FROM <url>` can make it load a remote graph. Either would let a
shared model read or leak data without going through tools and approval.
Every query the engine runs on behalf of a model is checked here.
"""

from __future__ import annotations

import rdflib.plugins.sparql as _sparql
from rdflib.plugins.sparql import prepareQuery

# Never dereference graphs named in FROM / FROM NAMED.
_sparql.SPARQL_LOAD_GRAPHS = False


class UnsafeQuery(ValueError):
    pass


def _names(node) -> set[str]:
    out = set()
    if hasattr(node, "name"):
        out.add(node.name)
    if isinstance(node, dict):
        for v in node.values():
            out |= _names(v)
    elif isinstance(node, (list, tuple)):
        for v in node:
            out |= _names(v)
    return out


def check_query(query: str, what: str = "query") -> None:
    """Raise UnsafeQuery if the query could touch anything outside the sheet."""
    try:
        q = prepareQuery(query)
    except Exception as e:
        raise UnsafeQuery(f"{what}: does not parse: {e}") from e
    if "ServiceGraphPattern" in _names(q.algebra):
        raise UnsafeQuery(f"{what}: SERVICE is not allowed (models cannot reach the network)")
    if getattr(q.algebra, "datasetClause", None):
        raise UnsafeQuery(f"{what}: FROM / FROM NAMED is not allowed")
