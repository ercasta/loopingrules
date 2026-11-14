"""What a pack promises: a stranger's export, merged into a world that
already has its own entities -- not `save.py`'s promise (the same world,
ids and all, next time), a different one (someone ELSE'S world, remapped,
this time).

Refs are declared by NAME (`world.refs`), not by class field metadata, and
the importing world's own `refs` -- never the file's claim -- decides which
attribute names get remapped.
"""

from __future__ import annotations

import pytest

from loopingrules import share
from loopingrules.world import World


REFS = {"book", "members"}


def a_book_and_its_chapters():
    w = World()
    w.refs = set(REFS)
    book = w.spawn()
    w.set(book, "title", "Moby Dick")
    c1 = w.spawn()
    w.set(c1, "book", book)
    w.set(c1, "number", 1)
    w.set(c1, "heading", "Loomings")
    c2 = w.spawn()
    w.set(c2, "book", book)
    w.set(c2, "number", 2)
    w.set(c2, "heading", "The Carpet-Bag")
    return w, book, c1, c2


# --- the round trip, under id collision --------------------------------

def test_a_reference_follows_its_entity_to_the_new_id_even_under_collision():
    src, book, c1, c2 = a_book_and_its_chapters()
    pack = share.dump_pack(src, [book, c1, c2])

    # The target world's own, UNRELATED entities happen to occupy the exact
    # same id numbers the pack arrives with.
    tgt = World()
    tgt.refs = set(REFS)
    other_book = tgt.spawn()
    tgt.set(other_book, "title", "War and Peace")
    other_chapter = tgt.spawn()
    tgt.set(other_chapter, "book", other_book)
    tgt.set(other_chapter, "heading", "Book One")
    assert other_book.id == book.id and other_chapter.id == c1.id

    problems, mapping = share.load_pack(tgt, pack)
    assert problems == []

    new_book_id = mapping[book.id]
    assert new_book_id not in (book.id,)
    assert tgt.get(other_book, "title") == "War and Peace"   # untouched

    imported = [row for row in tgt.each("heading")
                if row[0].id != other_chapter.id]
    assert {row[1] for row in imported} == {"Loomings", "The Carpet-Bag"}
    assert all(tgt.get(row[0], "book") == new_book_id for row in imported)


def test_a_fresh_entity_is_minted_for_every_pack_entity():
    src, book, c1, c2 = a_book_and_its_chapters()
    pack = share.dump_pack(src, [book, c1, c2])
    tgt = World()
    tgt.refs = set(REFS)
    before = len(tgt)
    _, mapping = share.load_pack(tgt, pack)
    assert len(mapping) == 3
    assert len(tgt) == before + 3
    assert len(set(mapping.values())) == 3        # no two collapsed onto one


def test_a_bare_entity_round_trips_as_bare():
    w = World()
    w.refs = set(REFS)
    bare = w.spawn()
    pack = share.dump_pack(w, [bare])
    tgt = World()
    tgt.refs = set(REFS)
    _, mapping = share.load_pack(tgt, pack)
    assert tgt.attributes(tgt.entity(mapping[bare.id])) == {}


# --- a list of refs: every member is remapped --------------------------

def test_a_list_of_refs_has_every_member_remapped():
    src = World()
    src.refs = set(REFS)
    b1, b2 = src.spawn(), src.spawn()
    anth = src.spawn()
    src.set(anth, "members", [b1, b2])
    pack = share.dump_pack(src, [b1, b2, anth])
    tgt = World()
    tgt.refs = set(REFS)
    _, mapping = share.load_pack(tgt, pack)
    got = tgt.get(tgt.entity(mapping[anth.id]), "members")
    assert set(got) == {mapping[b1.id], mapping[b2.id]}


# --- refusing rather than guessing --------------------------------------

def test_export_refuses_a_ref_pointing_outside_the_pack():
    src, book, c1, c2 = a_book_and_its_chapters()
    with pytest.raises(share.PackError) as raised:
        share.dump_pack(src, [c1])           # book is not included
    assert "book" in str(raised.value)
    assert "#%d" % book.id in str(raised.value)


def test_import_skips_a_dangling_reference_by_name_not_a_crash():
    bad_pack = [
        {"version": share.VERSION},
        {"entity": 1,
         "attributes": {"book": 999, "number": 1, "heading": "Ghost"}},
    ]
    tgt = World()
    tgt.refs = set(REFS)
    problems, mapping = share.load_pack(tgt, bad_pack)
    assert len(problems) == 1 and "999" in problems[0]
    # The entity itself still exists -- it just carries nothing.
    assert len(mapping) == 1


def test_a_pack_declaring_the_wrong_version_is_not_guessed_at():
    problems, mapping = share.load_pack(World(), [{"version": 99}])
    assert "version" in problems[0]
    assert mapping == {}


# --- what stays local, on purpose ---------------------------------------

def test_transient_names_never_leave_the_source_world():
    w, book, _, _ = a_book_and_its_chapters()
    w.transient = {"scratch"}
    w.set(book, "scratch", 1)
    pack = share.dump_pack(w, [book])
    imported = next(r for r in pack if r.get("entity") == book.id)
    assert "scratch" not in imported["attributes"]


def test_the_target_world_decides_what_a_ref_is_not_the_file():
    # A file claims `title` is a reference by putting an id-looking int in
    # it. The target's own `refs` says otherwise, so it is NOT remapped --
    # the file does not get to redefine the receiving domain's attributes.
    src = World()
    src.refs = set(REFS)
    book = src.spawn()
    src.set(book, "title", 42)          # looks like an id; is not a ref
    pack = share.dump_pack(src, [book])
    tgt = World()
    tgt.refs = set(REFS)                # `title` is not a ref here either
    _, mapping = share.load_pack(tgt, pack)
    assert tgt.get(tgt.entity(mapping[book.id]), "title") == 42
