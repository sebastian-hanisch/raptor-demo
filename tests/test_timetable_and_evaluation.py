"""Fahrpläne (kleines Netz, Stadtnetz, Zufalls-Linien, Fußwegabschluss), Kennzahlen, Front, Bildfolge, Abbildungen und Messreihen."""

import numpy as np
import pytest

import rp_algorithm as alg
import rp_constants as C
import rp_evaluation as ev
import rp_timetable as T
import rp_visualization as viz

INF = float("inf")


# --- Fahrpläne -------------------------------------------------------------------------------------------------------------------------------------------

def _check_no_overtaking(tt):
    for route in tt.routes:
        assert all(len(t) == len(route.stops) and all(b > a for a, b in zip(t[:-1], t[1:])) for t in route.times)
        for j in range(len(route.stops)):
            col = [t[j] for t in route.times]
            assert col == sorted(col) and len(set(col)) == len(col)                         # spätere Fahrt ist an jedem Halt später
            assert route.cols[j] == col


def test_small_timetable_has_six_lines_and_no_overtaking():
    tt = T.small_timetable()
    assert tt.n == 8 and len(tt.routes) == 6 and tt.n_trips() == 308 and tt.n_stop_times() == 1179 and tt.change == C.CHANGE
    _check_no_overtaking(tt)
    assert all(t[0] >= C.FIRST for r in tt.routes for t in r.times) and all(t[0] <= C.LAST for r in tt.routes for t in r.times)


@pytest.mark.parametrize("walk", (0, 3))
def test_city_timetable_has_bus_and_express_lines_and_no_overtaking(walk):
    tt = T.city_timetable(6, 10, walk, 3)
    kinds = [r.kind for r in tt.routes]
    assert tt.n == 36 and kinds.count("Bus") == 4 * 6 and kinds.count("Express") == 4 * 2                     # 6 Zeilen und 6 Spalten, je 2 Richtungen; Express in Zeile 1 und 4, Spalte 1 und 4
    _check_no_overtaking(tt)
    express = next(r for r in tt.routes if r.kind == "Express")
    assert len(express.stops) == 3 and len(express.times) < len(next(r for r in tt.routes if r.kind == "Bus").times)       # hält seltener und fährt seltener
    assert (walk > 0) == any(tt.footpaths)


def test_random_timetable_covers_most_stops_and_is_reproducible():
    a, b = T.random_timetable(40, 16, 0, 5), T.random_timetable(40, 16, 0, 5)
    assert [r.stops for r in a.routes] == [r.stops for r in b.routes] and np.array_equal(a.xy, b.xy) and len(a.routes) == 32
    _check_no_overtaking(a)
    assert sum(1 for p in range(a.n) if a.stop_routes[p]) >= 30
    assert T.random_timetable(40, 16, 5, 5).footpaths != a.footpaths


@pytest.mark.parametrize("make", (lambda: T.city_timetable(5, 10, 4, 2), lambda: T.random_timetable(30, 10, 5, 2)))
def test_footpaths_are_symmetric_and_transitively_closed(make):
    tt = make()
    walk = {(p, q): d for p in range(tt.n) for q, d in tt.footpaths[p]}
    assert walk and all(walk.get((q, p)) == d for (p, q), d in walk.items())
    for (p, q), d in walk.items():
        for r, d2 in ((r, dd) for r, dd in tt.footpaths[q] if r != p):
            assert (p, r) in walk and walk[(p, r)] <= d + d2                                       # abgeschlossen: ein Weg reicht so weit wie jede Kette


def test_walking_closure_of_a_chain():
    foot = T.walking_closure(4, [(0, 1, 2), (1, 2, 3)])
    assert dict(foot[0]) == {1: 2, 2: 5} and dict(foot[2]) == {1: 3, 0: 5} and foot[3] == []


def test_make_timetable_rejects_unknown_nets():
    with pytest.raises(ValueError):
        T.make_timetable("ring")


def test_earliest_trip_finds_the_first_departure_at_or_after_the_ready_time():
    tt = T.small_timetable()
    col = tt.routes[0].cols[0]
    assert tt.earliest_trip(0, 0, col[3]) == 3 and tt.earliest_trip(0, 0, col[3] + 1) == 4 and tt.earliest_trip(0, 0, col[-1] + 1) is None and tt.earliest_trip(0, 0, 0) == 0


