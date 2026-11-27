# folder-scan-goal

Goal-driven variant of folder-scan. Nothing happens until you state a goal:

    ex:g1  a          ex:CountLinesGoal
    ex:g1  ex:folder  ex:target

Add those two triples in the sheet; autocomplete knows the goal's shape. Then press ▶ Autopilot. It stops right after marking the goal `lr:reached`.
