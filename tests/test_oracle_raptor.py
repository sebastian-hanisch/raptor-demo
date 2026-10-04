"""Unabhängiges Orakel für RAPTOR: ein Zeit-Dijkstra über Zustände (Halt, zu Fuß oder mit Fahrt angekommen) und eine Rundenrechnung über einzelne Fahrten (jede Fahrt, jeder Einstieg), beide mit getrennter
Buchführung für Fuß- und Fahrt-Ankünfte. Regression: mit nur einem Label je Halt ging ein Anschluss verloren, den eine spätere Fuß-Ankunft (keine Umsteigezeit) noch erreicht, die frühere Fahrt-Ankunft (Umsteigezeit)
aber nicht - RAPTOR fand dann keine oder eine zu späte Verbindung."""

import heapq
import random

import numpy as np
import pytest

import rp_algorithm as alg
import rp_timetable as T

INF = float("inf")


def oracle_rounds(tt, s, depart, rounds):
    n = tt.n
    walk_to = [dict(tt.footpaths[p]) for p in range(n)]
    aw, at = [INF] * n, [INF] * n
    aw[s] = depart
    for q, d in walk_to[s].items():
        aw[q] = min(aw[q], depart + d)
    out = [[min(aw[p], at[p]) for p in range(n)]]
    for _ in range(rounds):
        ready = [min(aw[p], at[p] + tt.change) for p in range(n)]
        nt = list(at)
        for r in tt.routes:
            for trip in r.times:
                for i in range(len(r.stops) - 1):
                    if ready[r.stops[i]] <= trip[i]:
                        for j in range(i + 1, len(r.stops)):
                            nt[r.stops[j]] = min(nt[r.stops[j]], trip[j])
        nw = list(aw)
        for p in range(n):
            if nt[p] < INF:
                for q, d in walk_to[p].items():
                    nw[q] = min(nw[q], nt[p] + d)
        at, aw = nt, nw
        out.append([min(aw[p], at[p]) for p in range(n)])
    return out


def oracle_any_trips(tt, s, depart):
    """Früheste Ankunft mit beliebig vielen Fahrten: Dijkstra über (Halt, Art der Ankunft)."""
    walk_to = [dict(tt.footpaths[p]) for p in range(tt.n)]
    heap = [(depart, s, 0)] + [(depart + d, q, 0) for q, d in walk_to[s].items()]
    heapq.heapify(heap)
    best, done = [INF] * tt.n, set()
    while heap:
        a, p, by_trip = heapq.heappop(heap)
        if (p, by_trip) in done:
            continue
        done.add((p, by_trip))
        best[p] = min(best[p], a)
        ready = a + (tt.change if by_trip else 0)
        if by_trip:
            for q, d in walk_to[p].items():
                heapq.heappush(heap, (a + d, q, 0))
        for r in tt.routes:
            for i, stop in enumerate(r.stops[:-1]):
                if stop == p:
                    for trip in r.times:
                        if trip[i] >= ready:
                            for j in range(i + 1, len(r.stops)):
                                heapq.heappush(heap, (trip[j], r.stops[j], 1))
    return best


def front_of(arrivals, t):
    front, prev = [], INF
    for k, row in enumerate(arrivals):
        if row[t] < prev:
            front.append((k, row[t]))
            prev = row[t]
    return front


def random_timetable(rng):
    n = rng.randint(4, 8)
    routes = []
    for _ in range(rng.randint(2, 5)):
        length = rng.randint(2, min(n, 5))
        stops = rng.sample(range(n), length)
        run = [rng.randint(1, 4) for _ in range(length - 1)]
        times = []
        for start in sorted(rng.sample(range(0, 30), rng.randint(1, 5))):
            row = [start]
            for x in run:
                row.append(row[-1] + x)
            times.append(row)
        routes.append(T.Route("L", "Bus", stops, times))
    edges = [(*rng.sample(range(n), 2), rng.randint(1, 4)) for _ in range(rng.randint(2, 2 * n))]
    return T.Timetable(tuple(f"S{i}" for i in range(n)), np.zeros((n, 2)), routes, T.walking_closure(n, edges), rng.randint(2, 4))


def test_a_later_walk_arrival_can_catch_the_connection_the_earlier_trip_arrival_misses():
    # Halt b: mit Bus A um 100 (Umsteigezeit 3: Einstieg ab 103) und zu Fuß von c um 101 (Bus B ab c, an c um 99, 2 min Fußweg); Bus C fährt ab b um 101.
    a = T.Route("A", "Bus", [0, 1], [[90, 100]])
    b = T.Route("B", "Bus", [0, 2], [[90, 99]])
    c = T.Route("C", "Bus", [1, 3], [[101, 110]])
    tt = T.Timetable(tuple("abcd"), np.zeros((4, 2)), [a, b, c], T.walking_closure(4, [(2, 1, 2)]), 3)
    r = alg.raptor(tt, 0, 3, 90)
    assert oracle_any_trips(tt, 0, 90)[3] == 110
    assert r.front == [(2, 110.0)] and alg.csa_earliest(tt, 0, 3, 90)[0] == 110
    assert [leg[0] for leg in r.journey(2)] == ["trip", "walk", "trip"]
    assert alg.range_raptor(tt, 0, 3, 90, 90, 5)[0] == [(90, [(2, 110.0)])]
    assert alg.naive_rounds(tt, 0, 3, 90)[2][3] == 110


def test_rounds_front_and_range_query_equal_the_oracle_on_tight_random_timetables():
    rng = random.Random(77)
    for _ in range(120):
        tt = random_timetable(rng)
        s, depart = rng.randrange(tt.n), rng.choice([0, 2, 5, 9])
        want = oracle_rounds(tt, s, depart, 6)
        assert want[-1] == oracle_any_trips(tt, s, depart)                                  # das Orakel stimmt mit seinem zweiten Rechenweg überein
        got = alg.raptor(tt, s, None, depart, 6).tau                                         # RAPTOR hört auf, sobald nichts mehr markiert ist: die übrigen Runden ändern nichts
        assert got + [got[-1]] * (len(want) - len(got)) == want and alg.naive_rounds(tt, s, 0, depart, 6) == want
        for t in range(tt.n):
            if t != s:
                r = alg.raptor(tt, s, t, depart, 6)
                assert r.front == front_of(want, t)
                assert alg.csa_earliest(tt, s, t, depart)[0] == want[-1][t]
        t = rng.choice([p for p in range(tt.n) if p != s])
        for d, front in alg.range_raptor(tt, s, t, 0, 12, 3, 6)[0]:
            assert front == front_of(oracle_rounds(tt, s, d, 6), t)
