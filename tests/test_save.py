"""What the state file promises: the same world, ids and all, next time.

Under the attribute substrate (D8) there is no class to rebuild and no
`module:ClassName` record: a state line is an entity and a dict of its
ATTRIBUTE NAMES to values. Transience is a NAME (`world.transient`), not a
`@transient` class.
"""

from __future__ import annotations

import json

import pytest

from loopingrules import save
from loopingrules.world import World


def peopled():
    """A world shaped like the fs domain's: a folder holding entries that
    point back at it, and a flat list of their ids kept on the folder."""
    w = World()
    folder = w.spawn()
    w.set(folder, "path", "/tmp/notes")
    ids = []
    for name in ("a.txt", "b.bin"):
        entry = w.spawn()
        w.set(entry, "folder", folder)          # a reference
        w.set(entry, "name", name)
        ids.append(entry.id)
    w.set(folder, "names", ids)                 # a flat list of references
    w.mark(w.entity(ids[0]), "stale")
    return w, folder, ids


def roundtrip(w):
    fresh = World()
    records = [json.loads(json.dumps(r)) for r in save.dump(w)]
    assert save.load(fresh, records) == []
    return fresh


# --- the round trip ---------------------------------------------------

def test_everything_comes_back_with_the_same_ids():
    w, folder, ids = peopled()
    back = roundtrip(w)
    assert [e.id for e in back.entities()] == [e.id for e in w.entities()]
    assert back.get(folder, "path") == "/tmp/notes"
    assert back.has(back.entity(ids[0]), "stale")
    assert not back.has(back.entity(ids[1]), "stale")


def test_a_reference_still_points_at_the_same_entity():
    w, folder, ids = peopled()
    back = roundtrip(w)
    assert back.get(back.entity(ids[1]), "folder") == folder.id
    assert back.get(folder, "names") == ids


def test_the_counter_resumes_above_every_restored_id():
    w, _, _ = peopled()
    back = roundtrip(w)
    assert back.spawn().id == 4


def test_a_destroyed_highest_entity_does_not_free_its_id():
    w, _, ids = peopled()
    w.destroy(w.entity(ids[1]))
    assert roundtrip(w).spawn().id == 4


@pytest.mark.parametrize("value", [
    None, True, 17, 1.5, "text", [], [1, "two", None]])
def test_the_value_types_a_world_may_hold(value):
    w = World()
    entity = w.spawn()
    w.set(entity, "value", value)
    assert roundtrip(w).get(entity, "value") == value


def test_an_empty_world_round_trips_to_an_empty_world():
    assert len(roundtrip(World())) == 0


def test_loading_wants_an_empty_world():
    w, _, _ = peopled()
    with pytest.raises(ValueError):
        save.load(w, save.dump(w))


# --- surviving the file itself ----------------------------------------

def test_a_state_file_from_another_version_is_not_guessed_at():
    records = save.dump(World())
    records[0]["version"] = 99
    back = World()
    assert "version" in save.load(back, records)[0]
    assert len(back) == 0


def test_no_file_is_not_a_problem_it_is_a_first_run(tmp_path):
    w = World()
    assert save.read(w, str(tmp_path / "never-written.json")) == []
    assert len(w) == 0


def test_a_corrupt_file_costs_the_world_not_the_session(tmp_path):
    path = tmp_path / "world.json"
    path.write_text("{not json at all", encoding="utf-8")
    w = World()
    problems = save.read(w, str(path))
    assert len(problems) == 1 and str(path) in problems[0]
    assert len(w) == 0
    assert path.exists(), "the file is still there to look at"


def test_writing_makes_the_directory_and_replaces_atomically(tmp_path):
    w, _, _ = peopled()
    path = tmp_path / "deep" / "down" / "world.json"
    save.write(w, str(path))
    save.write(w, str(path))                      # again, over the top
    header = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert header["next"] == 3
    assert not (tmp_path / "deep" / "down" / "world.json.tmp").exists()


def test_written_and_read_back_is_the_same_world(tmp_path):
    w, folder, ids = peopled()
    path = str(tmp_path / "world.json")
    save.write(w, path)
    back = World()
    assert save.read(back, path) == []
    assert back.get(back.entity(ids[0]), "folder") == folder.id


def test_the_file_is_the_same_bytes_on_every_platform(tmp_path):
    w, _, _ = peopled()
    path = tmp_path / "world.json"
    save.write(w, str(path))
    assert b"\r\n" not in path.read_bytes()
    assert path.read_bytes().endswith(b"\n")


def test_one_line_per_record_is_what_makes_it_JSONL():
    w, folder, ids = peopled()
    records = save.dump(w)
    # Header, plus one line per entity that carries a durable attribute --
    # the folder, and the two entries -- nothing nested inside another.
    assert records[0] == {"version": save.VERSION, "next": w._next}
    assert len(records) == 1 + 3


# --- transience is a name ----------------------------------------------

def test_dump_skips_every_transient_name():
    w, folder, _ = peopled()
    w.transient = {"scratch"}
    w.set(folder, "scratch", 1)
    records = save.dump(w)
    folder_record = next(r for r in records if r.get("entity") == folder.id)
    assert "scratch" not in folder_record["attributes"]
    assert "path" in folder_record["attributes"]


def test_a_transient_alongside_durable_ones_writes_normally():
    w, folder, _ = peopled()
    w.transient = {"scratch"}
    w.set(folder, "scratch", 1)
    back = roundtrip(w)
    assert back.get(folder, "path") == "/tmp/notes"
    assert not back.has(folder, "scratch")


def test_an_entity_whose_only_attributes_were_transient_does_not_survive():
    w = World()
    w.transient = {"scratch"}
    scratch_only = w.spawn()
    w.set(scratch_only, "scratch", 1)
    durable = w.spawn()
    w.set(durable, "kept", "yes")
    back = roundtrip(w)
    assert scratch_only.id not in [e.id for e in back.entities()]


def test_a_genuinely_bare_entity_still_round_trips_as_bare():
    w = World()
    bare = w.spawn()
    back = roundtrip(w)
    assert bare.id in [e.id for e in back.entities()]
    assert back.attributes(back.entity(bare.id)) == {}
