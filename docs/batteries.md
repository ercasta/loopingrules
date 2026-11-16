# Batteries: the reusable model library

A **battery** is a shipped, reusable **model** -- components + operations -- plus
examples and knobs, exposed as an **island** (ADR-12: *model* is the importable
unit; *island* is a terminology-indexed view over its operations; *pattern* is a
reusable hole-shaped operation). Its reusable surface is a **narrow, generic
interface** (ADR-6: narrow interface, broad gate). The rule of reuse is D6's --
**the domain owns the projection, the battery owns the decision**.

Batteries live in `loopingrules_lang/batteries/*.yaml` and compose on one loop:

```
lr run batteries/core.yaml batteries/scope.yaml batteries/rank.yaml \
       models/table.yaml -c models/table.context.yaml
```

## The spine: a small set of shared shapes

A battery never names a domain. Nearly all of them are readers/writers over a few
neutral shapes, and *that* is what keeps the library small:

| shape | what it is |
|---|---|
| `candidate{worth, label}` | a proposable thing (card, listing, departure, plan option) |
| `metric{value}` | a projected scalar |
| `constraint{kind, limit}` + `verdict{ok, reason}` | a business check |
| `policy{order, limit}` | the knobs (values fitted by search, ADR-2) |
| roles (tags): `chosen`, `excluded`, `selected` | what a battery confers |
| `request{capability, args}` | the tool seam (built) |

## The catalog

**A. Evaluation & choice** -- the most reused. `scope`/`rank` ship today.
| battery | thin interface | decides | vers. | status |
|---|---|---|---|---|
| `scope` | `candidate.worth` + `policy.limit` → `excluded` | which candidates are in play | ★★★ | **shipped** |
| `rank` | `candidate.worth` + `policy.order` → `chosen` | the best (argmin/argmax) | ★★★ | **shipped** |
| `threshold` | `metric.value` + policy → `verdict` | too risky / urgent / big | ★★★ | planned (`patterns.judge`) |
| `feasibility` | `candidate` + `constraint` → `verdict{ok, reason}` | is it allowed | ★★★ | planned (the constraint hub) |
| `preference` | `preference{a,b}` → a partial order | A over B (pairs, sorting) | ★★ | planned (D2) |
| `aggregate` | `child.of` → sum/count/join | totals & reports | ★★ | folds into `table` |

**B. Memory & context**
| battery | thin interface | decides | vers. | status |
|---|---|---|---|---|
| `memory` | focus/events → `remembered` | what to keep, promote, forget | ★★★ | `loopingrules.memory` exists -- consolidate |
| `focus` (deixis) | attention → `most_recent`/`most_intense` | what "it / that" refers to | ★★★ | `examples/deixis.py` sketch |
| `episodic` | the change log → `was`/`did` | what happened, who did it | ★★ | application memory (ADR-13) |
| `ledger` | writes → provenance | why, what was conceded | ★ | `reflect` + the concession ledger |

**C. Structure**
| battery | thin interface | decides | vers. | status |
|---|---|---|---|---|
| `graph` | `node`/`edge` → `path`/`frontier`/`dominance` | reachability, shortest path | ★★★ | `trip` is one -- extract |
| `sequence` (procedure) | `step.next` / `cursor` → advance once | follow ordered steps | ★★★ | U3 names it |
| `tree` | parent/child refs → roll-up / flatten | hierarchy, nesting | ★★ | planned |
| `set-algebra` | roles → union/intersect/difference | candidates satisfying A **and** B | ★★ | planned |

**D. Search & planning**
| battery | thin interface | decides | vers. | status |
|---|---|---|---|---|
| `search` (frontier) | `frontier` + expand → next `frontier`, `visited` | best-first / A* / greedy | ★★ | `trip.frontier` seed |
| `planning` | compose ops → `plan{cost}` → `chosen` | build & pick a multi-step plan | ★★ | `trip`/`s6` -- composes search + rank + feasibility |
| `schedule` | `task{window, resource}` + constraints → order | timetabling | ★★ | planned |
| `simulate` | fork the world, step, score | evaluate a candidate by rollout | ★★ | `save`+`replay` = cloning |

**E. Resolution & language edge**
| battery | thin interface | decides | vers. | status |
|---|---|---|---|---|
| `resolve` (disambiguate) | several definers of a term → one, by context | which meaning fires | ★★ | `s3`; control-network-adjacent |
| `lexicon` | token → attribute/value | coerce text to a value | ★★ | ADR-2 L4 / U7 |
| `referent` | a name/description → an entity | coreference ("the cheap one") | ★★ | `deixis`/`memory` |

**F. IO & runtime**
| battery | thin interface | decides | vers. | status |
|---|---|---|---|---|
| `table_io` (`read_table`) | `request{read_table, path, relation, columns}` → row entities | bring a table in | ★★★ | **shipped** |
| `adapters` | `request{capability, args}` → world entities | reach files/HTTP/JSON | ★★★ | `read_table`/`train_timetable`/`echo` |
| `clock` | time as world data → minutes/dates/timers | deadlines, "before 9am" | ★★★ | planned (tiny) |
| `doubt` | nothing covered → `Doubt` | novelty / training signal | ★★ | the scheduler's `Doubt` |
| `controls` | `RuleControl` → enable/disable/reorder | runtime steering | ★ | shipped (`reflect`) |

**G. Data & tables** -- the substrate is *already* a table store (an entity is a
row, a component a relation, its fields columns), so this is algebra + IO, not new
storage.
| battery | thin interface | decides | vers. | status |
|---|---|---|---|---|
| `table` | a table descriptor + rows → derived/filtered rows | `where`/`project`/`order_by`/`limit`/`distinct`/`group_by`+agg/`join` | ★★★ | planned; `scope`/`rank`/`aggregate` are its first operations |
| `table_io` | see F | read/write CSV/JSON; **declared return schema** | ★★★ | **shipped** (`read_table`) |

## Return schema

For a table, the **return schema** is the relation's component and its columns,
with a **coercion type** per column (a coercion at the edge -- values stay
primitives, `PRINCIPLES.md`):

```yaml
- do: {source: timetables/2026.csv, relation: departure,
       columns: "train:str,from:str,to:str,depart:minutes,arrive:minutes,fare:float"}
```

`read_table` coerces `minutes` (`"07:00"` → 420), `int`, `float`, `bool`, `str`.
A model that reads the relation declares the component -- an undeclared use is a
`schema.Gap`, refused at load. *(The columns are one flat string, not a list: a
request's `args` are a flat list, and the substrate stores flat values only.)*

## The core to ship first, and the order

**Shipped:** `core` (the shared vocabulary), `scope`, `rank`, `table_io`.

**Next, in order:** `threshold` + `feasibility` (finish the evaluation quartet) →
`clock` → `graph` + `sequence` → `memory` + `focus` → `table`'s algebra
(`group_by`/`join`/`order_by`) → `search`/`planning` → the language edge.

`planning` is **not** a monolith: it is `search` + `rank` + `feasibility` + `graph`,
so it falls out once those exist.

## Admission and format

A battery ships when it meets the bar, not when it is written:

- **generic vocabulary** -- it names no domain;
- **one decision**;
- **closed in authorship** -- nothing in it imports a domain (D6);
- **a second domain depends on it at runtime** (the standing promotion rule);
- a pinned example that can fail.

Layout: `loopingrules_lang/batteries/<name>.yaml` (the model) + a context under
`models/` + a test. When the library outgrows a flat directory, each battery moves
to its own folder with a `README` (interface + return schema). The name *battery*
is provisional; the repo's terms are **island** / **model**.
