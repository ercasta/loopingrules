# Examples

`examples/` holds worked domains. They are **source in this repo, not part of
the installed package**: `pip install -e .` installs `loopingrules` only, and
nothing in the package imports them. Tests reach them because
`pyproject.toml` puts the repo root on `pythonpath`.

Each has a matching `tests/test_examples_*.py`. **Read the test alongside the
example.** It shows the scenario being driven.

| Example | What it demonstrates | Start here if you want to see... |
|---|---|---|
| `cards.py` | An autonomous trading agent over a virtual card market | **The core idea**: `decide_buy` reads three tags (`Wanted`, `Affordable`, `FairPriced`) attached by three rules that share no code. The best first example |
| `judge.py` | One domain-oblivious rule (`Risk`, `TooRisky`) usable by any domain | Reuse across domains without a shared vocabulary |
| `shopping.py` | A household shopping list, the second domain to use `judge.Risk` | `judge` reused for real, with `Said`/`reply` handling |
| `decide.py` | A second domain-oblivious rule (`Option`, `Score`, `Winner`) that picks a scored winner among several rivals for one occasion | A bridge rule: a domain projects its own rivalry, `pick_winner` computes and attaches the answer back |
| `deixis.py` | `"look at X"` then `"it"`/`"that"` | `memory.Focus`/`Memory` on a real reference-resolution rule |
| `files.py` | A `stat` capability reached only through `circuits.Call` | A rule authored as **data** requesting real disk I/O |
| `parts.py` | A prototype: a generic tag beside every specific part-edge | A generic walker that stays analyzable (needs literal component types) |
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
3. `examples/judge.py`, then `shopping.py`, to see reuse.
4. `examples/decide.py`, judge's sibling for a SCORED, several-rivals
   contest rather than a single threshold.
5. `tests/test_analyze.py`, to see what rule analysis can and cannot do.
6. `examples/deixis.py` if you work on conversation.
7. `examples/trip.py` last. It is the largest, uses the most machinery, and
   is `decide.py`'s own worked domain.

## Why they are not shipped

The package's own rule: it ships no domain, with `help.py` as the single
stated exception. Examples exist to prove the substrate against real rules.
Their docstrings each say what they were built to test, and several
record bugs the exercise caught. They are worth reading for the reasoning as
much as the code.
