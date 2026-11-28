# planning

A **library pack** for following a method (design D31): reach a series of subgoals, each by recognising the situation and carrying out a known procedure. The procedures are written by people, as in a textbook. There's no search.

It installs into any project: `lr add-layer planning.lr.zip <project>`. The Rubik example (`examples/rubik`) is built on it.

## What the domain writes (knowledge)
```turtle
ex:method a pl:Method ; pl:firstStage ex:s1 ; pl:view ex:v1, ex:v2 .   # views: see below
ex:s1 a pl:Stage ; rdfs:label "first stage" ; pl:goal ex:c1 ; pl:next ex:s2 .
ex:k1 a pl:Case ; pl:stage ex:s1 ; pl:when ex:c2, ex:c3 ; pl:do ex:p1 ; pl:priority 0 .
ex:p1 a pl:Procedure ; pl:steps ( ex:a ex:p2 ex:loop ex:until ) .   # ( ) for brevity: see below
ex:loop  a pl:Repeat ; pl:times 3 ; pl:do ex:p3 .
ex:until a pl:Until ; pl:until ex:c4 ; pl:do ex:p4 .     # checks first
```
- **A step** is a procedure (call it), a `pl:Repeat`, a `pl:Until`, or anything else: a **primitive action**, for the domain to carry out.
- **Conditions** (`ex:c1` …) are the domain's own resources. The pack never looks inside them.
- **Views** are the ways a case can be recognised: the Rubik example has 4, one per way of holding the cube. A case is planned in the view where its conditions hold, and its procedure runs in that view. A domain without symmetries declares one.
- **Lists in knowledge need named nodes:** knowledge can't hold blank nodes (D28).

## The protocol: requests and answers in the sheet
| The pack deposits | The domain answers |
|---|---|
| `[] a pl:Check ; pl:run ?r ; pl:about ?x ; pl:condition ?c ; pl:view ?v` | `?check pl:result true` or `false`. Answer them all in one operation, with `lr:params ""`, so it's one tick. |
| `?run pl:doing ?action` | Carry the action out *and* delete `pl:doing` in the same application, so the pack never asks about a state that hasn't changed yet. |

The domain starts a run with `[] a pl:Run ; pl:method ex:method`. The pack says `Done: <stage>.` on `lr:out` at each stage's end, then `Finished.` and removes the run. If no case fits, it says `Stuck in <stage>: no case fits.` and stops.

A complete small domain, a counter, is in `engine/tests/test_d31.py`: two operations.

## How it runs
- **The run's phase:** `pl:Look` (about to ask), then `pl:Question` (asked; waiting for answers, then a decision).
- **One decision per round of answers:**
  - next stage, or finish;
  - plan a case, with the highest `pl:priority` (the only controller);
  - stuck.

  A decision marks the run `pl:decided`, and `pl:forget` then clears the answers.
- **A procedure runs on a call stack** of frames (`pl:rest`, `pl:parent`, `pl:loop`, `pl:left`). The pack's operations call, start repeats and untils, hand out actions, and return.
- **Every operation waits through its own pattern:** nothing pending, nothing being done. So the order is in the preconditions.

## Writing patterns for it (performance)
Oxigraph (D30) builds every candidate row before applying `FILTER NOT EXISTS`:
- **Start expensive operations from a positive triple** that's missing when they don't apply, such as the run's phase. A filter that rules them out comes too late.
- **Keep `UNION` branches self-contained.** Each branch should start from what's being matched (the check), not be joined to it from outside.
- **Make "is there a false check about X" a single star pattern:** that's why checks carry `pl:about`.
