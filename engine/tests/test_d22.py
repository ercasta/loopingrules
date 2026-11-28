"""Design D22: operation parameters, guards, postconditions and steps."""

import pytest
from rdflib import Graph, Literal, Namespace
from rdflib.namespace import RDF

from loopingrules.engine import Engine
from loopingrules.operations import load_operations
from loopingrules.patterns import UnsupportedPattern
from loopingrules.project import Project

EX = Namespace("https://example.org/")
PFX = ("@prefix lr: <https://loopingrules.org/ns#> . @prefix ex: <https://example.org/> . "
       "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n")

# Two folders; ex:d1 has two tagged files and a pending scan.
SHEET = PFX + '''
ex:d1 a ex:Folder ; ex:scanned true .
ex:d2 a ex:Folder ; ex:scanned true .
ex:f1 ex:inFolder ex:d1 ; ex:tag "a", "b" .
ex:f2 ex:inFolder ex:d1 ; ex:tag "c" .
ex:f3 ex:inFolder ex:d2 ; ex:tag "d" .
ex:scan1 ex:scanOf ex:d1 ; ex:status ex:Pending .
'''


def make(tmp_path, model: str, sheet: str = SHEET) -> Engine:
    (tmp_path / "model.ttl").write_text(PFX + model)
    (tmp_path / "controllers.ttl").write_text(PFX)
    (tmp_path / "sheet.ttl").write_text(sheet)
    return Engine(Project.load(tmp_path, persist=False))


def apps_of(eng, name):
    return {str(a.bindings.get("folder", "")).rsplit("/", 1)[-1]: a
            for a in eng.applications() if a.operation.name == name}


# --- lr:params --------------------------------------------------------------

UNTAG = '''
ex:untag a lr:Operation ; rdfs:label "untag folder" ;
  lr:params "folder" ;
  lr:where  "?folder a ex:Folder . ?f ex:inFolder ?folder ; ex:tag ?t ." ;
  lr:delete "?f ex:tag ?t ." .
'''


def test_params_merge_solutions_into_one_application(tmp_path):
    eng = make(tmp_path, UNTAG)
    apps = apps_of(eng, "untag folder")
    assert set(apps) == {"d1", "d2"}
    assert apps["d1"].bindings == {"folder": EX.d1}
    assert apps["d1"].deletes == {(EX.f1, EX.tag, Literal("a")), (EX.f1, EX.tag, Literal("b")),
                                  (EX.f2, EX.tag, Literal("c"))}


def test_without_params_every_solution_is_an_application(tmp_path):
    eng = make(tmp_path, UNTAG.replace('lr:params "folder" ;', ""))
    assert len(eng.applications()) == 4


def test_the_application_id_depends_on_the_params_only(tmp_path):
    eng = make(tmp_path, UNTAG)
    before = apps_of(eng, "untag folder")["d1"].id
    eng.edit(add=[(EX.f9, EX.inFolder, EX.d1), (EX.f9, EX.tag, Literal("z"))])
    assert apps_of(eng, "untag folder")["d1"].id == before


@pytest.mark.parametrize("params", ['"?folder"', '"folder, f"', '"folder", "f"', '"?folder ?f"'])
def test_params_spellings(params):
    g = Graph().parse(data=PFX + UNTAG.replace('lr:params "folder"', f"lr:params {params}"), format="turtle")
    [op] = load_operations(g)
    assert op.params[0] == "folder"


def test_params_must_be_bound_by_where():
    g = Graph().parse(data=PFX + UNTAG.replace('lr:params "folder"', 'lr:params "folder nope"'), format="turtle")
    with pytest.raises(ValueError, match=r"\?nope not bound"):
        load_operations(g)


# --- lr:requires / lr:ensures ---------------------------------------------------

GUARDED = UNTAG.replace('lr:params "folder" ;', '''lr:params "folder" ;
  lr:requires [ rdfs:label "no scan in progress" ;
                lr:ask "FILTER NOT EXISTS { ?c ex:scanOf ?folder ; ex:status ex:Pending }" ] ;''')


def test_a_failing_guard_blocks_the_application_and_says_why(tmp_path):
    eng = make(tmp_path, GUARDED)
    apps = apps_of(eng, "untag folder")
    assert not apps["d1"].valid and not apps["d1"].deletes
    assert [(v["component"], v["message"]) for v in apps["d1"].violations] == [("lr:requires", "no scan in progress")]
    assert apps["d2"].valid
    assert eng.step().application.bindings == {"folder": EX.d2}


def test_a_guard_can_be_a_plain_pattern(tmp_path):
    model = UNTAG.replace('lr:params "folder" ;', 'lr:params "folder" ; lr:requires "?folder ex:scanned true" ;')
    eng = make(tmp_path, model)
    assert all(a.valid for a in eng.applications())
    eng.edit(remove=[(EX.d2, EX.scanned, Literal(True))])
    apps = apps_of(eng, "untag folder")
    assert apps["d1"].valid and not apps["d2"].valid
    assert apps["d2"].violations[0]["message"] == "?folder ex:scanned true"


