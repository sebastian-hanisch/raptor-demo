"""Rauchtests der Streamlit-Oberfläche per AppTest: Standard, jedes Preset, Randgrößen, Abfahrtszeiten, ausgeblendete Regler, Abspielen, Permalink, Experimente auf Abruf, Schlüssel."""

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import rp_constants as C
from rp_presets import PRESET_KEYS

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app.py"
VERDICT = {"🔀 Kleines Netz": "success", "🏙️ Stadtnetz": "warning", "🕸️ Zufalls-Linien": "success", "🐌 Seltener Takt": "warning"}
POINT = "Verbindung auf der Front (0 = wenigste Fahrten)"


def _run(setup=None, timeout=600, net=None):
    at = AppTest.from_file(str(APP), default_timeout=timeout)
    if net:
        at.query_params["net"] = net
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    if setup is not None:
        setup(at)
        at.run()
        assert not at.exception, [e.value for e in at.exception]
    return at


def _apply(at, p):
    for key, state_key in PRESET_KEYS.items():
        at.session_state[state_key] = p[key]


def _labels(at):
    return {w.label for w in list(at.sidebar.slider) + list(at.sidebar.selectbox) + list(at.sidebar.number_input) + list(at.sidebar.select_slider)} - {POINT}


def _play(at):
    [b for b in at.button if b.label == "▶️ Abspielen"][0].click()
    at.run()


def _verdicts(at):
    return len(at.success) + len(at.info) + len(at.warning)


def test_default_renders_without_exception_and_states_the_front():
    at = _run()
    assert any("RAPTOR in Aktion" in m.value for m in at.markdown)
    assert len(at.success) == 1 and "Zielkonflikt: 3 Verbindungen" in at.success[0].value and "9:05" in at.success[0].value and "8:40" in at.success[0].value and not at.warning and not at.error


@pytest.mark.parametrize("name", list(C.PRESETS))
def test_every_preset_renders_with_one_verdict(name):
    at = _run(lambda a: _apply(a, C.PRESETS[name]))
    got = {"success": len(at.success), "warning": len(at.warning), "info": len(at.info)}
    assert got[VERDICT[name]] == 1 and sum(got.values()) == 1 and not at.error


@pytest.mark.parametrize("net", C.NETS)
@pytest.mark.parametrize("depart", (360, 480, 1200))
def test_every_net_renders_in_the_morning_and_in_the_evening(net, depart):
    def setup(at):
        at.session_state["net_select"] = net
        at.session_state["depart_slider"] = depart
        at.session_state["side_slider"] = 4
        at.session_state["nodes_slider"] = 30
    at = _run(setup)
    assert _verdicts(at) == 1 and not at.error


def test_a_pair_that_cannot_be_connected_is_explained():
    at = _run(lambda a: (a.session_state.__setitem__("net_select", "random"), a.session_state.__setitem__("lines_slider", 6), a.session_state.__setitem__("nodes_slider", 80), a.session_state.__setitem__("depart_slider", 1200)))
    assert _verdicts(at) == 1 and not at.error


def test_a_single_point_front_hides_the_point_slider_and_says_so():
    at = _run(net="city")
    assert len(at.info) == 1 and "Nur eine Verbindung auf der Front" in at.info[0].value
    assert POINT not in {w.label for w in at.sidebar.slider}
    assert any("kein Zielkonflikt" in c.value for c in at.sidebar.caption)


def test_the_point_slider_switches_the_shown_journey():
    at = _run()
    assert POINT in {w.label for w in at.sidebar.slider}
    first = [m.value for m in at.markdown if m.value.startswith("**Verbindung mit")]
    at.slider(key="point_slider").set_value(2)
    at.run()
    last = [m.value for m in at.markdown if m.value.startswith("**Verbindung mit")]
    assert not at.exception and first and last and first != last and "3 Fahrten" in last[0] and "1 Fahrt:" in first[0]


def test_extreme_settings_render():
    def small(at):
        at.session_state["net_select"] = "city"
        at.session_state["side_slider"] = C.SIDE_MIN
        at.session_state["headway_slider"] = C.HEADWAY_MAX
        at.session_state["walk_slider"] = C.WALK_MAX

    def big(at):
        at.session_state["net_select"] = "city"
        at.session_state["side_slider"] = C.SIDE_MAX
        at.session_state["headway_slider"] = C.HEADWAY_MIN
        at.session_state["distance_slider"] = C.DISTANCE_MAX

    def random_(at):
        at.session_state["net_select"] = "random"
        at.session_state["nodes_slider"] = C.NODES_MIN
        at.session_state["lines_slider"] = C.LINES_MAX
        at.session_state["distance_slider"] = C.DISTANCE_MIN
    for setup in (small, big, random_):
        at = _run(setup)
        assert at.slider(key="rp_step").value == at.slider(key="rp_step").max


