# The scale probe: can the stigmergic pattern scale — in models, and in use cases?

Status: **design only.** No probe is built — no maze family, no baseline harness, no
test. This doc extends D10 (`archived-old/plan-maze.md`, "a benchmark for the
control network") from scoring a *network* to scoring the **composition pattern**,
and it stage-manages the comparison this repo has so far refused to run
(`comparison-soar.md`: *"Not a benchmark… no claim about comparative capability is
made or implied"*). It is written **before the port is green** because the claim
it tests is load-bearing for the whole direction, and because its cheap half can
be pinned as soon as `checks` lands (`handoff.md` §6). Nothing here is a
commitment to code: every claim is a probe with a kill/reshape criterion, in the
repo's posture. The name is provisional, like `plan-ux.md` and
`loopingrules_forge`.

## 1. The question, stated once

> Does the **stigmergic computation pattern** scale better than **ad-hoc
> programs that compose multiple models**?

The word "scale" hides **two axes**, and this doc takes both:

| axis | what grows | what is held fixed | the claim | where |
|---|---|---|---|---|
| **A — composition** | the **models** (N) | the use case | composing N models stays local, totally analyzable, reproducible | §3–§4 |
| **B — coverage** | the **use cases** answered | the **model set** | a *fixed* model set answers a **combinatorial** family of questions/goals, with **no per-case code**, by taking *different trajectories* on the user's input | §5 |

Axis A is the one the earlier thread named. **Axis B is the sharper one** — it is
what "no-code authoring" (ADR-1, ADR-8) actually promises, and it has a competitor
axis A does not: an **LLM agent also takes a different path per input with no
code**, so B counts only if the substrate's coverage is **sound and bounded** where
the LLM's is not.

Two further things must be fixed before either can be answered.

**Which pattern.** Two different claims wear the word "stigmergic" here, and they
are not the same test:

- the **pattern** — what this doc tests: rules never call each other, the only
  channel is what is deposited in the `World`; "lowering" is derivation, not
  compilation; iteration is **stigmergic re-firing**, not a construct
  (ADR-4, ADR-11 §2, `PRINCIPLES.md`). This is the substrate's reason to exist.
- the **control network** (D9) — ADR-13 **replaced** its mechanism: it is now a
  **pure evaluator** that writes nothing, so "one control attribute steers the
  next application" is gone. D9's decision-tree *sharing* argument was the
  sharpest scaling claim the design ever made, and ADR-13 explicitly relocates
  it ("sharing is a property of the *evaluation*, not of world state") and
  leaves it **unmeasured** (`plan-control-network.md`, "Cost").

So the pattern's case must now stand on ADR-4/ADR-11 alone. The test is of the
**pattern**, not of a network.

**Which comparison.** The baseline is an **ad-hoc program that composes multiple
models**: orchestration code — hand-written or model-written — that calls model
operations in a coded order, wires their outputs together by hand, and returns a
result. That is the shape of most current "multi-model" systems (function-calling
pipelines, workflow graphs, ensemble wrappers). The substrate's claim is that its
composition instead **emerges** from independently-authored, mutually-ignorant
rules.

## 2. Why "prove" is the wrong verb

A universal *"scales better"* is not provable, and this repo already says so of
itself (`comparison-soar.md`). For any fixed distribution a hand-written program
can hardcode the right answer; any measured win is **regime-bounded**. What is
achievable instead:

- **(a) structural claims that are provable**, and that the baseline structurally
  cannot satisfy — these are the *real* scaling argument, because scaling is
  about what happens **per model** (axis A) and **per authored concept** (axis B);
- **(b) bounded empirical experiments**, with a mechanical ground truth and a kill
  criterion, that a curve can falsify.

"Prove" is therefore replaced by two falsifiable things: pin the structural
claims as tests (they can fail), and pre-register the empirical predictions (they
can fail). A verdict that cannot name which of these two it rests on is not a
verdict.

Axis A's structural claims are P1–P4 (§3); axis B's are the **sound / bounded /
auditable** trio (§5.1). Axis A's experiment is §4; axis B's is §5.3–§5.5.

## 3. Axis A, the provable half — four structural claims

Scaling is a **slope**, so each claim is stated **per-model**, and each is
cheaper than any experiment. Note which are near-theorems of the substrate
(P1–P3 follow from `analyze` and the loop, both already built) and which is a
measurement of the *build* (P4).

| # | Claim | Pin it by | Why ad-hoc composition cannot |
|---|---|---|---|
| **P1** | **Composition is totally analyzable** — `reads`/`writes` are *derived* over the whole composed set, not declared. | `analyze` a world with N models installed; assert the derived read/write graph is total (no `Opaque` for ordinary operations). | An orchestrator that calls model functions is a callable; `analyze` sees through it to nothing → `Opaque` (§`compile_answerer` is the substrate's own conceded `Opaque` case). |
| **P2** | **An undefined term is a blocking gap** — a used-but-unwritten name stops composition at build time. | Compose two models whose vocabularies collide or miss; the forge's read-without-writer gate must fire. | Composing two models ad-hoc is a runtime `NameError`/`None` at best and a silent wrong answer at worst — never a build-time stop. |
| **P3** | **Determinism/replay is a gate** — same input → same `signature`, world-clonable. | `save` + `replay` twice; assert equal `signature` (`calibration.kit`). | Calling N models is order- and timing-dependent; there is no replay by construction. |
| **P4** | **Adding the Nth model is local** — import + declare a bridge/joint operation; the orchestrator is not edited. | Count the diff to add model N; assert it is **O(1)** in N. | A central orchestrator is edited once per interaction → O(N) per model, **O(N²)** total — the actual scaling failure mode. |

**Sketch (proposed, red until the port lands).** P1–P3 pin as tests beside
`tests/test_analyze.py` / `tests/test_loop.py`; P4 pins as a script that
builds a world with N=1…k models and records the diff, so its output is a curve,
not a boolean. The point of P1–P4: **their failure would refute the pattern's
selling point even if the empirical experiment never runs.** They are the part
that is genuinely provable, so they are the first thing worth pinning after
`checks`.

## 4. Axis A, the empirical half — the experiment

### 4.1 Fix the scarce resource first

"Better" is meaningless untied to a resource. Choose **one** axis up front:
**authoring effort** (the tokens or person-hours to produce the system) or
**examples**. Then:

> "Better" = **success at held-out composition under equal resource.**

Changing the axis changes the verdict, so it is declared, not implied.

### 4.2 The generator — the D10 maze, with a complexity knob

One generator with a small parameter — N models (or interaction-graph branching
and depth), shared sub-branches — and: **mechanical** ground truth (goal reached
/ shortest / moves-used), a **held-out** split, and **no coded solution** (the
moves are generic; only the composition decides). This is D10 lifted: what D10
scores a *network* with, the scale probe scores a *composition* with. The
generator's parameters **are** the independent variable; without them there is no
scaling claim to make.

### 4.3 Four arms, because two confound

The interesting cell is **machine-searched ad-hoc**: without it, a win is
attributable to *having a search* (the forge), not to stigmergy.

| | hand-authored | machine-searched |
|---|---|---|
| **stigmergic** | substrate: authored bridges, grown selection | substrate: the forge grows the composition |
| **ad-hoc** | a person writes the orchestrator | the same generator writes the orchestrator program |

The grid separates **"the pattern"** from **"having a forge at all."** Any verdict
must name which factor produced it — this is the single most likely way to get a
fake result (see §7).

### 4.4 Sweep the knob, report the curve

Sweep N. Report **success@held-out**, **effort@N**, and **detectable-error@N**.
Read the **slope**. A single N — the shape of S3/S5/S6 today — cannot answer a
scaling question by construction.

### 4.5 Pre-registered predictions

Stated before running, so the probe can lose:

1. The substrate wins on **held-out composition** and on **P4 change-locality**.
2. Ad-hoc wins at **small N** — no join enumeration, no search, a lower constant
   factor (ADR-9 and ADR-13 both name enumeration cost as the real risk).
3. The deliverable is the **crossing point and the regime**, not a winner.

### 4.6 Negative controls

- **(a)** Generic moves with no composition must **fail** the maze — this is what
  makes "the solution was not coded" true rather than assumed.
- **(b)** Train and held-out from the **same** generator — a memorization check; a
  network that only wins on train has learnt the family, not the pattern.
- **(c)** Checks must **not** presume the substrate's split structure — D10's own
  hazard: a check that rewards the very structure being searched for proves
  nothing.

## 5. Coverage scaling — many use cases, one model set

### 5.1 The claim, sharpened

What an author ships is a **fixed set of models** (components + operations,
ADR-12). What a *user* supplies is a **use case** — a question or a goal — as
(structured) input. The claim of axis B:

> From a fixed model set, the system reaches the answers to a **combinatorially
> larger family of use cases** than were ever authored, with **zero per-use-case
> code**, because the input's structure selects a **trajectory** over the same
> operations (ADR-8's anchors; ADR-13's recorded selection).

The "no code" property is **not** unique to this substrate — an LLM agent routes
to a different tool per prompt with no code too. So the claim is only interesting
once sharpened to the substrate's actual bets:

- **Sound** — a covered use case is reached by a trajectory over *declared*
  concepts; there is no path off the model set (ADR-2: growth never invents a
  concept).
- **Bounded** — a use case needing a concept no model defines is a **gap**
  (ADR-3/ADR-8's blocking read-without-writer): a question, **never a guess**.
- **Auditable** — the trajectory is the *recorded* selection sequence (ADR-13
  application memory), replayable (P3), so "why this answer" is the trace.

So axis B is a **triple — (coverage, soundness, auditability)** — not a single
coverage number. The naive "answers more use cases?" is won by an LLM by
construction; the substrate's claim is coverage **at soundness 1, with a total gap
boundary, and a replayable trace**.

### 5.2 What a use case is, and the *closable* space

A use case is an **anchor structure**: a goal/question over the models' terms
(`buy.what = "underrated"`; `step.next = #j`; `deadline < depart`). Its
**trajectory** is chosen by the engine each step, not coded. Two consequences fix
the metric:

- The reachable use cases are the **combinatorial closure** of the model set's
  concepts and relations — the **closable space** (finitary once typed: ADR-10's
  schema is the type system that keeps it finite).
- Everything *not* closable is a **gap**, and that is a **correct** outcome, not a
  coverage failure — exactly plan-ux §6's *"anchors constrain; they never
  synthesize."*

So the metric is **coverage of the closable space**, plus an assertion that the
rest are gaps — not raw coverage, which a guesser can inflate.

### 5.3 The generator — a use-case family over a fixed toolbox

One generator: a **fixed toolbox** (the N models) and a **grammar** over its
concepts producing a use-case family, mechanically scored (goal reached / answer
correct — reusing `checks`). Split the family:

| split | what it tests | expected |
|---|---|---|
| **seen** | the authored/calibrated cases | covered (sanity) |
| **held-out composition** | a **new conjunction** of known concepts (each known, the combination never authored) | **covered** — this is the claim |
| **held-out concept** | a use case needing a term no model defines | **gap** — this is the boundary |
| **held-out shape** | a new *goal shape* (scope vs order vs optimize) over known concepts | covered, or a named reshape if not |

Without the last two splits the metric is gameable (coverage is trivially
inflatable by answering everything); they are what make "scaling" mean
*composition* and not *guessing*.

### 5.4 Baselines — same toolbox, same budget

Hold the toolbox fixed and the authoring/training budget fixed; vary only **how the
system decides what to do**. Then coverage is comparable:

| baseline | per-use-case cost | where it should win / lose |
|---|---|---|
| **ad-hoc program** | **code per use case** (a branch each) | wins only on cases someone coded; coverage ≈ code |
| **LLM agent, same tools** | zero code, **per prompt** | covers broadly, **unsound tail** — no total gap boundary, no replay guarantee |
| **fixed pipeline** | zero code, but **one path** | fails held-out *composition* by construction |
| **substrate** | zero code | predicted: covers held-out **composition**, gaps held-out **concept**, sound + replayable |

The interesting curve is **coverage at fixed soundness** (and at a fixed
auditability requirement): re-plot the LLM baseline at the soundness the substrate
guarantees, so a raw-coverage win cannot hide an unsound tail.

### 5.5 The scaling statistic — *fan-out per concept*

The claim is not "covers more" but "coverage grows **per authored concept**, not
per authored use case." So report:

> **fan-out** = new held-out use cases covered, per **concept or bridge added** to
> the model set.

A rules engine that needs a rule per case has fan-out ≈ 1 (linear); the substrate's
bet is **superlinear** fan-out — a concept composes into many use cases, the
use-case analogue of D9's "one split cuts a whole subtree." This single number is
the sharp version of "scales in use cases," and it is again a **slope**: measured
as the model set grows, and as the use-case family grows.

### 5.6 Pre-registered predictions

1. Substrate **covers held-out compositions** of known concepts, **gaps held-out
   concepts**, at **soundness 1** on the covered set.
2. Coverage **fan-out per concept > 1**, rising with the model set (the
   combinatorial-closure bet).
3. The LLM baseline beats the substrate on **raw coverage**, and loses on
   **coverage-at-soundness-1-with-a-replayable-trace** — the crossing point is the
   result.
4. A fixed pipeline loses held-out composition by construction (a control that
   **must** fail).

### 5.7 Negative controls

- A use case needing an **unknown concept** must **gap**, never answer — the test
  that "no code" is not "guess."
- **Paraphrase vs structure**: the same use case re-phrased (U7, the NL edge) must
  coerce to the same anchors and the same trajectory — else coverage is
  surface-form, not composition.
- **No per-case leakage**: the held-out family must share no authored case
  verbatim; a paraphrase of a seen case is not held-out.

**Probe status — the mechanism slice is built.** `loopingrules_ux.t1` (a spike,
pinned by `tests/test_ux_t1.py`) implements the mechanism half: a fixed
three-concept model set (a `what` **choose** concept, and `limit`/`affordable`
**scope** concepts, each rule reading exactly one) over one anchor, plus the
falsifier. Measured: held-out **combinations 5/5**; an unknown concept is a
**gap**; the branch-per-case control passes seen (2/2) and fails **every**
combination (0/5); **one added rule buys 3 use cases**; directives take **9/10
distinct trajectories**. Not yet built: the four baselines (§5.4), the use-case
generator of §5.3, and the **fan-out curve** over a growing model set — `t1`
measures fan-out at a single step.

## 6. Feasibility, and where this sits in the handoff

- **Provable now (cheap):** P1–P4, as soon as `checks` lands (stage 5b, currently
  red). They need only `analyze` + the loop + `checks`.
- **Axis A (composition) — a program (weeks):** §4. Needs the port green → **U3**
  (the island library) → a **D10 maze** + generator → a baseline harness + a strong
  **machine-searched** ad-hoc arm. **Nothing in §4 can precede the substrate.**
- **Axis B (coverage) — a program (weeks, partly parallel):** §5. Needs **U2**
  (the anchor schema + resolution) + **U3** → a **use-case generator** over a fixed
  toolbox → the four baselines. A structured input suffices for the first cut; the
  **NL edge (U7) is optional** (it extends axis B to free text, and is what the
  paraphrase control would exercise).
- **Not feasible at any cost:** a universal "scales better." The honest output is
  a **benchmark plus a regime** — and, as with D10, the **harness may be the
  contribution** more than the verdict.

**Ordering.** Finish the port unchanged, then `checks` → `patterns` → examples →
`r0`. Write this doc **now** so the substrate is built *falsifiable* rather than
retrofitted. Pin **P1–P4** as the first post-port tests (they catch a regression in
the pattern's whole claim); run **§4** after U3 and D10, and **§5** after U2 and U3.

## 7. What would make it a fake proof

Named up front, the way `DECISION_PATTERNS.md` was deleted for being untested
prose:

**Axis A (composition):**

- **A weak baseline** — a straw-man orchestrator. The baseline must be the best
  effort, including the machine-searched arm.
- **Budgets not equalized** — the substrate gets a search and the baseline gets a
  human (or vice-versa).
- **A generator tuned to the substrate's strengths** — shared sub-branches only
  the substrate can exploit.
- **Checks that reward the substrate's internal split structure** — D10's hazard.
- **Measuring one N** and calling it "scaling."
- **Ignoring enumeration + search cost** — the cost both ADR-9 and ADR-13 flag as
  *the* unmeasured one.

**Axis B (coverage):**

- **An unnamed comparator** — "other models" must be pinned to a baseline
  (program, LLM agent, pipeline) before it means anything.
- **Coverage without soundness** — reporting how many use cases are answered, not
  how many are answered *correctly*; a guesser wins that metric by construction.
- **Treating a gap as a failure** — penalizing an honest abstention inflates
  coverage by rewarding guesses, and erases the boundary the claim is *about*.
- **Held-out leakage** — a held-out case that is a paraphrase of a seen one is not
  held-out (see §5.7).
- **Per-case code in disguise** — "growth" that quietly receives one authored case
  per use case has fan-out ≈ 1 and proves nothing about concepts.

## 8. What this does not settle

- **The resource axis** (effort vs examples) — declared, not chosen.
- **The generator's realism** — a maze family is mechanical and cheap, and may be
  a poor proxy for a real multi-model system.
- **How strong "ad-hoc" can be made** — the comparison is only as good as the
  baseline's best effort, which is unbounded.
- **What "other models" means** (axis B) — an LLM agent, a program, and a fixed
  pipeline are three different comparators with three different verdicts; the run
  must name one.
- **Whether coverage fan-out is actually superlinear** — the real empirical
  question, and the one that would refute the combinatorial-closure bet if it came
  back linear (fan-out ≈ 1).
- **How soundness is measured** when a use case admits several valid answers — a
  canonical answer, or an equivalence check.
- **Whether P1's totality survives the tool seam** — `compile_answerer` is the
  substrate's own `Opaque` concession; the composed set is total *except* there.
- **Whether scale is even the right frame.** The pattern may win on
  **auditability, determinism or change-locality** rather than on held-out
  success; that is a different, and possibly stronger, result — and it is what
  P1–P4 already test.

## Open questions

1. Is the scale probe its own package (`loopingrules_maze`), an `examples/`
   family, or a forge fixture — the layout choice D10 also left open?
2. Does "effort" mean tokens (a forge/LM arm) or person-hours (the hand arm), and
   are the two even comparable?
3. Does the ad-hoc baseline get to **specialize per maze**, or must one program
   span the family — and which is the fair reading of "scales"?
4. Are the structural claims (P1–P4) scored as pass/fail, or as curves, so
   "scales" is measured on them too?
5. Should the maze family ship its **ground-truth solutions**, so credit can be
   checked against the optimal path and not only the outcome (D10's open 5)?
6. For axis B, is the **LLM agent** the comparator, or is it out of scope because
   its coverage is unbounded — and if it is the comparator, is
   **coverage-at-fixed-soundness** the right way to make the race fair?
7. Does the coverage family count a use case **once**, or weight it by its
   structure (a deeper conjunction is harder) — i.e. is coverage a count or an
   integral over the closable space?
8. Is a **new use-case shape** (scope vs order vs optimize) a coverage win, or the
   honest boundary of a **new concept** — and who decides which?
