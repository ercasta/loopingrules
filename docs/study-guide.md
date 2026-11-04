# Study guide: the systems behind the islands / evolution work

Background reading for the reuse layer (`plan-islands.md`) and the
idea of discovering rules by evolution. It is **not** part of the engine's
design; it is a map of the mature systems this work sits on, so nothing gets
reinvented.

## How to use this

1. **One canonical paper and one survey per system** — never the whole
   literature.
2. **Build the smallest toy** — each system below names its "hello world."
   Reading without building does not stick, and you will misjudge what is
   actually hard.
3. **Map the toy onto the IR** — the real test of *fit* is reproducing the
   toy over the entity/component blackboard.
4. **Write a one-page note per system**, in this repo's own style: *what it
   does / what it does not settle / does it fit.*
5. **Go narrow and deep on three**: XCS (credit), Grammatical
   Evolution/STGP (typing), and library learning (abstractions).

The target: you should be able to say, for this system, *"credit comes from
XCS's accuracy/niche scheme; generation is constrained by Grammatical
Evolution over the IR; abstractions are discovered by Stitch-style
compression; diversity is kept by MAP-Elites."* Four sentences, and the wheel
is not reinvented.

## The systems, in reading order

### Blackboard systems — the ancestor

A shared, accumulating store; *knowledge sources* that fire on conditions; a
scheduler above them. Coordination is by the medium, not by calls.

Why here: it is this substrate, and its four historical failure modes —
matching cost, the control problem, termination, and knowledge acquisition —
are the design brief.

Read: Erman et al., *The Hearsay-II Speech-Understanding System* (1980);
Lee Nii, *Blackboard Systems*, AI Magazine (1986, parts 1 and 2); Jagannathan
et al. (eds.), *Blackboard Architectures and Applications* (1989).

### Genetic Programming / evolutionary computation — the base vocabulary

Trees of functions, evolved by mutation and crossover against a fitness
function.

Why here: every later system extends this.

Read: Eiben and Smith, *Introduction to Evolutionary Computing* (2nd ed.,
2015); **Poli, Langdon and McPhee, *A Field Guide to Genetic Programming*
(2008) — free PDF, the best first read**; Koza, *Genetic Programming* (1992).

Toy: symbolic regression of `f(x) = x*x + x`. Code: DEAP, `gplearn`.

### XCS (Learning Classifier Systems) — study hardest

A population of `condition -> action` rules where **fitness is accuracy, not
reward**, and the genetic algorithm acts only inside the *action set* (the
rules matching the current state); reward is assigned by Q-learning-style
updates.

Why here: a blackboard is an XCS environment — states are component
configurations, actions are rule firings — and the `World.changes` log is
exactly the firing context XCS needs. This is the closest mature machinery
to "evolve the agent's interacting rules," and it already solves per-rule
credit assignment and over-generalization.

Read: Wilson, *Classifier Fitness Based on Accuracy* (1995); Butz and Wilson,
*An Algorithmic Description of XCS* (2001); Urbanowicz and Moore, *Learning
Classifier Systems: A Complete Introduction, Review, and Roadmap* (2009);
plus the recent 2022-2024 survey.

Toy: the multiplexer (MUX) benchmark, or Wilson's "woods" maze. Code: XCSF,
ExSTraCS.

### Grammatical Evolution and Strongly Typed GP — the schema constraint

GE evolves an integer genome mapped through a BNF grammar, so invalid programs
are never generated; STGP attaches types to terminals and restricts crossover
to type-compatible subtrees.

Why here: the grammar *is* the IR plus the component schema; the type system
*is* the entity/component structure.

Read: Ryan, Collins and O'Neill (1998); O'Neill and Ryan, *Grammatical
Evolution* (2003); Montana, *Strongly Typed Genetic Programming* (1995). Also
PushGP (Spector and Robinson, 2002) for type-safe multi-type programs.

Toy: evolve an arithmetic expression over a tiny BNF; then redo it typed.
Code: PonyGE2, GEVA.

