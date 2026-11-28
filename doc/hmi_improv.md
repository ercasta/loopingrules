I'd like to have:

- a graph representation of the SPOGs rendered maybe in another tab of the ui. The user must be able to pan, zoom in / out, filter, expand / compact a Subject. Links between subjects (are they represented as Objects in regular SPOs?) must be represented; two possible representations: fully connected graphs, or links not visible but clickable and they lead to the spo.
- two subgraphs, called in: and out: . These constitute the I/O channels of the engine. Humans and tools can write "command" (in form of a list of SPOs) in the in: channel, and the engine (via regular rules) can write to out: (as a list of SPOs).
- An integrated tutorial, implemented as regular rules, leveraging in: and out: , that leads the user. The user must become accustomed to "think in SPOGs"
- Also, a structural change: besides operations and controllers, distributable packs might also contain "knowledge" (SPOs) 
- Expose loopingrules as a tool for a coding harness like Claude Code, i.e. implement a stdio MCP server. In this way the LLMs could offload some ops to loopingrules. 
- Evaluate making loopingrules installable as github copilot hooks or pre-commit. Like for example we could have RDF/SHACL/models/controllers that "document" software architecture; and we can have pre-commit hooks that automatically check that architectural properties are respected.


