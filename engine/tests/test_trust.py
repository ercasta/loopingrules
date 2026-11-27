import pytest

from loopingrules.trust import TemplateError, TrustStore, compile_template, generalize


def test_generalize():
    assert generalize("wc -l < 'data/notes.txt'") == "wc -l < '{}'"
    assert generalize("cp 'a b' 'c'") == "cp '{}' '{}'"


@pytest.mark.parametrize("cmd,ok", [
    ("ls -1p 'data'", True),
    ("ls -1p 'a folder/with spaces'", True),
    ("ls -1p 'x'; rm -rf /", False),         # nothing may follow the template
    ("ls -1p 'x'\"'\"'; rm -rf / '", False),  # cannot escape the quotes
    ("ls -1p 'x\n'", False),                  # no newlines in arguments
    ("ls -1p data", False),                   # argument must be quoted
    ("ls -la 'data'", False),
])
def test_template_matching_is_strict(cmd, ok):
    assert bool(compile_template("ls -1p '{}'").match(cmd)) is ok


@pytest.mark.parametrize("bad", ["", "ls {}", "ls \"{}\"", "a\nb"])
def test_bad_templates_rejected(bad):
    with pytest.raises(TemplateError):
        compile_template(bad)


def test_store_is_scoped_to_project(tmp_path):
    f = tmp_path / "trust.ttl"
    a = TrustStore(tmp_path / "projA", f)
    a.add("wc -l < '{}'")
    assert a.match("wc -l < 'x.txt'").template == "wc -l < '{}'"
    assert TrustStore(tmp_path / "projB", f).match("wc -l < 'x.txt'") is None
    again = TrustStore(tmp_path / "projA", f)  # persisted
    [rule] = again.rules()
    again.remove(rule.id)
    assert TrustStore(tmp_path / "projA", f).rules() == []
