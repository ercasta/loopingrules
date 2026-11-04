# An 8-16 hour course: evolving rules over a blackboard

A sprint version of the [study guide](study-guide.md). The guide is the map;
this is the route. Read a little, **build a little**, answer one checkpoint,
move on.

## The finish line

By the end you can state, for this system, four sentences and defend each:

> Fitness and credit come from **XCS** (accuracy-based, niche GA). Generation
> is constrained by **Grammatical Evolution / strongly-typed GP** over the IR.
> Abstractions ("models", islands) are discovered by **library learning**
> (ADFs, Stitch-style compression). Diversity is kept by **MAP-Elites**.

And you have *hand-built* a tiny version of the first three and can point to
where each would live in the repo.

## How the course works

- **Every module has a build.** Reading without building does not stick and
  will make you misjudge what is hard. Budgets below include the build.
- **Hand-build the toys** (25-120 lines each). Do **not** import a framework
  first; a library you did not write teaches you the API, not the idea.
  Libraries are for the *extension* week.
- **A checkpoint is a gate.** If you cannot answer it out loud, redo the
  build before moving on.
- Keep everything in a scratch `labs/` directory.
- **You are not learning the field.** You are learning four mechanisms. If a
  module sprawls, stop and note the gap rather than reading on.

## The core modules (about 12.5 h)

| # | Time | Read | Build | Checkpoint |
|---|---|---|---|---|
| M0 | 0.5 h | this repo's `plan-islands.md`, `plan-forge.md`; `study-guide.md` | the `labs/` dir; a one-line "why am I doing this" | what is the ONE thing that would make this a waste of time? |
| M1 | 1 h | Eiben & Smith ch. 1-3, or Poli Field Guide §1-2 | a (1+1)-ES and a simple GA on OneMax | why does a piecewise-constant objective change the algorithm choice? |
| M2 | 1.5 h | Poli Field Guide §3; Montana (STGP); a Grammatical Evolution overview | tree GP symbolic regression, then make it *typed* | what does GE/STGP buy you when the language is your IR? |
| M3 | **3 h** | Wilson (1995); Butz & Wilson (2001) | a minimal **XCS** that solves MUX-6 | why accuracy-based fitness, and what is a "niche"? |
| M4 | 2 h | Koza (ADFs); DreamCoder (idea); Stitch (method) | evolve a **reusable subroutine** on a task with a shared subexpression | state the precondition for library learning; why can it not refactor a black box? |
| M5 | 1.5 h | Mouret & Clune (MAP-Elites); Lehman & Stanley (novelty) | hand-code **MAP-Elites** to illuminate a 2-D task | fitness vs. behavior descriptor; how does this become an island library? |
| M6 | 1 h | "ILP at 30" (skim); FunSearch; OpenEvolve README | run **Popper** on `grandparent` (or read its output) | when ILP, when GP, when LLM-guided? |
| Cap | 2 h | - | write `labs/NOTES.md` (the four sentences + a decision per mechanism) | can you defend each sentence with a *build* you did? |

### M3 is the one that matters

If you only do one module, do M3. XCS is the closest mature machinery to
"evolve the agent's interacting rules," and it already solves the two problems
that will bite you hardest: **credit assignment across interacting rules** and
**over-generalization**. Do not just read it - implement it. The algorithm is
roughly: match the current state against the population; form the prediction
array; pick an action (epsilon-greedy); update prediction, prediction error,
and *fitness* by Q-learning on the reward; run the GA inside the *action set*
only; insert/delete by niche. MUX-6 is the standard first target.

## The builds, precisely

Small enough to finish, big enough to teach. Each names an acceptance test.

- **M1 - `es_onemax.py`.** (1+1)-ES and a simple GA on OneMax (100 bits,
  all-ones optimum). Accept: GA reaches 100/100 in under ~5k evaluations.
  Then re-answer with your own system in mind: your knobs give a
  *piecewise-constant* reward, so remember why `search` in the calibration
  kit is grid, not gradient.
