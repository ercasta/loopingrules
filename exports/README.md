# Example exports

Shareable LoopingRules exports, made with `lr export`. Download one and import it:

```bash
lr import folder-scan-0.2.0.lr.zip my-folder-scan
lr serve my-folder-scan
```

| File | What it is |
|---|---|
| [`folder-scan-0.2.0.lr.zip`](folder-scan-0.2.0.lr.zip) | Lists a folder, registers and classifies its files, counts the lines of `.txt` files, one call per file or in one batch. |
| [`big-folders-0.1.0.lr.zip`](big-folders-0.1.0.lr.zip) | A **controller pack** for folder-scan: prefer the batch when a folder has more than N files. Add it with `lr add-layer big-folders-0.1.0.lr.zip my-folder-scan`. |
| [`folder-scan-goal-0.1.0.lr.zip`](folder-scan-goal-0.1.0.lr.zip) | The goal-driven variant: nothing happens until you add a `CountLinesGoal`. |

The models declare the commands they may run: `ls -1p '{}'`, `wc -l < '{}'`, and for folder-scan also `wc -l '{}'/*.txt`. The controller pack declares none, because controllers can't run anything. `lr import` shows you these commands. Add `--trust-declared` if you want to trust them right away.
