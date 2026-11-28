# rubik-show (policy pack)

A policy for [`rubik`](../rubik) with [`rubik-viewer`](../rubik-viewer): **make one turn, wait until the viewer has shown it, then make the next.** Without it, the model runs the whole plan at once and the viewer plays it back from its queue.

It adds no state and no code: one no-op operation and one controller (`show.ttl`).

| | What |
|---|---|
| `hold the plan until the last turn is shown` (controller) | Scores `turn` −10 while the last executed turn hasn't been announced, or its `viz:Turn` message hasn't been acknowledged. |
| `wait for the viewer` (no-op) | Available while a `viz:Turn` is unacknowledged. It scores 0, so it strictly beats only a held-back turn (D21). |

## How a run goes
With a listening autopilot:
1. **turn** runs, then **announce turn**.
2. **wait for the viewer** wins, and autopilot rests.
3. The viewer animates the turn and acknowledges it. The ack wakes autopilot, and the next turn runs.

## Why a penalty, not a block
- **Only the plan is held back.** A `viz:Sync`, a reset or an announcement still scores 0 and runs: when there's a tie, autopilot keeps going instead of stopping (D21).
- **A block could deadlock.** A viewer that has just loaded waits for the state before acknowledging anything, so its sync must always be answered.

## Install
```bash
lr export examples/rubik-show
lr add-layer examples/rubik-show-0.1.0.lr.zip my-cube   # after rubik-viewer
```

Remove it by deleting `my-cube/layers/rubik-show/`, and the plan runs at full speed again. That's the point of a policy pack: the model and the integration stay the same, and only data changes the behaviour.

`lr run --listen` honours it too: after printing and acknowledging `lr:out`, it runs again before it reads the next input.
