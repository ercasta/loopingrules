# arch-check

LoopingRules checking LoopingRules: a module of `engine/loopingrules` may only import from its own layer or the layers below (design D29).

- `knowledge.ttl`: the architecture, as read-only facts (D28): layers, their ranks, and each module's layer.
- `model.ttl`: two shell commands collect the facts (`ls`, then `grep` for each module's relative imports). Operations record them, then report problems as **findings** (`lr:out` messages of type `lr:Finding`).
- `sheet.ttl`: what to check.

Run it from the repository root:

```bash
lr check examples/arch-check --trust-declared
```

Exit code 0 means the layering holds, 1 means there are findings, and 2 means the check couldn't run (e.g. a command wasn't trusted).
