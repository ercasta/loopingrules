# Examples

`examples/` holds worked domains. They are **source in this repo, not part of
the installed packages**: `pip install -e .` installs `loopingrules`,
`loopingrules_calibration` and `loopingrules_patterns`, and nothing in any of
them imports an example. Tests reach the examples because `pyproject.toml`
puts the repo root on `pythonpath`.

Each has a matching `tests/test_examples_*.py`. **Read the test alongside the
example.** It shows the scenario being driven.

| Example | What it demonstrates | Start here if you want to see... |
|---|---|---|
| `cards.py` | An autonomous trading agent over a virtual card market | **The core idea**: `decide_buy` reads three tags (`Wanted`, `Affordable`, `FairPriced`) attached by three rules that share no code. The best first example |
| `shopping.py` | A household shopping list, the second domain to project onto the shipped `judge` [pattern](patterns.md) | A promoted pattern reused for real, with `Said`/`reply` handling |
| `decide.py` | A second domain-oblivious rule (`Option`, `Score`, `Winner`) that picks a scored winner among several rivals for one occasion | A bridge rule: a domain projects its own rivalry, `pick_winner` computes and attaches the answer back |
| `trip.py` | A multi-modal trip planner (train, taxi, subway) as forward-only rule expansion, over three merged networks; its winning itinerary is read back through `decide.py`'s bridge, not recomputed by hand | `share.py` remapping and domain-owned reconciliation on something bigger than a toy |

## Shape of a domain

Every example follows the same pattern, which is the pattern to copy:

1. **Components** as frozen dataclasses. Relationships are int ids.
2. **Rules** as plain functions of `w`, each doing one small thing.
3. **`install(loop)`** registers the rules with explicit qualified names and
   seeds any singleton entities (a purse, a risk profile).
4. **Input** arrives as `Said`. A `hear_*` rule consumes it when it recognizes
   its own verb. **Output** leaves as `reply(w, ...)`.

## Reading order for a new contributor

1. `tests/test_loop.py`, to see what the loop promises.
2. `examples/cards.py` and `tests/test_examples_cards.py`.
3. The shipped [`judge` pattern](patterns.md), then `shopping.py`, to see
   reuse.
4. `examples/decide.py`, judge's sibling for a SCORED, several-rivals
   contest rather than a single threshold.
5. [Rule analysis](analysis.md), to see what rule analysis can and cannot do.
6. `examples/trip.py` last. It is the largest, uses the most machinery, and
   is `decide.py`'s own worked domain.

## Why they are not shipped

The engine's own rule: it ships no domain. Examples exist to prove the
substrate against real rules; the vocabulary worth SHARING is moved into
[`loopingrules_patterns`](patterns.md) once a second domain depends on it,
which is why `judge` no longer lives here.
Their docstrings each say what they were built to test, and several
record bugs the exercise caught. They are worth reading for the reasoning as
much as the code.