- **M2 - `gp_symbolic.py`.** Tree GP for `f(x) = x*x + x` on `[-1, 1]`.
  Accept: MSE < 1e-3. Then give the function set two types (`bool`, `float`)
  and force crossover to respect them. Accept: no type-invalid tree is ever
  produced.
- **M3 - `xcs_mux.py`.** Minimal XCS on MUX-6. Accept: >= 95% correct actions,
  population under ~1000, with a *compact* general solution (watch maximal
  generality). Then the transfer: re-express the action set as *the rules
  whose reads are satisfied in the current world state*, using the repo's
  `World.changes` log as the firing context.
- **M4 - `adf.py`.** Evolve a program plus one invented subroutine on a task
  with an obvious shared subexpression. Accept: the subroutine gets reused
  across the population and shortens solutions. (Or run **Stitch** on a tiny
  list/arithmetic corpus and inspect the library it invents.)
- **M5 - `mapelites.py`.** MAP-Elites on a 2-D navigation or arm task.
  Accept: archive fills to a performance gradient across behavior cells.
- **M6 - `popper_run`.** Popper on the `grandparent` example. Accept: it
  induces `grandparent(X,Z) :- parent(X,Y), parent(Y,Z)`.
- **Capstone - `labs/NOTES.md`.** One page: the four sentences, each with the
  build that grounds it, plus *the concrete decision for your IR* (what is the
  genotype, what is the credit mechanism, what is inspectable vs. a tool).

## The 8-hour cut

If you have one day: **M0 + M1 + M3 + Capstone**, and skim (do not build)
M2 and M5.

- M0 (0.5) + M1 (1) + M3 (3) + Capstone (2) = **6.5 h** of work, plus ~1.5 h
  of reading. That is the 80/20: XCS's credit mechanism plus the mapping onto
  your system. Skip M4/M6 entirely on this cut; you can come back.

## The 16-hour extension

With the second day, add depth, not breadth:

1. **GE properly** (2 h): build the genotype-to-grammar mapping instead of
   typed trees; make the IR the grammar; confirm every genome decodes to a
   valid rule.
2. **XCSF** (2 h): extend your XCS to continuous inputs (function
   approximation) - this is what a real numeric blackboard needs.
3. **Library learning for real** (2 h): run Stitch/LILO on a real benchmark
   and read the library it discovers.
4. **ILP depth** (2 h): Popper beyond `grandparent` - mode declarations are
   precisely your schema constraint; feel how they bound the search.
5. **LLM-guided loop** (2 h): run **OpenEvolve** on one toy; see the LLM as
   the mutation operator inside the EA you already built.
6. **Read the two surveys** (1 h): "ILP at 30" and the LCS survey. This is
   where you stop treating the field as black boxes.

## What to ignore (anti-goals)

- Do not read surveys cover to cover; use them as indexes.
- Do not chase the newest paper - this corner moves faster than your project.
- Do not learn a framework (DEAP, pyribs, XCSF) *before* the toy. After is fine.
- Do not try to learn neuro-symbolic / differentiable rule induction yet; note
  it exists and move on.
- Do not try to make the toys good. They exist to be *finished*.

## Done looks like

A one-page `labs/NOTES.md` you can hand to a colleague, where every claim
points at a toy you built, and where the four mechanisms have each been
assigned a concrete place in the repo's IR. If you cannot point at a build,
you have read a survey, not learned a mechanism.

## Sources

All references (authors, years, and what to read first) are in the
[study guide](study-guide.md). The minimal set for this course:

- Poli, Langdon & McPhee, *A Field Guide to Genetic Programming* (2008, free).
- Wilson, *Classifier Fitness Based on Accuracy* (1995); Butz & Wilson,
  *An Algorithmic Description of XCS* (2001).
- Montana, *Strongly Typed Genetic Programming* (1995).
- Koza, *Genetic Programming II: Automatic Discovery of Reusable Programs* (1994).
- Ellis et al., *DreamCoder* (2021); Bowers et al., *Stitch* (2023).
- Mouret & Clune, *MAP-Elites* (2015).
- Cropper, Dumančić, Evans & Muggleton, *Inductive Logic Programming at 30* (2022).
- Romera-Paredes et al., *FunSearch* (2024); OpenEvolve (2025).
