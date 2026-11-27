# LoopingRules: a "semantic spreadsheet"

LoopingRules is "semantic spreadsheet". Instead of working with arbitrary rows and columns, you work with a list of RDF SPOGs. LoopingRules allows you to manipulate the SPOGs, and perform operations either manually, automatically, or mixed.

## Models

A model is made of:
- a set of SHACL validation rules
- a set of operations, i.e. preconditions -> effects i.e. the SPOGs delta

## Controllers

Based on the SPOGs in the sheet, the engine automatically computes all the possible applications of operations. When in manual mode, the user can select the specific application. When on autopilot, the engine leverages controllers.

Controllers are "scoring rules", that score the possible applications. At each "tick", controllers (there can be more than one active at the same time) score the applications. The highest scoring application "wins" and gets executed

## Deriving controllers

Controllers can be authored or derived from user operations. When in manual mode, the system automatically collects user choices, by tracking what the user looks at (to understand the relevant elements) and the what the user chooses (to define the scoring.)

"raw" controllers can be further refined by generalization / antiunification / rule mining techniques like RIPPER.


## "Layered" controllers

Assuming there are several controllers already "loaded", the system can either modify existing controllers, or can "freeze" them and "grow" extra controllers that can outscore the existing ones on specific conditions.

## Environment interaction

LoopingRules allows you to interact with the environment via Tools. Interaction happens in the following way:

1. The user or a rule writes a special set of SPOGs (conforming to a specific "tool calling model")
1. The engine recognizes it and calls the tool
1. The engine gets the result of the tool and adds it as SPOGs

