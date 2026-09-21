"""Jede Zahl aus Texten, Hilfen und README ist hier belegt (gemessen am 2026-09-21, Toleranzen fangen Rundung ab). Fahrzeiten, Zähler und ganzzahlige Zeiten sind plattformfest (reine Python-Rechnung mit festen Seeds);
Laufzeiten stehen in der App nur als Messwerte und werden hier nie geprüft."""

import pytest

import rp_algorithm as alg
import rp_constants as C
import rp_evaluation as ev
import rp_timetable as T

PRESET = {"small": "🔀 Kleines Netz", "city": "🏙️ Stadtnetz", "random": "🕸️ Zufalls-Linien", "slow": "🐌 Seltener Takt"}


def _preset(key):
    p = C.PRESETS[PRESET[key]]
    tt = T.make_timetable(p["net"], p["side"], p["headway"], p["walk"], p["nodes"], p["lines"], p["seed"])
    return tt, ev.analyse(tt, p["depart"], p["distance"], p["seed"], fixed=(0, 7) if p["net"] == "small" else None)


def _has(key, *needles):
    help_ = C.PRESET_HELP[PRESET[key]]
    for n in needles:
        assert n in help_, (key, n)


# --- Preset-Hilfen -----------------------------------------------------------------------------------------------------------------------------

def test_small_preset_numbers():
    tt, a = _preset("small")
    m = a.metrics
    assert (tt.n, len(tt.routes)) == (8, 6) and [(k, t - 480) for k, t in m["front"]] == [(1, 65), (2, 51), (3, 40)] and [C.hhmm(t) for _, t in m["front"]] == ["9:05", "8:51", "8:40"]
    assert [ev.leg_text(tt, l) for l in a.journeys[1]] == ["Bus 1: Hbf 8:19 → Flughafen 9:05"]
    assert [ev.leg_text(tt, l) for l in a.journeys[2]] == ["S1: Hbf 8:03 → Park 8:27", "S2: Park 8:30 → Flughafen 8:51"]
    assert [tt.routes[l[1]].line for l in a.journeys[3]] == ["S1", "Bus 3", "Bus 4"] and m["front"][0][1] - m["front"][1][1] == 14 and m["front"][1][1] - m["front"][2][1] == 11
    assert (m["rounds"], m["scanned"], m["csa_scanned"], m["range_steps"]) == (4, 52, 34, 9)
    _has("small", "8 Haltestellen, 6 Linien", "drei Punkte", "9:05, 65 min", "Bus 1", "Park", "8:51, 51 min", "8:40, 40 min", "14 und 11 min", "4 Runden", "52 Halte", "34 Verbindungen")


def test_city_preset_numbers():
    tt, a = _preset("city")
    m = a.metrics
    assert (tt.names[a.s], tt.names[a.t]) == ("C2", "F6") and [(k, t - 480) for k, t in m["front"]] == [(0, 55), (1, 48), (2, 30)]
    assert [l[0] for l in a.journeys[0]] == ["walk"] and [l[0] for l in a.journeys[1]] == ["walk", "trip", "walk"] and [tt.routes[l[1]].line for l in a.journeys[2]] == ["Bus S2", "Bus Z6"]
    assert (m["rounds"], m["scanned"], m["csa_scanned"]) == (4, 500, 388)
    _has("city", "6 × 6, Takt 10, 10 min je Block", "Seed 2", "von C2 nach F6", "in 55 min", "in 48 min", "Express", "Bus S2", "Bus Z6", "in 30 min", "500 Halte in 4 Runden", "388 Verbindungen")


