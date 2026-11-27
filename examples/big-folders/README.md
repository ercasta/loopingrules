# big-folders (controller pack)

A pack that contains **only a controller**. It doesn't add any operation; it changes which of [folder-scan](../folder-scan)'s options wins.

folder-scan offers two ways to count lines: one call per file, or one batch call. Its own controllers prefer one call per file. This pack says: **when a folder has more than N files, use the batch.**

N is data in the sheet, not code in the pack:

    ex:settings  ex:batchThreshold  10

The default is 4.

Add it to a folder-scan project:

    lr add-layer big-folders-0.1.0.lr.zip my-folder-scan

It lands in `my-folder-scan/layers/big-folders/`. Delete that folder to remove it.
