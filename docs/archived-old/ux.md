Work in progress - do not touch

I think we have to start thinking about the "user experience" of the system. The idea is that someone can install this system, provide some rules and examples, potentially launch a training so the "control network" is grown, and then spawn agents based on the rules it provided. 

Looking at the examples, a user might want to create an agent that helps in planning train trips, or suggest what cards to sell / buy, or check github commits according to "house rules".

The value proposition is that this system allows creating these kind of agents without having to code, and not even having to "low code" workflows (remember, the "computation pattern" is stygmergy over a blackboard, with the rules creating a trajectory). The idea is that people can share their agents / rules on some kind of repository (even a sharepoint) by packaging them.

One reason we recently switched from entity-components to entity-attributes is that the structure is simpler and potentially does not require coding python classes and functions, assuming we have a "language" that can express all we need to do.

For sure we need the agent to be able to use tools. I am assuming the engine provides support for tool calling by creating suitable entities and components. That is, the engine requires agents to adopt a convention, and the engine performs the tool calling. This means that if we want to use existing tools like command line tools, apis, etc, we need a mapping (even a standard one based on conventions) to "render" entity-attributes into tool input, and "parsing" tool output (it might be also be a structured output so no need for real parsing) into entity-attributes.

also a very important part is how we interact with the user i.e. how we translate the user input in an "entity-attribute" structure on which the agent can then operate. i am thinking about a text-based interaction but in general we might also have rich user interfaces. The point is i'd like the interaction to be driven by the underlying model the agent understands, either via autocompletion based on schema, or via something else. I am thinking about a list of short "instructions" that are then combined together. Even in this case, I am assuming the engine adopts some conventional entity-attribute schema, like representing commands / instructions with entities, so that it is possible to create "ingestion" rules. One point regarding this is that I expect the engine to "ship with batteries" i.e. a set of "metarules and tools" that allow to "parse" the user input according to the schema the agent understands, so that users do not need to reinvent the wheel any time. 