### Automatically Defined Functions — reusable subroutines found by evolution

GP with a main program plus invented subroutines it can call and reuse.

Why here: "models" are ADFs; it is the proof that evolution can discover
reusable abstractions.

Read: Koza, *Genetic Programming II: Automatic Discovery of Reusable
Programs* (1994). Toy: parity, or a regression with a shared subexpression.

### DreamCoder and library learning — the island-building machinery

Wake-sleep: solve tasks by search using the current library; then *compress*
the solved programs into new reusable abstractions (via E-graph refactoring)
and add them to the library. The library and the search policy bootstrap each
other.

Why here: this is precisely the progressively-built island library.

Read: Ellis et al., *DreamCoder* (PLDI 2021); **Stitch** (Bowers et al., POPL
2023) and **LILO** (Grand et al., 2023) — the practical modern systems to
build on.

Toy: the small list/arithmetic "curve" or text-editing domains.

### Quality-Diversity: MAP-Elites and novelty search

Keep the best solution *per cell* of a behaviour-descriptor grid, not just the
global best, producing a map of diverse high-performing behaviours.

Why here: this is how to get an island library (diverse behaviours) instead
of one agent.

Read: Mouret and Clune, *MAP-Elites* (2015); Lehman and Stanley, *Novelty
Search* (2011); Cully and Demiris survey (2017). Code: pyribs, qdax.

Toy: illuminate a 2-D navigation or walker task.

### Inductive Logic Programming and Meta-Interpretive Learning — rules over a declared, typed predicate set

ILP induces Datalog/Prolog rules from examples plus background knowledge,
constrained by mode declarations (types).

Why here: it is the blackboard rules, learned, with the typing discipline
built in.

Read: Muggleton, *Progol* (1995); **Cropper, Dumančić, Evans and Muggleton,
*Inductive Logic Programming at 30* (2022) — the modern survey**; Muggleton
et al., *Meta-Interpretive Learning*.

Toy: learn `grandparent(X, Z)` from `parent`. Code: Popper, Aleph, Metagol.

### LLM-guided evolution — the authoring helper, never the runtime

An LLM proposes edits; an automatic evaluator scores; an evolutionary loop
(often island-based, with a MAP-Elites archive) keeps the good ones. The LLM
is the *mutation operator* inside the EA.

Why here: it is "LLM-helped authoring plus an EA" — the LLM is used only to
propose, never at run time.

Read: FunSearch (Romera-Paredes et al., *Nature* 2024); AlphaEvolve (Novikov
et al., 2025); then OpenEvolve, ShinkaEvolve, CodeEvolve (2025).

Note: this corner moves fastest; check for newer work before relying on it.

### Options and hierarchical RL — the frame for "models"

A temporally-extended action ("option") is a policy plus a termination
condition; a "model" is a learned dynamics predictor you plan with.

Why here: "a rule calls a model" is a macro, and the tags in this repo
already behave like option-termination conditions.

Read: Sutton, Precup and Singh, *Between MDPs and semi-MDPs* (1999); Sutton
and Barto, *Reinforcement Learning* (2nd ed., free PDF), the options chapter;
Dyna (Sutton, 1991).

## A six-week path

- **Weeks 1-2**: blackboard history; GP fundamentals (Poli's Field Guide);
  one `gplearn` example.
- **Weeks 3-4**: XCS end to end on the multiplexer, then re-implement its
  credit over a toy blackboard using the change log. Highest-value weeks.
- **Week 5**: Grammatical Evolution and STGP; make the IR the grammar.
- **Week 6**: library learning (Stitch/LILO, then DreamCoder) and MAP-Elites
  (pyribs).
- **As needed**: ILP (Popper) and LLM-guided evolution (OpenEvolve).

## Offline and phone

This page is part of the MkDocs site, so it is published to the project's
GitHub Pages and readable in any mobile browser. For reading away from a
browser, the same Markdown converts to an EPUB or PDF with `pandoc`, and the
whole `docs/` directory can be read in any Markdown app or the GitHub mobile
app.
