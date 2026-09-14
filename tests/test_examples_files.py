"""`examples.files` -- `loopingrules.circuits.Call`, proven against real
disk I/O rather than a synthetic stand-in tool. Four things pinned:
the tool actually runs (via the deposited `ToolRequest`/`ToolResult`,
not in place) and its conclusion (`Size`/`Modified`, or `Failed`) lands
in the `World`; the compile-time registry is a hard gate, not a
convention (a spec naming an unregistered tool fails loudly, before any
`World` is touched); a tool only ever receives plain data, never a live
`Entity` -- checked directly, not assumed, with a tool that would fail
its own assertion if handed one; and `reads()`/`writes()` are sound for
`Call` itself now, with the opacity moved to `compile_answerer`'s own
rule.
"""

import pytest

from examples import files
from loopingrules import analyze, circuits
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
    tools = {"stat": spy}
    lp.rule(circuits.compile_circuit(files.do_stat_spec, tools=tools))
    lp.rule(circuits.compile_answerer(tools))
    lp.run()
    assert received == [entry.id]


def test_call_deposits_a_toolrequest_instead_of_running_the_tool_in_place():
    """`Call` spawns a `ToolRequest` in the SAME tick, not a `stat`
    call -- the tool only runs once `compile_answerer`'s own rule (not
    installed here) sees it, so the request stands, unanswered,
    forever."""
    lp = Loop()
    w = lp.world
    entry = w.spawn(files.Entry("irrelevant.txt"))
    w.spawn(files.StatRequest(entry.id))
    lp.rule(circuits.compile_circuit(files.do_stat_spec, tools={"stat": files.stat}))
    lp.run()
    request = w.first(circuits.ToolRequest)
    assert request is not None
    assert request[1] == circuits.ToolRequest("stat", (entry.id,))
    assert w.get(entry, files.Size) is None    # stat never ran: no answerer installed


def test_compile_answerer_deposits_rejected_when_the_tool_raises():
    def boom(w, entry_id):
        raise ValueError("disk on fire")

    lp = Loop()
    w = lp.world
    entry = w.spawn(files.Entry("irrelevant.txt"))
    w.spawn(files.StatRequest(entry.id))
    tools = {"stat": boom}
    lp.rule(circuits.compile_circuit(files.do_stat_spec, tools=tools))
    lp.rule(circuits.compile_answerer(tools))
    lp.run()
    request = w.first(circuits.ToolRequest)
    assert request is not None
    rejected = w.get(request[0], circuits.Rejected)
    assert rejected is not None
    assert "disk on fire" in rejected.reason


def test_reads_is_sound_for_a_call_effect_naming_what_its_args_read():
    assert circuits.reads(files.do_stat_spec) == {files.StatRequest}


def test_writes_includes_toolrequest_for_a_call_effect():
    assert circuits.writes(files.do_stat_spec) == {circuits.ToolRequest}


def test_the_answerer_rule_is_where_the_opacity_now_lives():
    """The claim `loopingrules.circuits`'s own docstring makes -- opacity
    MOVES to `compile_answerer`'s rule, it does not disappear -- checked
    against `loopingrules.analyze`, the module that already refuses to
    guess about a dynamic dispatch it cannot resolve."""
    with pytest.raises(analyze.Opaque):
        analyze.analyze(circuits.compile_answerer({"stat": files.stat}))