# --- Kennzahlen -----------------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("net,kw", (("small", {}), ("city", dict(side=5, walk=6)), ("random", dict(nodes=30, lines=12))))
def test_analysis_invariants(net, kw):
    tt = T.make_timetable(net, seed=3, **kw)
    a = ev.analyse(tt, 480, 80, 3, fixed=(0, 7) if net == "small" else None)
    m = a.metrics
    assert m["reachable"] and m["exact"] and a.s != a.t and m["front"] == a.res.front and set(a.journeys) == {k for k, _ in m["front"]}
    assert m["fastest"] == m["front"][-1][1] - 480 and m["fewest_trips"] == m["front"][0][0] and m["max_trips"] == m["front"][-1][0]
    assert m["csa_arrival"] == m["front"][-1][1] and m["scanned"] == a.res.counters["scanned"] and m["range_points"] == ev.WINDOW // ev.RANGE_STEP + 1
    assert m["range_scanned"] <= m["range_independent"] and 1 <= m["range_steps"] <= m["range_points"] and m["stop_times"] == tt.n_stop_times()
    assert ev.verdict(a) in ("front", "single", "walk") and [d for d, _ in a.rng] == list(range(480, 601, 5))
    assert a.rng[0][1] == a.res.front


def test_verdict_covers_the_cases():
    small = ev.analyse(T.small_timetable(), 480, fixed=(0, 7))
    assert ev.verdict(small) == "front" and len(small.metrics["front"]) == 3
    walk = ev.analyse(T.city_timetable(6, 10, 10, 2), 480, 100, 2)
    assert ev.verdict(walk) == "walk" and walk.metrics["front"][0][0] == 0
    unreachable = ev.analyse(T.small_timetable(), 480, fixed=(7, 0))
    assert ev.verdict(unreachable) == "unreachable" and not unreachable.metrics["reachable"]
    single = ev.analyse(T.city_timetable(5, 10, 0, 3), 480, 80, 3)
    assert ev.verdict(single) == "single" and len(single.metrics["front"]) == 1


def test_pick_pair_follows_the_arrival_percentile_and_fixed_pairs():
    tt = T.city_timetable(6, 10, 0, 3)
    arr, _ = alg.earliest_all(tt, 0, 480)
    picks = [ev.pick_pair(tt, 480, pct, 3) for pct in (0, 50, 100)]
    assert all(s == picks[0][0] for s, _ in picks)
    times = [arr[t] for _, t in picks]
    assert times[0] <= times[1] <= times[2] and ev.pick_pair(tt, 480, 50, 3) == picks[1]
    assert ev.pick_pair(T.small_timetable(), 480, 10, 3, fixed=(0, 7)) == (0, 7)


def test_frames_and_state_follow_the_rounds():
    a = ev.analyse(T.small_timetable(), 480, fixed=(0, 7))
    fr = ev.frames(a)
    assert fr == list(range(len(fr))) and fr[-1] == a.metrics["max_trips"] and fr[-1] <= a.res.rounds
    tau0, imp0 = ev.state_at(a, 0)
    assert tau0[a.s] == 480 and imp0 == {a.s: 480.0} and sum(1 for x in tau0 if x < INF) == 1
    reached = [sum(1 for x in ev.state_at(a, k)[0] if x < INF) for k in fr]
    assert reached == sorted(reached) and reached[-1] > 3
    tau_last, _ = ev.state_at(a, fr[-1])
    assert tau_last[a.t] == a.metrics["front"][-1][1]


def test_leg_text_names_lines_stops_and_times():
    tt = T.small_timetable()
    a = ev.analyse(tt, 480, fixed=(0, 7))
    text = [ev.leg_text(tt, l) for l in a.journeys[2]]
    assert text == ["S1: Hbf 8:03 → Park 8:27", "S2: Park 8:30 → Flughafen 8:51"]


# --- Abbildungen -----------------------------------------------------------------------------------------------------------------------------------------