def test_random_preset_numbers():
    tt, a = _preset("random")
    m = a.metrics
    assert (tt.n, len(tt.routes) // 2, tt.names[a.s], tt.names[a.t]) == (40, 16, "H7", "H26") and [(k, t - 480) for k, t in m["front"]] == [(2, 83), (3, 53)] and (m["scanned"], m["csa_scanned"]) == (330, 669)
    _has("random", "40 Haltestellen, 16 Linien", "Seed 3", "von H7 nach H26", "in 83 min", "drei Fahrten in 53 min", "30 Minuten", "330 Halte", "669 Verbindungen")


def test_slow_headway_preset_numbers():
    tt, a = _preset("slow")
    m = a.metrics
    assert (tt.names[a.s], tt.names[a.t]) == ("C2", "A5") and [(k, t - 480) for k, t in m["front"]] == [(0, 40), (1, 38)] and (m["scanned"], m["csa_scanned"]) == (311, 146)
    assert C.PRESETS[PRESET["slow"]]["headway"] == 30 and tt.n_stop_times() == 5304
    _has("slow", "Takt 30", "von C2 nach A5", "in 40 min", "in 38 min", "Bus Z2", "146 Verbindungen", "311 Halte")


# --- Sidebar-Hilfen -----------------------------------------------------------------------------------------------------------------------------

def test_departure_help_numbers_in_the_small_network():
    tt = T.small_timetable()
    for dep in range(360, 1200, 30):
        front = alg.raptor(tt, 0, 7, dep).front
        if dep % 60 == 0:
            assert [t - dep for _, t in front] == [65, 51, 40], dep
        else:
            assert len(front) == 2, dep


def test_headway_help_numbers():
    rows = {r["headway"]: r for r in ev.headway_rows()}
    assert [rows[h]["front"] for h in (5, 10, 15, 20, 30)] == pytest.approx([1.92, 1.62, 1.41, 1.27, 1.27], abs=0.005)
    assert rows[5]["journey"] == pytest.approx(14.46, abs=0.005) and rows[30]["journey"] == pytest.approx(16.79, abs=0.005) and [rows[h]["journey"] for h in (5, 10, 15, 20)] == sorted([rows[h]["journey"] for h in (5, 10, 15, 20)])
    assert rows[30]["journey"] - rows[5]["journey"] == pytest.approx(2.325, abs=0.005) and rows[5]["stop_times"] / rows[30]["stop_times"] == pytest.approx(6.0, abs=0.02)      # Fahrplan sechsmal kleiner
    assert rows[5]["trips"] == pytest.approx(0.98, abs=0.005) and rows[30]["trips"] == pytest.approx(0.265, abs=0.0051)


def test_walk_help_numbers_and_the_conflict_rows():
    rows = {r["label"]: r for r in ev.front_rows()}
    zero, w3, w5, w10 = (rows[k] for k in ("Stadtnetz, ohne Fußwege", "Stadtnetz, 3 min je Block zu Fuß", "Stadtnetz, 5 min je Block zu Fuß", "Stadtnetz, 10 min je Block zu Fuß"))
    assert (zero["multi"], w5["multi"], w10["multi"]) == pytest.approx((0.03, 0.58, 0.95), abs=0.005)                  # Hilfe: 3 / 58 / 95 %
    assert w10["front"] == pytest.approx(2.44, abs=0.005) and zero["trips"] == pytest.approx(1.72, abs=0.005) and w3["trips"] < 0.1 and all(r["reach"] == 1.0 for r in list(rows.values())[:5])
    assert [rows[k]["rounds_max"] for k in ("Stadtnetz, ohne Fußwege", "Stadtnetz, 3 min je Block zu Fuß", "Stadtnetz, 5 min je Block zu Fuß", "Stadtnetz, 10 min je Block zu Fuß")] == pytest.approx([4.0, 2.0, 3.0, 4.0], abs=0.05)
    assert max(r["rounds_max"] for r in rows.values()) == pytest.approx(5.6, abs=0.05) and rows["Zufalls-Linien, 40 Halte"]["reach"] == pytest.approx(0.9, abs=0.005)


# --- Experimente und die Tabelle "Wo die Annahmen enden" ------------------------------------------------------------------------------------------

def test_scan_experiment_numbers():
    rows = {(r["key"], r["size"]): r for r in ev.scan_rows()}
    assert (rows[("city", 4)]["raptor"], rows[("city", 4)]["csa"]) == pytest.approx((80.2, 75.2), abs=0.05)
    assert (rows[("city", 7)]["raptor"], rows[("city", 7)]["csa"], rows[("city", 7)]["stop_times"]) == pytest.approx((268.8, 366.4, 21853.3), abs=0.05)
    assert rows[("random", 80)]["raptor"] / rows[("random", 80)]["csa"] == pytest.approx(0.26, abs=0.005) and (rows[("random", 80)]["raptor"], rows[("random", 80)]["csa"]) == pytest.approx((211.9, 799.9), abs=0.05)
    assert rows[("city", 4)]["csa"] < rows[("city", 4)]["raptor"] and all(r["raptor"] < 0.02 * r["stop_times"] for r in rows.values())            # kleines Netz: CSA leicht schneller; RAPTOR scannt winzigen Teil des Fahrplans


def test_range_experiment_numbers():
    rows = {(r["key"], r["size"]): r for r in ev.range_rows()}
    ks = (("city", 5), ("city", 6), ("city", 7), ("random", 40))
    assert [rows[k]["shared"] for k in ks] == pytest.approx([2357.4, 2915.1, 3912.3, 3105.9], abs=0.05) and [rows[k]["independent"] for k in ks] == pytest.approx([3513.9, 4531.1, 6499.5, 6262.3], abs=0.05)
    saving = [1 - r["shared"] / r["independent"] for r in rows.values()]
    assert min(saving) == pytest.approx(0.329, abs=0.001) and max(saving) == pytest.approx(0.504, abs=0.001) and rows[("city", 6)]["steps"] == pytest.approx(16.75, abs=0.05)


def test_no_conflict_in_plain_grid_networks():
    """Tabelle "Wo die Annahmen enden": im 6 × 6-Stadtnetz ohne Fußwege haben nur 3 % der Paare mehr als einen Punkt auf der Front."""
    rows = {r["label"]: r for r in ev.front_rows(cases=[("plain", dict(net="city", side=6, headway=10, walk=0))])}
    assert rows["plain"]["multi"] == pytest.approx(0.03, abs=0.005)


def test_every_preset_answer_is_confirmed_by_the_connection_scan():
    for key in PRESET:
        _, a = _preset(key)
        assert a.metrics["exact"] and a.metrics["csa_arrival"] == a.metrics["front"][-1][1], key
