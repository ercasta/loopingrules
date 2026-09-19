# The engine and channels

`Engine` (`engine.py`) is one thread that owns a `Loop` and any number of
**channels**.

```python
engine = Engine(loop)
engine.attach(my_terminal)       # each channel is anything with the contract below
engine.attach(my_socket_server)
engine.run()                     # blocks: THE thread that touches the world
```

Terminals, WebSocket servers and clients are **not** in this package. They
live in `harneskills` (`repl`, `serve`, `client`) or in your code.

## A channel is a duck type

No base class. Four members:

| Member | Called | Purpose |
|---|---|---|
| `name` | on attach | unique `str`. The engine sets `ch1`, `ch2`... if it is unset. `"user"` is reserved |
| `start(engine)` | on attach | optional. Start your threads here |
| `deliver(message)` | from the engine's thread | receive a dict. Must not block for long |
| `close()` | on detach or shutdown | optional |

If `deliver` raises, the engine drops that channel and carries on. One dead
socket does not end the session.

A minimal channel, verified against this codebase:

```python
import threading
from loopingrules import Engine, Loop
from loopingrules.world import Said, reply

class Collector:
    name = "test"
    def __init__(self): self.got = []
    def start(self, engine): pass
    def deliver(self, message): self.got.append(message)
    def close(self): pass

loop = Loop()

@loop.rule
def echo(w):
    for e, s in w.each(Said):
        w.destroy(e)
        reply(w, "you said " + s.text, s.channel)   # only to the asker

engine = Engine(loop)
ch = Collector()
engine.attach(ch)
t = threading.Thread(target=engine.run); t.start()
engine.post(ch, "say", "hello")
engine.post(ch, "command", "/rules")
engine.post(ch, "stop")
t.join()
print(ch.got)
```

Output:

```
{'settled': {'revision': 0, 'entities': 0}}
{'reply': {'channel': 'test', 'text': 'you said hello'}}
{'settled': {'revision': 6, 'entities': 0}}
{'lines': [' 1. __main__.echo']}
```

## Messages in: `post(channel, kind, text=None)`

`post` is the **only way in**, and it is thread-safe. It puts a tuple on a
queue, and the engine's thread handles it via `_do`:

| kind | effect |
|---|---|
| `say` | spawn `Said(channel.name, text)`, then `settle()` |
| `get` | send this channel `{"world": save.dump(world)}` |
| `command` | run a slash command on the engine thread |
| `stop` | shut down: close and detach every channel, end `run` |

Any other `kind` is silently ignored. `stop` is a message rather than a
direct call so that it lands in order behind whatever the channel said just
before it. A channel may call `engine.stop()` directly for "right now, whatever
is queued."

### Slash commands

Built in: `/show` (one line per entity) and `/rules` (the numbered rule
list). Others come from `Engine(loop, commands={"/name": fn})`, where
`fn(engine, argument)` runs on the engine thread. If `fn` returns a new
`Loop`, the engine adopts it and settles. Every channel stays attached, and
only the world beneath them changes. That is how `/reload` works. An unknown
command returns `{"error": {"text": "no such command: ..."}}`.

## Messages out

| Message | Meaning |
|---|---|
| `{"reply": {"channel", "text"}}` | a `Reply` entity, consumed |
| `{"unheard": {"text"}}` | a `Said` no rule claimed, reported only once settled |
| `{"error": {"text"}}` | a rule raised, or the loop gave up after `budget` ticks |
| `{"lines": [...]}` | a command's own output |
| `{"settled": {"revision", "entities"}}` | the world stopped moving |
| `{"world": [...]}` | reply to `get` |

## Who hears what

`"user"` means **everyone**. `reply(w, "text")` (channel defaults to
`"user"`) is broadcast to every attached channel, which is what a shared
world means. A `Reply` addressed to a channel's own name goes only there:
carry `said.channel` off the `Said` you consumed to answer just the asker.

## `settle()` and `on_settle`

`settle()` runs the loop to quiescence, draining replies after **every**
tick, not just at the end. A rule that stops to ask a question must not do
so above what the same tick already said. Then it drains, reports any hot
rules, broadcasts `settled`, and calls `on_settle(loop)` if given. That is the
hook for persistence:

```python
Engine(loop, on_settle=lambda lp: save.write(lp.world, "world.jsonl"))
```

`settle()` also runs once at the start of `run()`, so a domain that had
something to say at install time gets to say it.

## Threading rules

- Only the engine thread touches the world or calls a rule.
- Channels touch only `post()` and their own `deliver()`.
- The channel list is protected by a lock. The world needs none.