def test_charts_and_tables_render_for_every_net_and_round():
    for net, kw in (("small", {}), ("city", dict(side=5, walk=6)), ("random", dict(nodes=30, lines=12))):
        tt = T.make_timetable(net, seed=3, **kw)
        a = ev.analyse(tt, 480, 80, 3, fixed=(0, 7) if net == "small" else None)
        for k in ev.frames(a):
            viz.build_network(a, k, a.metrics["front"][-1][0] if k == ev.frames(a)[-1] else None)
            assert isinstance(viz.round_table(a, k), list)
        for k, _ in a.metrics["front"]:
            assert viz.journey_table(a, k)
        viz.build_front(a, 0)
        viz.build_range(a)
    viz.build_fronts([{"label": "x", "front": 1.2, "rounds": 3.0}])
    viz.build_headway([{"headway": 10, "journey": 15.0, "front": 1.5}])
    viz.build_scan([{"key": "city", "n": 16, "raptor": 80.0, "csa": 75.0, "stop_times": 7000.0}, {"key": "random", "n": 40, "raptor": 200.0, "csa": 500.0, "stop_times": 13000.0}])
    viz.build_range_rows([{"key": "city", "size": 5, "shared": 2000.0, "independent": 3000.0}])


def test_round_table_lists_the_earliest_stops_first_with_how_to_get_there():
    tt = T.small_timetable()
    a = ev.analyse(tt, 480, fixed=(0, 7))
    rows = viz.round_table(a, 1)
    assert rows and [r["Ankunft"] for r in rows] == sorted((r["Ankunft"] for r in rows), key=lambda x: (int(x.split(":")[0]), int(x.split(":")[1])))
    assert all(("ab" in r["Wie"]) for r in rows) and viz.round_table(a, 0)[0]["Wie"] == "Start" and viz.round_table(a, 99) == []


def test_hhmm_formats_times_of_day():
    assert C.hhmm(0) == "0:00" and C.hhmm(485) == "8:05" and C.hhmm(1500) == "1:00" and C.hhmm(545.0) == "9:05"


# --- Messreihen ---------------------------------------------------------------------------------------------------------------------------------------

def test_sample_pairs_are_reproducible_and_in_the_morning():
    tt = T.city_timetable(5, 10, 0, 3)
    p = ev.sample_pairs(tt, 20, 3)
    assert p == ev.sample_pairs(tt, 20, 3) and all(s != t and 360 <= d < 840 and d % 5 == 0 for s, t, d in p)


def test_front_rows_show_that_walking_creates_conflicts():
    rows = ev.front_rows(cases=[("a", dict(net="city", side=5, headway=10, walk=0)), ("b", dict(net="city", side=5, headway=10, walk=10))], seeds=C.SWEEP_SEEDS[:2], pairs=15)
    assert rows[0]["multi"] < rows[1]["multi"] and rows[0]["front"] < rows[1]["front"] and rows[0]["reach"] == 1.0 and rows[1]["rounds_max"] >= 2


def test_headway_rows_shrink_the_timetable_and_lengthen_the_journey():
    rows = ev.headway_rows(headways=(5, 30), side=5, seeds=C.SWEEP_SEEDS[:2], pairs=15)
    assert rows[0]["stop_times"] > 4 * rows[1]["stop_times"] and rows[0]["journey"] < rows[1]["journey"] + 3 and rows[0]["front"] >= rows[1]["front"]


def test_scan_rows_compare_the_two_algorithms_on_the_same_answers():
    rows = ev.scan_rows(cases=[("city", dict(side=4)), ("random", dict(nodes=30, lines=12))], seeds=C.SWEEP_SEEDS[:2], pairs=15)
    assert all(r["raptor"] > 0 and r["csa"] > 0 and r["raptor"] < r["stop_times"] for r in rows) and rows[1]["raptor"] < rows[1]["csa"]


def test_range_rows_share_labels_and_agree_with_independent_runs():
    rows = ev.range_rows(cases=[("city", dict(side=5))], seeds=C.SWEEP_SEEDS[:2], pairs=4)
    assert rows[0]["shared"] < rows[0]["independent"] and rows[0]["steps"] > 1                      # range_rows prüft die Fronten je Abfahrt selbst (assert)