def test_a_failing_postcondition_makes_the_application_invalid(tmp_path):
    # untagging must leave the folder with at least one tag: never true here
    model = UNTAG.replace('lr:params "folder" ;', '''lr:params "folder" ;
      lr:ensures [ rdfs:label "some tag left" ; lr:ask "?f ex:inFolder ?folder ; ex:tag ?t" ] ;''')
    eng = make(tmp_path, model)
    apps = apps_of(eng, "untag folder")
    assert not apps["d1"].valid and apps["d1"].deletes  # the delta is still shown
    assert [(v["component"], v["message"]) for v in apps["d1"].violations] == [("lr:ensures", "some tag left")]
    assert eng.step().status == "done"


def test_conditions_use_the_pattern_subset():
    g = Graph().parse(data=PFX + UNTAG.replace('lr:params "folder" ;',
                                               'lr:params "folder" ; lr:requires "?folder ex:a/ex:b ?x" ;'),
                      format="turtle")
    with pytest.raises(UnsupportedPattern, match="property paths"):
        load_operations(g)


# --- lr:steps ---------------------------------------------------------------

FORGET = '''
ex:forget a lr:Operation ; rdfs:label "forget folder" ;
  lr:params "folder" ;
  lr:where "?folder a ex:Folder ; ex:scanned true ." ;
  lr:steps (
    [ lr:where "?f ex:inFolder ?folder ; ?p ?o ." ; lr:delete "?f ?p ?o ." ]
    [ lr:delete "?folder ex:scanned true ." ]
  ) .
'''


def test_steps_run_in_order_and_give_one_delta(tmp_path):
    eng = make(tmp_path, FORGET)
    apps = apps_of(eng, "forget folder")
    assert apps["d2"].deletes == {(EX.f3, EX.inFolder, EX.d2), (EX.f3, EX.tag, Literal("d")),
                                  (EX.d2, EX.scanned, Literal(True))}
    assert not apps["d2"].inserts
    assert not apps["d2"].noop
    assert set(eng.sheet) == set(Graph().parse(data=SHEET, format="turtle"))  # nothing applied yet


def test_a_step_sees_what_earlier_steps_did(tmp_path):
    model = '''
    ex:note a lr:Operation ; rdfs:label "note" ;
      lr:params "folder" ;
      lr:where "?folder a ex:Folder ." ;
      lr:insert "_:n a ex:Note ; ex:about ?folder ." ;
      lr:steps ( [ lr:where "?n a ex:Note ; ex:about ?folder ." ; lr:insert "?n ex:checked true ." ] ) .
    '''
    eng = make(tmp_path, model)
    app = apps_of(eng, "note")["d1"]
    [note] = {s for s, p, o in app.inserts if o == EX.Note}
    assert (note, EX.about, EX.d1) in app.inserts
    assert (note, EX.checked, Literal(True)) in app.inserts


def test_a_later_step_can_undo_an_earlier_one(tmp_path):
    model = '''
    ex:flip a lr:Operation ; rdfs:label "flip" ;
      lr:params "folder" ;
      lr:where "?folder ex:scanned true ." ;
      lr:delete "?folder ex:scanned true ." ;
      lr:insert "?folder ex:busy true ." ;
      lr:steps ( [ lr:delete "?folder ex:busy true ." ; lr:insert "?folder ex:scanned true ." ] ) .
    '''
    assert make(tmp_path, model).applications() == []  # net change: nothing


def test_delete_then_insert_of_the_same_triple_changes_nothing(tmp_path):
    # SPARQL Update order: every delete, then every insert
    model = '''
    ex:touch a lr:Operation ; rdfs:label "touch" ;
      lr:where "?folder ex:scanned true ." ;
      lr:delete "?folder ex:scanned true ." ;
      lr:insert "?folder ex:scanned true . ?folder ex:touched true ." .
    '''
    [app, _] = make(tmp_path, model).applications()
    assert not app.deletes and app.inserts == {(app.bindings["folder"], EX.touched, Literal(True))}


@pytest.mark.parametrize("step, error", [
    ('[ lr:where "?f ex:inFolder ?folder" ]', "needs an lr:delete or an lr:insert"),
    ('[ lr:where "?f ex:inFolder+ ?folder" ; lr:delete "?f ?p ?o" ]', "property paths"),
    ('[ lr:delete "_:x ex:p ?folder" ]', "blank nodes"),
])
def test_steps_are_checked_at_load(step, error):
    g = Graph().parse(data=PFX + FORGET.replace('[ lr:delete "?folder ex:scanned true ." ]', step),
                      format="turtle")
    with pytest.raises(ValueError, match=error):
        load_operations(g)


def test_autopilot_applies_a_multi_step_operation(tmp_path):
    eng = make(tmp_path, FORGET)
    eng.run()
    assert not list(eng.sheet.triples((None, EX.inFolder, None)))
    assert not list(eng.sheet.triples((None, EX.scanned, None)))
    assert set(eng.sheet.subjects(RDF.type, EX.Folder)) == {EX.d1, EX.d2}
