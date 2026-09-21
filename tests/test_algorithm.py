"""RAPTOR gegen unabhängige Referenzen: naive Runden ohne Markierungen (alle Fahrten in jeder Runde) und Connection Scan; jede Verbindung wird nachgespielt; die Bereichsabfrage gegen unabhängige Läufe; Grenzfälle."""

import numpy as np
import pytest

import rp_algorithm as alg
import rp_constants as C
import rp_timetable as T

INF = float("inf")


def _small_random(n, lines, walk, seed):
    return T.random_timetable(n, lines, walk, seed)


TIMETABLES = {
    "small": lambda: T.small_timetable(),
    "city": lambda: T.city_timetable(4, 15, 0, 3),
    "city_walk": lambda: T.city_timetable(4, 15, 4, 3),
    "city_slow_walk": lambda: T.city_timetable(4, 30, 9, 5),
    "random": lambda: _small_random(20, 8, 0, 3),
    "random_walk": lambda: _small_random(20, 8, 5, 4),
}


def _pairs(tt, k, seed):
    rng = np.random.default_rng(seed)
    out = []
    while len(out) < k:
        s, t = (int(x) for x in rng.integers(0, tt.n, 2))
        if s != t:
            out.append((s, t, int(rng.integers(72, 200)) * 5))
    return out


def _front_of(tau_rows, t):
    front, prev = [], INF
    for k, row in enumerate(tau_rows):
        if row[t] < prev:
            front.append((k, row[t]))
            prev = row[t]
    return front


# --- Richtigkeit gegen die Referenzen ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name", TIMETABLES)
def test_front_equals_the_naive_rounds_and_the_earliest_arrival_equals_the_connection_scan(name):
    tt = TIMETABLES[name]()
    for s, t, dep in _pairs(tt, 30, 1):
        r = alg.raptor(tt, s, t, dep)
        naive = alg.naive_rounds(tt, s, t, dep)
        assert r.front == _front_of(naive, t), (name, s, t, dep)
        csa, scanned = alg.csa_earliest(tt, s, t, dep)
        assert csa == (r.front[-1][1] if r.front else INF), (name, s, t, dep)
        assert scanned >= 0 and all(a > b for (_, a), (_, b) in zip(r.front[:-1], r.front[1:]))          # jeder weitere Punkt kommt früher an


@pytest.mark.parametrize("name", ("small", "city_walk", "random"))
def test_every_round_matches_the_naive_rounds_at_every_stop_when_there_is_no_target(name):
    tt = TIMETABLES[name]()
    for s, _, dep in _pairs(tt, 12, 2):
        r = alg.raptor(tt, s, None, dep)
        naive = alg.naive_rounds(tt, s, 0, dep)
        for k in range(len(r.tau)):
            assert r.tau[k] == naive[k], (name, s, dep, k)


def test_all_stops_earliest_arrival_equals_the_connection_scan_for_every_target():
    tt = T.city_timetable(4, 20, 4, 6)
    arr, _ = alg.earliest_all(tt, 0, 480)
    for t in range(1, tt.n):
        assert arr[t] == alg.csa_earliest(tt, 0, t, 480)[0]


# --- Verbindungen nachspielen ----------------------------------------------------------------------------------------------------------------------------

def _replay(tt, s, t, depart, legs, trips, arrival):
    """Prüft eine Verbindung aus den Fahrplandaten heraus: Anschluss der Etappen, Zeiten, Umsteigezeit, Fußwege nur nach einer Fahrt, Zahl der Fahrten."""
    foot = {(p, q): d for p in range(tt.n) for q, d in tt.footpaths[p]}
    here, clock, last_trip, n_trips, last_walk = s, float(depart), False, 0, False
    for leg in legs:
        if leg[0] == "trip":
            _, r, trip, p, q, dep, arr = leg
            route = tt.routes[r]
            i, j = route.stops.index(p), route.stops.index(q)
            assert p == here and i < j and route.times[trip][i] == dep and route.times[trip][j] == arr
            assert dep >= clock + (tt.change if last_trip else 0)
            here, clock, last_trip, last_walk = q, float(arr), True, False
            n_trips += 1
        else:
            _, p, q, minutes, dep, arr = leg
            assert p == here and foot[(p, q)] == minutes and dep == clock and arr == dep + minutes
            assert not last_walk
            here, clock, last_trip, last_walk = q, float(arr), False, True
    assert here == t and clock == arrival and n_trips <= trips


@pytest.mark.parametrize("name", TIMETABLES)
def test_every_front_point_is_a_valid_journey_with_the_reported_arrival(name):
    tt = TIMETABLES[name]()
    checked = 0
    for s, t, dep in _pairs(tt, 25, 3):
        r = alg.raptor(tt, s, t, dep)
        for k, arrival in r.front:
            _replay(tt, s, t, dep, r.journey(k), k, arrival)
            checked += 1
    assert checked > 0


# --- Bereichsabfrage -------------------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name", ("small", "city", "city_walk", "random", "random_walk"))
def test_range_query_gives_the_front_of_an_independent_run_for_every_departure(name):
    tt = TIMETABLES[name]()
    for s, t, dep in _pairs(tt, 10, 4):
        out, counters = alg.range_raptor(tt, s, t, dep, dep + 60, 5)
        assert [d for d, _ in out] == list(range(dep, dep + 61, 5)) and counters["runs"] == 13
        for d, front in out:
            assert front == alg.raptor(tt, s, t, d).front, (name, s, t, d)


