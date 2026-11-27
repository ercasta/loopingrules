# Example exports

Shareable LoopingRules exports, made with `lr export`. Download one and import it:

```bash
lr import folder-scan-0.1.0.lr.zip my-folder-scan
lr serve my-folder-scan
```

| File | What it is |
|---|---|
| [`folder-scan-0.1.0.lr.zip`](folder-scan-0.1.0.lr.zip) | Lists a folder, registers and classifies its files, counts the lines of `.txt` files. |
| [`folder-scan-goal-0.1.0.lr.zip`](folder-scan-goal-0.1.0.lr.zip) | The goal-driven variant: nothing happens until you add a `CountLinesGoal`. |

Both declare that they may run `ls -1p '{}'` and `wc -l < '{}'`. `lr import` shows you these commands. Add `--trust-declared` if you want to trust them right away.
