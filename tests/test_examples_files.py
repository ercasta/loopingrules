"""`examples.files` -- `loopingrules.circuits.Call`, proven against real
disk I/O rather than a synthetic stand-in tool. Three things pinned:
the tool actually runs and its conclusion (`Size`/`Modified`, or
`Failed`) lands in the `World`; the compile-time registry is a hard
gate, not a convention (a spec naming an unregistered tool fails
loudly, before any `World` is touched); and a tool only ever receives
plain data, never a live `Entity` -- checked directly, not assumed,
with a tool that would fail its own assertion if handed one.
"""

import pytest

from examples import files
from loopingrules import circuits
from loopingrules.loop import Loop


def _requested(tmp_path, name="hello.txt", content="hi", write=True):
    """A fresh `Loop`, one `Entry` for a file under `tmp_path`
    (optionally written), and a `StatRequest` naming it -- the setup
    every test below starts from."""
    lp = Loop()
    w = lp.world
    path = tmp_path / name
    if write:
        path.write_text(content)
    entry = w.spawn(files.Entry(str(path)))
    w.spawn(files.StatRequest(entry.id))
    return lp, w, entry


def test_do_stat_spec_writes_size_and_modified_from_a_real_file(tmp_path):
    lp, w, entry = _requested(tmp_path, content="hello world")
    files.install(lp)
    lp.run()
    size = w.get(entry, files.Size)
    modified = w.get(entry, files.Modified)
    real = (tmp_path / "hello.txt").stat()
    assert size == files.Size(real.st_size)
    assert modified == files.Modified(int(real.st_mtime))
    assert w.first(files.StatRequest) is None    # claimed and destroyed


def test_do_stat_spec_spawns_failed_when_the_path_does_not_exist(tmp_path):
    lp, w, entry = _requested(tmp_path, name="ghost.txt", write=False)
    files.install(lp)
    lp.run()
    assert w.get(entry, files.Size) is None
    failed = w.first(files.Failed)
    assert failed is not None
    assert "ghost.txt" in failed[1].what
    assert w.first(files.StatRequest) is None    # claimed either way


def test_compile_circuit_refuses_a_call_to_an_unregistered_tool():
    with pytest.raises(KeyError, match="stat"):
        circuits.compile_circuit(files.do_stat_spec, tools={})


def test_compile_circuit_refuses_a_call_with_no_registry_at_all():
    with pytest.raises(KeyError, match="stat"):
        circuits.compile_circuit(files.do_stat_spec)


def test_call_hands_the_tool_a_plain_int_never_a_live_entity(tmp_path):
    """The safety property `Call`'s own docstring claims, checked, not
    just read: a tool that asserts its argument is a plain `int` (the
    same discipline `World.attach` already enforces on a component
    field) must still succeed -- if `Call` ever regressed to passing
    the `Entity` handle `evaluate(Self(...))` resolves against, this
    tool would raise instead."""
    received = []

    def spy(w, entry_id):
        assert isinstance(entry_id, int), "got %r, not a plain int" % (entry_id,)
        received.append(entry_id)

    lp = Loop()
    w = lp.world
    entry = w.spawn(files.Entry(str(tmp_path / "irrelevant.txt")))
    w.spawn(files.StatRequest(entry.id))
    lp.rule(circuits.compile_circuit(files.do_stat_spec, tools={"stat": spy}))
    lp.run()
    assert received == [entry.id]


def test_reads_raises_opaque_naming_the_tool():
    with pytest.raises(circuits.Opaque, match="stat"):
        circuits.reads(files.do_stat_spec)


def test_writes_raises_opaque_naming_the_tool():
    with pytest.raises(circuits.Opaque, match="stat"):
        circuits.writes(files.do_stat_spec)
