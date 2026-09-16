"""What a pack promises: a stranger's export, merged into a world that
already has its own entities -- not `save.py`'s promise (the same
world, ids and all, next time), a different one (someone ELSE'S world,
remapped, this time)."""

import dataclasses

import pytest

from loopingrules import share
from loopingrules.world import World, transient


@dataclasses.dataclass(frozen=True)
class Book:
    title: str


@dataclasses.dataclass(frozen=True)
class Chapter:
    book: int = share.ref()
    number: int = 0
    heading: str = ""


@dataclasses.dataclass(frozen=True)
class Anthology:
    members: tuple = share.ref(default=())


@transient
@dataclasses.dataclass(frozen=True)
class Scratch:
    value: int = 0


REGISTRY = {
    share._name_of(Book): Book,
    share._name_of(Chapter): Chapter,
    share._name_of(Anthology): Anthology,
}


def a_book_and_its_chapters():
    w = World()
    book = w.spawn(Book("Moby Dick"))
    c1 = w.spawn(Chapter(book.id, 1, "Loomings"))
    c2 = w.spawn(Chapter(book.id, 2, "The Carpet-Bag"))
    return w, book, c1, c2


# --- the round trip, under id collision --------------------------------

def test_a_reference_follows_its_entity_to_the_new_id_even_under_collision():
    src, book, c1, c2 = a_book_and_its_chapters()
    pack = share.dump_pack(src, [book, c1, c2])

    # The target world's own, UNRELATED entities happen to occupy the
    # exact same id numbers the pack arrives with.
    tgt = World()
    other_book = tgt.spawn(Book("War and Peace"))
    other_chapter = tgt.spawn(Chapter(other_book.id, 1, "Book One"))
    assert other_book.id == book.id and other_chapter.id == c1.id

    problems, mapping = share.load_pack(tgt, pack, REGISTRY)
    assert problems == []

    new_book_id = mapping[book.id]
    assert new_book_id not in (book.id,)          # a genuinely fresh id
    assert tgt.get(other_book, Book) == Book("War and Peace")   # untouched

    imported = [c for e, c in tgt.each(Chapter) if e.id != other_chapter.id]
    assert {c.heading for c in imported} == {"Loomings", "The Carpet-Bag"}
    assert all(c.book == new_book_id for c in imported)


def test_a_fresh_entity_is_minted_for_every_pack_entity():
    src, book, c1, c2 = a_book_and_its_chapters()
    pack = share.dump_pack(src, [book, c1, c2])
    tgt = World()
    before = len(tgt)
    _, mapping = share.load_pack(tgt, pack, REGISTRY)
    assert len(mapping) == 3
    assert len(tgt) == before + 3
    assert len(set(mapping.values())) == 3        # no two collapsed onto one


def test_a_bare_entity_round_trips_as_bare():
    w = World()
    bare = w.spawn()
    pack = share.dump_pack(w, [bare])
    tgt = World()
    _, mapping = share.load_pack(tgt, pack, REGISTRY)
    assert tgt.components(tgt.entity(mapping[bare.id])) == []


# --- tuple ref fields: the bug the sketch actually caught ---------------

def test_a_tuple_ref_field_comes_back_a_tuple_not_a_list():
    src = World()
    b1, b2 = src.spawn(), src.spawn()
    anth = src.spawn(Anthology((b1.id, b2.id)))
    pack = share.dump_pack(src, [b1, b2, anth])
    tgt = World()
    _, mapping = share.load_pack(tgt, pack, REGISTRY)
    got = tgt.get(tgt.entity(mapping[anth.id]), Anthology)
    assert isinstance(got.members, tuple)
    assert set(got.members) == {mapping[b1.id], mapping[b2.id]}
    hash(got)  # a frozen component holding a list, not a tuple, is not


# --- refusing rather than guessing --------------------------------------

def test_export_refuses_a_ref_pointing_outside_the_pack():
    src, book, c1, c2 = a_book_and_its_chapters()
    with pytest.raises(share.PackError) as raised:
        share.dump_pack(src, [c1])           # book is not included
    assert "Chapter.book" in str(raised.value)
    assert "#%d" % book.id in str(raised.value)


def test_import_skips_a_dangling_reference_by_name_not_a_crash():
    bad_pack = [
        {"version": share.VERSION},
        {"entity": 1, "type": share._name_of(Chapter),
         "fields": {"book": 999, "number": 1, "heading": "Ghost"}},
    ]
    problems, mapping = share.load_pack(World(), bad_pack, REGISTRY)
    assert len(problems) == 1 and "999" in problems[0]
    # The entity itself still exists -- it just carries nothing.
    assert len(mapping) == 1


def test_import_skips_an_unregistered_type_and_names_it():
    src, book, _, _ = a_book_and_its_chapters()
    pack = share.dump_pack(src, [book])
    problems, mapping = share.load_pack(World(), pack, {})
    assert len(problems) == 1 and "Book" in problems[0]
    assert len(mapping) == 1          # the entity is minted; it carries nothing


def test_a_pack_declares_the_wrong_version_is_not_guessed_at():
    problems, mapping = share.load_pack(World(), [{"version": 99}], REGISTRY)
    assert "version" in problems[0]
    assert mapping == {}


# --- what stays local, on purpose ---------------------------------------

def test_transient_components_never_leave_the_source_world():
    w, book, _, _ = a_book_and_its_chapters()
    w.attach(book, Scratch(1))
    pack = share.dump_pack(w, [book])
    assert not any(r.get("type", "").endswith(":Scratch") for r in pack)


def test_a_registry_never_resolves_a_name_by_importing_it():
    # The whole point of a caller-supplied registry: a pack cannot name
    # an arbitrary importable symbol and have it resolved for it, the
    # way `save._kind` resolves its own trusted state file.
    src, book, _, _ = a_book_and_its_chapters()
    pack = share.dump_pack(src, [book])
    assert not hasattr(share, "_kind")
