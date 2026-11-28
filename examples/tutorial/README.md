# tutorial

Learn LoopingRules by doing. The tutorial is itself a LoopingRules model (design D26): lessons are data, operations present them and check your exercises, and controllers decide what happens next.

```bash
lr tutorial            # copies it to ./lr-tutorial and opens it on http://127.0.0.1:8765
```

Then tick **listen** and press **▶ Autopilot**. Talk to the tutorial in the Messages panel:

| Message | Effect |
|---|---|
| `[] a tut:Next .` | next lesson (on lessons without an exercise) |
| `[] a tut:Hint .` | a hint for the current lesson |
| `[] a tut:Skip .` | skip the current lesson |

Lessons: messages, a triple, properties and literals, links, shapes, operations, controllers, commands.

Files:
- `sheet.ttl`: the lessons and your progress (`tut:progress tut:current …`), as data;
- `model.ttl`: shapes, the tutorial's operations (present, hint, next, skip, one check per lesson), and the operations of your world, unlocked lesson by lesson;
- `controllers.ttl`: why the tutorial answers first, why autopilot waits for you, and the two greeting styles of lesson 6.

To start over, delete the `.lr/` folder.
