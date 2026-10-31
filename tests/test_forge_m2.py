"""M2's claim, as permanent verification points (`docs/plan-forge.md`).

A frozen compiled catalog must be a well-defined artifact the calibration kit
can tune reproducibly: freezing deterministic, structure separated from
values, the frozen catalog behaving exactly like the source it came from, and
`calibrate` reporting the plateaus it reports for any hand-authored domain.
"""

import pytest

from loopingrules_forge import m2


@pytest.fixture(scope="module")
def result():
    return m2.report()


def test_freeze_is_deterministic_and_structural(result):
    assert result["freeze_deterministic"]
    assert result["version_tracks_structure"]      # a change moves the version
    assert result["version_is_structural"]         # knobs do NOT move it


def test_frozen_catalog_behaves_like_its_source(result):
    assert result["deterministic"]                 # two replays agree
    assert result["frozen_reproduces"]             # two freezes agree
    assert result["frozen_matches_unfrozen"]       # freeze == the M0 catalog


def test_calibration_reports_plateaus_on_a_frozen_catalog(result):
    assert result["values_move_behaviour"]         # knobs choose behaviour
    assert result["calibration"].plateaus          # many settings, one trajectory
