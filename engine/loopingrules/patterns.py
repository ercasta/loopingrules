"""The SPARQL subset allowed in operation patterns (design D23).

Operation patterns (`lr:where`) may use triple patterns, FILTER (with EXISTS /
NOT EXISTS), BIND, OPTIONAL, UNION, VALUES and the expression functions. This
subset can later be compiled to incremental matching (Rete-style), so the
engine can update matches from a delta instead of re-running every WHERE every
tick. Subqueries, aggregates, MINUS, property paths and GRAPH are refused.

Controllers are not restricted: they are full SPARQL.
"""

from __future__ import annotations

from rdflib.paths import Path
from rdflib.plugins.sparql import prepareQuery
from rdflib.plugins.sparql.parserutils import CompValue


class UnsupportedPattern(ValueError):
    pass


# Algebra (and, inside EXISTS, parse-tree) node names -> what the author wrote.
_REFUSED = {
    "SubSelect": "subqueries",
    "ToMultiSet": None,  # VALUES (allowed) or a subquery: decided by its child, see below
    "Group": "GROUP BY / aggregates",
    "AggregateJoin": "GROUP BY / aggregates",
    "Minus": "MINUS",
    "MinusGraphPattern": "MINUS",
    "Graph": "GRAPH",
    "GraphGraphPattern": "GRAPH",
    "ServiceGraphPattern": "SERVICE",
}


def _problems(node, out: set[str], top: bool = False) -> None:
    if isinstance(node, Path):
        out.add("property paths (write one triple per predicate)")
        return
    if isinstance(node, CompValue):
        name = node.name
        if name.startswith("Aggregate_"):
            out.add("GROUP BY / aggregates")
        elif name == "ToMultiSet":
            if getattr(node.get("p"), "name", None) != "values":
                out.add("subqueries")
        elif name == "Project" and not top:
            out.add("subqueries")
        elif _REFUSED.get(name):
            out.add(_REFUSED[name])
        for key, v in node.items():
            # The top-level SelectQuery holds exactly one Project: ours.
            _problems(v, out, top=(name == "SelectQuery" and key == "p"))
    elif isinstance(node, dict):
        for v in node.values():
            _problems(v, out)
    elif isinstance(node, (list, tuple, set, frozenset)):
        for v in node:
            _problems(v, out)


def check_pattern(pattern: str, prefixes: str, what: str = "pattern") -> None:
    """Raise UnsupportedPattern if a WHERE pattern leaves the allowed subset."""
    try:
        q = prepareQuery(f"{prefixes}SELECT * WHERE {{ {pattern} }}")
    except Exception as e:
        raise UnsupportedPattern(f"{what}: does not parse: {e}") from e
    found: set[str] = set()
    _problems(q.algebra, found)
    if found:
        raise UnsupportedPattern(
            f"{what}: not allowed in operation patterns: {', '.join(sorted(found))} "
            "(operation patterns use a subset of SPARQL, see design D23)")