def test_hidden_controls_follow_the_net():
    common = {"Netz", "Abfahrtszeit"}
    small, city, rnd = (_labels(_run(net=n)) for n in ("small", "city", "random"))
    assert small == common                                                                            # feste Aufgabe: kein Ziel, kein Seed
    assert city == common | {"Haltestellen je Seite", "Takt der Buslinien [min]", "Fußweg [min je Block]", "Entfernung des Ziels [Perzentil]", "Zufalls-Seed"}
    assert rnd == common | {"Fußweg [min je Block]", "Haltestellen", "Linien", "Entfernung des Ziels [Perzentil]", "Zufalls-Seed"}


def test_hidden_slider_values_come_back_when_the_net_is_shown_again():
    # Die erste Sicht muss das Netz mit dem Regler sein: AppTest verliert den Wert, wenn der Regler zuerst ausgeblendet war (im echten Browser bleibt er erhalten).
    at = _run(net="city")
    at.session_state["headway_slider"] = 25
    at.run()
    at.session_state["net_select"] = "small"
    at.run()
    at.session_state["net_select"] = "city"
    at.run()
    assert not at.exception and at.slider(key="headway_slider").value == 25


def test_step_slider_returns_to_the_last_round_when_the_departure_changes():
    at = _run(lambda a: _apply(a, C.PRESETS["🏙️ Stadtnetz"]))
    at.slider(key="rp_step").set_value(1)
    at.run()
    assert at.slider(key="rp_step").value == 1
    at.session_state["depart_slider"] = 600
    at.run()
    assert not at.exception and at.slider(key="rp_step").value == at.slider(key="rp_step").max
    assert at.slider(key="point_slider").value == 0


def test_every_round_of_the_small_network_renders():
    at = _run()
    for k in range(0, int(at.slider(key="rp_step").max) + 1):
        at.slider(key="rp_step").set_value(k)
        at.run()
        assert not at.exception, k


def test_play_renders_several_frames_without_duplicate_keys():
    """Beim Abspielen entstehen in einem Lauf mehrere Diagramme mit demselben Namen - die Schlüssel tragen deshalb die Runde (Regression: StreamlitDuplicateElementKey bei mehr als einem Bild)."""
    for setup in (lambda a: None, lambda a: _apply(a, C.PRESETS["🏙️ Stadtnetz"]), lambda a: _apply(a, C.PRESETS["🕸️ Zufalls-Linien"])):
        at = _run(setup)
        _play(at)
        assert not at.exception, [e.value for e in at.exception]


def test_permalink_parameters_select_the_net_and_are_clamped_and_snapped():
    at = AppTest.from_file(str(APP), default_timeout=600)
    at.query_params["net"] = "city"
    at.query_params["headway"] = "999"
    at.query_params["depart"] = "487"
    at.query_params["walk"] = "-4"
    at.run()
    assert not at.exception and at.selectbox(key="net_select").value == "city"
    assert at.slider(key="headway_slider").value == C.HEADWAY_MAX and at.select_slider(key="depart_slider").value == 485 and at.slider(key="walk_slider").value == C.WALK_MIN


def test_unknown_net_in_the_permalink_falls_back_to_the_default():
    at = AppTest.from_file(str(APP), default_timeout=600)
    at.query_params["net"] = "ring"
    at.run()
    assert not at.exception and at.selectbox(key="net_select").value == C.DEFAULT_NET


def test_experiments_run_on_demand():
    at = _run()
    assert not any("Mittel über 5 Fahrpläne" in c.value for c in at.caption)
    for key in ("fronts_start", "headway_start", "scan_start", "range_start"):
        at.button(key=key).click()
        at.run()
        assert not at.exception, (key, [e.value for e in at.exception])
    text = " ".join(c.value for c in at.caption)
    for needle in ("gibt es ohne Fußwege fast nie einen Zielkonflikt", "min mehr, weil bei seltenem Takt", "das Connection Scan liefert zudem nur die früheste Ankunft", "die Fronten sind in jedem Fall dieselben"):
        assert needle in text, needle


def _calls(src, name):
    """Der Text jedes Aufrufs `name(...)` einschließlich verschachtelter Klammern."""
    out = []
    for m in re.finditer(re.escape(name) + r"\(", src):
        depth, i = 1, m.end()
        while depth:
            depth += {"(": 1, ")": -1}.get(src[i], 0)
            i += 1
        out.append(src[m.start():i])
    return out


def test_every_plotly_chart_has_an_explicit_key_and_axes_are_locked():
    calls = _calls(APP.read_text(encoding="utf-8"), "plotly_chart")
    keys = [re.search(r'key=f?"([a-z_]+?)(?:_\{\w+\})?"', c).group(1) for c in calls]
    # Die Karte steht in der Play-Schleife: ihr Schlüssel trägt die Runde
    assert sorted(keys) == sorted(["net_chart", "front_chart", "range_chart", "fronts_chart", "headway_chart", "scan_chart", "range_exp_chart"]), keys
    assert sum('key=f"' in c for c in calls) == 1 and all('_{current}"' in c for c in calls if 'key=f"' in c)
    viz = (ROOT / "rp_visualization.py").read_text(encoding="utf-8")
    assert "fixedrange=True" in viz and viz.count("_base(fig") >= 5


def test_app_text_has_no_links_to_repository_files():
    assert not re.search(r"\]\(\w+\.py\)", APP.read_text(encoding="utf-8"))