def test_the_range_query_needs_the_per_round_bound_not_the_overall_one():
    """Regression: mit der Schranke über alle Runden verdeckt eine Ankunft mit mehr Fahrten aus einer späteren Abfahrt eine gleich frühe mit weniger Fahrten."""
    tt = T.city_timetable(5, 10, 0, 100000)
    for s, t, dep in ((24, 10, 785), (18, 1, 580)):
        out, _ = alg.range_raptor(tt, s, t, dep, dep + 60, 5)
        for d, front in out:
            assert front == alg.raptor(tt, s, t, d).front


def test_the_range_query_scans_fewer_stops_than_independent_runs():
    tt = T.city_timetable(6, 10, 0, 7)
    total_shared = total_independent = 0
    for s, t, dep in _pairs(tt, 8, 5):
        out, counters = alg.range_raptor(tt, s, t, dep, dep + 120, 5)
        total_shared += counters["scanned"]
        total_independent += sum(alg.raptor(tt, s, t, d).counters["scanned"] for d in range(dep, dep + 121, 5))
    assert total_shared < total_independent


# --- Grenzfälle -----------------------------------------------------------------------------------------------------------------------------------------

def test_same_stop_unreachable_target_and_a_departure_after_the_last_trip():
    tt = T.small_timetable()
    r = alg.raptor(tt, 0, 0, 480)
    assert r.front == [(0, 480.0)] and r.journey(0) == []
    assert alg.raptor(tt, 7, 0, 480).front == []                                  # Linien fahren nur Richtung Flughafen
    late = alg.raptor(tt, 0, 7, C.LAST + 200)
    assert late.front == [] and alg.csa_earliest(tt, 0, 7, C.LAST + 200)[0] == INF
    early = alg.raptor(tt, 0, 7, 100)                                              # vor dem ersten Betrieb: warten bis 5:00
    assert early.front and early.front[-1][1] >= C.FIRST + 40


def test_the_minimum_change_time_is_respected_and_a_walk_needs_none():
    # Linie A: 0 -> 1 (Ankunft 10), Linie B: 1 -> 2 (Abfahrt 11 und 12); mit 2 Minuten Umsteigezeit ist nur die Abfahrt 12 erreichbar
    a = T.Route("A", "Bus", [0, 1], [[0, 10]])
    b = T.Route("B", "Bus", [1, 2], [[11, 20], [12, 21]])
    tt = T.Timetable(("p", "q", "r"), np.zeros((3, 2)), [a, b], [[] for _ in range(3)], 2)
    assert alg.raptor(tt, 0, 2, 0).front == [(2, 21.0)] and alg.csa_earliest(tt, 0, 2, 0)[0] == 21.0
    tt0 = T.Timetable(("p", "q", "r"), np.zeros((3, 2)), [a, b], [[] for _ in range(3)], 0)
    assert alg.raptor(tt0, 0, 2, 0).front == [(2, 20.0)]
    # ein Fußweg von q nach q2 (Minute 1) und Linie C ab q2 um 11: zu Fuß angekommen um 11, keine Umsteigezeit nötig
    c = T.Route("C", "Bus", [3, 2], [[11, 25]])
    tt2 = T.Timetable(("p", "q", "r", "q2"), np.zeros((4, 2)), [a, c], [[], [(3, 1)], [], [(1, 1)]], 2)
    assert alg.raptor(tt2, 0, 2, 0).front == [(2, 25.0)] and alg.csa_earliest(tt2, 0, 2, 0)[0] == 25.0


def test_walking_alone_is_a_front_point_with_zero_trips_and_more_trips_must_improve():
    tt = T.city_timetable(5, 30, 6, 2)
    found = False
    for s, t, dep in _pairs(tt, 40, 6):
        r = alg.raptor(tt, s, t, dep)
        if r.front and r.front[0][0] == 0:
            found = True
            assert all(k > 0 for k, _ in r.front[1:]) and r.journey(0)[0][0] == "walk" and len(r.journey(0)) == 1
    assert found


def test_a_target_further_than_the_round_limit_is_reported_as_not_found():
    tt = T.small_timetable()
    assert alg.raptor(tt, 0, 7, 480, max_rounds=1).front == [(1, 545.0)]
    assert alg.raptor(tt, 0, 7, 480, max_rounds=2).front == [(1, 545.0), (2, 531.0)]
    assert alg.raptor(tt, 0, 7, 480, max_rounds=3).front == [(1, 545.0), (2, 531.0), (3, 520.0)]


def test_counters_are_consistent():
    tt = T.city_timetable(5, 10, 0, 3)
    r = alg.raptor(tt, 0, 24, 500)
    c = r.counters
    assert c["routes_scanned"] > 0 and c["scanned"] >= c["routes_scanned"] and c["improved"] >= sum(len(h) for h in r.history) > 0 and c["boardings"] >= 1
    assert r.rounds == len(r.tau) - 1 and all(len(x) == tt.n for x in r.tau)
