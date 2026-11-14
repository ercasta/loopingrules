All of our plan still does not clarify what a rule is. What's its shape? And what is a model?

Intuitively, a model is something that says what is allowed and what is not allowed. One of such things is describing the evolution of a system over time.

What if we treat time as a dimension? Actually, if we want to support probabilistic reasoning, each scenario is a different "dimension", i'd say a different universe.

Language is the shadown projected by world models. World models made by humans are not always fully consisent. That's why you can't always blindly apply "fixpoint" computation. That's why you need a control network.

Back to our thinking. What is a "rule", actually? It's a statement you can "apply". Like "if you water a plant, it grows". This sentence is actually the "shadow" of multiple models at play together, one describing and "action", another describing what happens over time. That is, "grows", as a token is the "shadow" of a model. The model is "unnamed", we conventionally decided to give it a name because it is useful to do so, but if we did not have it, we could use other words, but we are describing something that only conventionally has a name. For example we say a plant "grows", and this means its size increases, but also the plant incurs a lot more transformations, its chemical and physical structure changes. Our language does not capture all of this, and even our "models" are an arbitrary selection of some aspects we choose to represent.

So, our models are imperfect and incomplete. The same phenomenon can be described by multiple models, each focusing on different aspects. So "reasoning" is actually "connecting" multiple models, applying them in sequence.

Reasoning is not only verbal, it can be visual. Everyone has its own way of reasoning, everyone chooses its preferred "shadows" to work with.

A model describes relationships. They can be over time, space, or whatever fictitious abstraction we humans named, e.g. you "fill" a jar, you "pay" the rent, and so on. Words are only a convention, what matters are the underlying dynamics. We could use other words, numbers, symbols, etc: as long as they describe the same model, they will represent the same thing.

Like take for example buying and selling. Now, you can model this in several ways. you could say that "the buyer gets an intem and loses money, the seller gest money and loses an item". This is expressed in words, but you could use other formalism, the point is that these concepts are expressed in terms of more fundamental models; in the buying and selling example, when you use a the "get item, lose money" you are effectively connecting multiple models. Models can represent the passage of time, and the concept of losing something, or better, if we decompose it, there are two models jointly in action, one is the passage of time, the other is something being in possession of something, were "possession" is a human abstraction, while time is something we experience as a physical dimension.
"Possession" itself is a model with its own "rules". Ad the same entity can be simultaneously part of two or moder models at play. Rules are the rules of the model. The control network learns which rules to apply.

The point is, we need to adopt a formalism for models that allows composition. It's like deciding the axes of a reference system and express everything based on those: if we use "words" that are not "axis aligned", we create models that "interfere" with one another. I think it doens't really matters which axes we choose, as long as we create models that are "orthogonal" spaces.

Each model actually defines its own "operations". But since the models are imperfect and incomplete, we can't imagine the composition of models as a nice N-dimensional space with operations forming a group. Some rules express operations that might compose information from different axes and even bring to other axes, similar to what vector product does (creates a vector in the third dimension). 

Besides operations, a model also define relations. By relation i mean something that occurs among the "shadows" of entities when looked at through the lenses of a model. For example in the vector space you can define the distance. in model spaces you can have a relation between e.g. a landlord and and a conductor. But also note that the distance itself is an operation defined between different "model spaces", usually distance is an operation between an N dimensional space to 1-dimensional space if you adopt a uniform "numerical vector" formalism, here it's more complex as the different axes are completely different models, but a similar concept applies.

LLMS learn opertations and relationships in vector spaces, by finding pattters in data, and they are so good they find operations and relatioships we humans have no words for! But LLMS use sequences of tokens are entities, arbitrarily picked (attention mechanisms actually dynamically "pick" entities by choosing some tokens from the context.)
