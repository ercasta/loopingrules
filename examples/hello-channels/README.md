# hello-channels

The smallest model driven by messages (design D25).

- Send `[] a cmd:Hello ; cmd:name "Ada" .` to `lr:in`.
- The model answers on `lr:out`, and remembers how many times each person said hello.
- Anything else gets a "not understood" answer.
- The package is in **app mode** (`lr:directEdits false`): the sheet is read-only in the UI, and input goes through the Messages panel.

Try it headless:

```bash
printf '[] a cmd:Hello ; cmd:name "Ada" .\n\n[] a cmd:Hello ; cmd:name "Ada" .\n' | lr run examples/hello-channels --listen
```
