# Review

- We need to keep a standard way to interact with the "external" (i.e. "tools"). The point is no arbitrary python code should run in the engine in the form of tools.
- The engine should provide a "closed set" of primitives to write rules in (rule-building python functions); the engine should run on a structured representation; not running python rule code directly
- The engine must provide a way to attach to it (channels?)
- The engine might come with a library of useful "patterns".

# Tuning
- Some rules are used to score alternatives. Scoring rules are the tunable part. 
- Scoring rules are tuned in isolation, based on a training dataset dedicated to that rule.
- The trajectory of the system is actually decided by scoring rules.
