# Review

- `world.py`: keep it
- Remove all ⚠ and ⭐ marks from code and docs
- Said, Proposal, Reply, Ripe must all go away from world.py, together with census, arbitrate, etc. The point is: other modules might use a different "terminology" and rules, and everything would be fine, as long as there are "bridging" rules.
- We need to keep a standard way to interact with the "external" (i.e. "tools"). The point is no arbitrary python code should run in the engine in the form of tools.
- The engine should provide a "closed set" of primitives to write rules in (rule-building python functions); the engine should run on a structured representation; not running python rule code directly
- The engine must provide a way to attach to it (channels?)
- The engine might come with a library of useful "patterns".

- Rules must not directly modify the entity-component "blackboard". Each rule specifies the transformations using basic operations: add or remove a component from an entity, create or delete an entity.
- Some rules are used to score alternatives. Scoring rules are the tunable part. 
- Scoring rules are tuned in isolation, based on a training dataset dedicated to that rule.
- The trajectory of the system is actually decided by scoring rules.
