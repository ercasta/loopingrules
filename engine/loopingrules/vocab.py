"""The lr: vocabulary and the built-in shapes for tool calls."""

from rdflib import Namespace

LR = Namespace("https://loopingrules.org/ns#")

# Operation:   lr:where / lr:delete / lr:insert  (SPARQL fragments as strings)
# Controller:  lr:query (SPARQL SELECT returning ?score), lr:active (boolean)
# Tool calls:  lr:ShellCall with lr:command, lr:status,
#              lr:exitCode, lr:stdoutLine / lr:stderrLine -> [ lr:index ; lr:text ]
# Statuses:    lr:Pending, lr:Done, lr:Rejected, lr:Failed

PENDING = LR.Pending
DONE = LR.Done
REJECTED = LR.Rejected
FAILED = LR.Failed

BUILTIN_SHAPES = """
@prefix lr: <https://loopingrules.org/ns#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

lr:ShellCallShape a sh:NodeShape ;
  sh:targetClass lr:ShellCall ;
  sh:property [ sh:path lr:command ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path lr:status ; sh:minCount 1 ; sh:maxCount 1 ;
                sh:in ( lr:Pending lr:Done lr:Rejected lr:Failed ) ] ;
  sh:property [ sh:path lr:exitCode ; sh:maxCount 1 ; sh:datatype xsd:integer ] .
"""
