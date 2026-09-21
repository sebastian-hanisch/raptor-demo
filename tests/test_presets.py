"""Presets, Permalink-Angaben und Regler-Grenzen sind untereinander stimmig."""

import pytest

import rp_constants as C
import rp_presets as P
from rp_timetable import make_timetable


def test_every_preset_sets_every_control_within_bounds_and_has_help():
    assert set(C.PRESETS) == set(C.PRESET_HELP) and len(C.PRESETS) == 4
    for name, p in C.PRESETS.items():
        assert set(p) == set(P.PRESET_KEYS) and p["net"] in C.NETS and p["depart"] in C.DEPART_OPTIONS
        for key, state_key in P.PRESET_KEYS.items():
            spec = P.SETTING_SPECS[state_key]
            if spec.lo is not None:
                assert spec.lo <= p[key] <= spec.hi, (name, key)
        make_timetable(p["net"], p["side"], p["headway"], p["walk"], p["nodes"], p["lines"], p["seed"])
        assert C.PRESET_HELP[name]
    assert [p["net"] for p in C.PRESETS.values()][:3] == list(C.NETS)


def test_setting_specs_and_kept_keys_are_consistent():
    assert set(P.PRESET_KEYS.values()) == set(P.SETTING_SPECS) and set(P.KEPT) <= set(P.SETTING_SPECS)
    for spec in P.SETTING_SPECS.values():
        assert spec.lo is None or spec.lo < spec.hi                                 # kein Regler mit gleichen Grenzen (Streamlit bricht ab)
    assert len({s.url_param for s in P.SETTING_SPECS.values()}) == len(P.SETTING_SPECS)


def test_defaults_lie_inside_the_bounds():
    for lo, hi, d in ((C.SIDE_MIN, C.SIDE_MAX, C.DEFAULT_SIDE), (C.HEADWAY_MIN, C.HEADWAY_MAX, C.DEFAULT_HEADWAY), (C.NODES_MIN, C.NODES_MAX, C.DEFAULT_NODES), (C.LINES_MIN, C.LINES_MAX, C.DEFAULT_LINES),
                      (C.DISTANCE_MIN, C.DISTANCE_MAX, C.DEFAULT_DISTANCE), (C.DEPART_MIN, C.DEPART_MAX, C.DEFAULT_DEPART)):
        assert lo < d < hi
    assert C.WALK_MIN <= C.DEFAULT_WALK <= C.WALK_MAX and C.DEFAULT_NET == "small" and C.DEFAULT_DEPART in C.DEPART_OPTIONS and C.DEPART_OPTIONS[0] == 360 and C.DEPART_OPTIONS[-1] == 1200


def test_choice_casters_reject_unknown_values():
    cast = P.SETTING_SPECS["net_select"].caster
    assert cast("random") == "random"
    with pytest.raises(ValueError):
        cast("ring")
