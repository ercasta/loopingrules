# folder-scan

Lists a folder with `ls`, registers each file, classifies it by extension, and counts the lines of `.txt` files with `wc`.

1. Set `ex:path` on `ex:target` to the folder you want to scan. The path is relative to where you run `lr serve`.
2. Press ▶ Autopilot, and approve the shell calls (or trust them with *Always allow…*).

## Two ways to count

The model offers two strategies for counting lines: one `wc -l < 'file'` call per file, or a single `wc -l 'folder'/*.txt` batch. The base controllers prefer one call per file. To switch to the batch for big folders, add the [`big-folders`](../big-folders) controller pack:

    lr add-layer exports/big-folders-0.1.0.lr.zip my-folder-scan
