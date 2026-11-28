Let's review the operations and controlles. Keeping in mind the future learnability, we need to make sure:
- controllers can score the "no op" making it win (and this stops autopilot, of course). Otherwise the system would go on applying rules even when the correct choice is to stop
- we need to score the delta i.e. we need to be able to say "given this initial situation, this delta looks better than another"
- the operations must allow not a single SPARQL expression but more arbitrary transformations. A single SPARQL expression might not be enough to move the SPOGs from a consistent state to another consistent state
- how are preconditions expressed in operations? Again, it's a matter of model consistencies, some operations might only be valid if some precondition holds.
- If needed, we can invent our language
- we need operations to bind to specific values, a SPARQL expression might bind to too many values at once
- applying operations and scoring must be high performance as they are the core of the system
