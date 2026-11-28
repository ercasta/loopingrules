# rubik-viewer (pack)

Shows a [`rubik`](../rubik) cube in 3D. The pack is the model's side, and `app/` is the external program. They only talk through the channels (D25): the viewer posts to `lr:in`, reads `lr:out`, and acknowledges what it has shown. It never edits the sheet.

## The pack (`viz.ttl`)
| Operation | What |
|---|---|
| `announce turn` | Every executed turn, once, becomes `[] lr:channel lr:out ; a viz:Turn ; viz:move mv:R ; viz:seq 17`. |
| `send the cube's state` | Answers `[] a viz:Sync` with a `viz:State`: the 54 colours (`viz:facelet [ viz:pos pos:U1 ; viz:colour rk:White ]`) and `viz:turns`, how many turns they include. |

The state message's IRI is derived from the request (`BIND(IRI(CONCAT(STR(?m), "-state")) AS ?s)`). That way its step can add all 54 facelets to the same message: a fresh `[]` would mint a new message for every row.

## The app (`app/`)
A small Vite + TypeScript + Three.js page:
- **Turns are shown in order, one at a time.** The viewer animates each `viz:Turn` in `viz:seq` order, then acknowledges it. **The ack means "displayed"**: a pacing policy (`rubik-show`) waits for it.
- **The model decides the colours.** A `viz:State` overwrites what the viewer shows, and turns it already includes are skipped.
  - The viewer asks for the state when it starts, after a reset, and when it finds a gap in the turns (e.g. someone else acknowledged some).
  - It also polls slowly, in case a WebSocket event is lost.
- **Buttons:**
  - **Scramble** posts `rk:Scramble` with 20 random moves;
  - **Reset** posts `rk:Reset`;
  - **Sync** posts `viz:Sync`.
- **On load,** it starts a listening autopilot (`POST /api/autopilot/start {listen: true}`), so posts are handled as they arrive.

## Run it
```bash
cp -r examples/rubik my-cube                          # a project of your own (the example stays clean)
lr export examples/rubik-viewer                       # -> examples/rubik-viewer-0.1.0.lr.zip
lr add-layer examples/rubik-viewer-0.1.0.lr.zip my-cube
lr serve my-cube                                      # API on :8765

cd examples/rubik-viewer/app && npm install && npm run dev   # http://localhost:5180
```

The dev server proxies `/api` to `lr serve`, so the page and the API share an origin. The LoopingRules UI on :8765 shows the same run: the turns, the messages, and the pack's operations.
