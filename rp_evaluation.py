"""RAPTOR im Vergleich mit dem Connection Scan: Kennzahlen, Front, Bildfolge der Runden, Bereichsabfrage und die Messreihen der Experimente. Aufwand als Zähler (gescannte Halte, gescannte Linien, gescannte Verbindungen);
Laufzeiten stehen nur als Messwerte in der App."""

import time
from dataclasses import dataclass

import numpy as np

import rp_algorithm as alg
import rp_constants as C
from rp_timetable import make_timetable

INF = float("inf")
WINDOW = 120                                       # Fenster der Bereichsabfrage in Minuten nach der Abfahrtszeit
RANGE_STEP = 5


@dataclass(frozen=True)
class Analysis:
    tt: object
    depart: int
    s: int
    t: int
    res: alg.RaptorResult
    journeys: dict                                  # Fahrten -> Etappen
    rng: list                                       # Bereichsabfrage: [(Abfahrt, Front)]
    metrics: dict
    seconds: dict


def pick_pair(tt, depart, distance_pct=C.DEFAULT_DISTANCE, seed=C.DEFAULT_SEED, fixed=None):
    """Start und Ziel: bei festem Netz Hbf und Flughafen; sonst ein Start (Raster: nahe bei 30 % Breite und 50 % Höhe; sonst der Halt mit den meisten Linien) und als Ziel der erreichbare Halt, dessen früheste Ankunft in der Rangfolge
    aller erreichbaren Halte bei `distance_pct` Prozent liegt."""
    if fixed:
        return fixed
    if "A1" in tt.names:
        lo, hi = tt.xy.min(axis=0), tt.xy.max(axis=0)
        s = int(np.argmin(np.hypot(*(tt.xy - (lo + (hi - lo) * np.array([0.3, 0.5]))).T)))
    else:
        s = int(max(range(tt.n), key=lambda p: (len(tt.stop_routes[p]), -p)))
    arr, _ = alg.earliest_all(tt, s, depart)
    reachable = [p for p in range(tt.n) if p != s and arr[p] < INF]
    if not reachable:
        return s, s
    order = sorted(reachable, key=lambda p: (arr[p], p))
    return s, order[min(len(order) - 1, int(round(distance_pct / 100.0 * (len(order) - 1))))]


def analyse(tt, depart, distance_pct=C.DEFAULT_DISTANCE, seed=C.DEFAULT_SEED, fixed=None):
    s, t = pick_pair(tt, depart, distance_pct, seed, fixed)
    t0 = time.perf_counter()
    res = alg.raptor(tt, s, t, depart)
    t_raptor = time.perf_counter() - t0
    t0 = time.perf_counter()
    csa_arr, csa_scanned = alg.csa_earliest(tt, s, t, depart)
    t_csa = time.perf_counter() - t0
    journeys = {k: res.journey(k) for k, _ in res.front}
    t0 = time.perf_counter()
    rng, rc = alg.range_raptor(tt, s, t, depart, depart + WINDOW, RANGE_STEP)
    t_range = time.perf_counter() - t0
    indep = {"routes_scanned": 0, "scanned": 0}
    for d in range(depart, depart + WINDOW + 1, RANGE_STEP):
        one = alg.raptor(tt, s, t, d)
        indep["scanned"] += one.counters["scanned"]
        indep["routes_scanned"] += one.counters["routes_scanned"]
    front = res.front
    reachable = bool(front) and s != t
    fastest = front[-1][1] if front else INF
    m = {"n": tt.n, "routes": len(tt.routes), "trips": tt.n_trips(), "stop_times": tt.n_stop_times(), "reachable": reachable, "front": front, "fastest": fastest - depart if front else INF,
         "fewest_trips": front[0][0] if front else 0, "max_trips": front[-1][0] if front else 0, "csa_arrival": csa_arr, "exact": bool(front and abs(csa_arr - fastest) < 1e-9), "rounds": res.rounds,
         "scanned": res.counters["scanned"], "routes_scanned": res.counters["routes_scanned"], "improved": res.counters["improved"], "boardings": res.counters["boardings"], "csa_scanned": csa_scanned,
         "range_points": len(rng), "range_steps": _steps(rng), "range_scanned": rc["scanned"], "range_independent": indep["scanned"], "range_routes": rc["routes_scanned"], "range_routes_independent": indep["routes_scanned"]}
    return Analysis(tt, int(depart), s, t, res, journeys, rng, m, {"raptor": t_raptor, "csa": t_csa, "range": t_range})


def _steps(rng):
    """Zahl der Stufen der Treppenfunktion "früheste Ankunft gegen Abfahrt" im Fenster (verschiedene Ankunftszeiten)."""
    arr = [f[-1][1] if f else INF for _, f in rng]
    return 1 + sum(1 for a, b in zip(arr[:-1], arr[1:]) if a != b)


def verdict(a):
    """Code für die App: unreachable / single (nur ein Punkt auf der Front) / front (Zielkonflikt) / walk (nur zu Fuß am besten)."""
    m = a.metrics
    if not m["reachable"]:
        return "unreachable"
    if m["front"][0][0] == 0:
        return "walk"
    return "front" if len(m["front"]) > 1 else "single"


def frames(a):
    """Bilder der Runden-Ansicht: 0 = Start (mit Fußwegen), dann je eine Runde bis zur letzten, die etwas verbessert hat."""
    last = max((k for k, h in enumerate(a.res.history) if h), default=0)
    return list(range(last + 1))


def state_at(a, k):
    """Nach Runde k: Ankunft je Haltestelle (inf: noch nicht erreicht) und die in Runde k verbesserten Halte."""
    tau = a.res.tau[min(k, len(a.res.tau) - 1)]
    return list(tau), dict(a.res.history[k]) if k < len(a.res.history) else {}


def leg_text(tt, leg):
    if leg[0] == "trip":
        _, r, _, p, q, dep, arr = leg
        return f"{tt.routes[r].line}: {tt.names[p]} {C.hhmm(dep)} → {tt.names[q]} {C.hhmm(arr)}"
    _, p, q, minutes, dep, arr = leg
    return f"zu Fuß: {tt.names[p]} {C.hhmm(dep)} → {tt.names[q]} {C.hhmm(arr)} ({minutes} min)"


# --- Messreihen ---------------------------------------------------------------------------------------------------------------------------------------------

def _mean(rows):
    return {k: float(np.mean([r[k] for r in rows])) for k in rows[0]}


def sample_pairs(tt, k, seed):
    """k zufällige (Start, Ziel, Abfahrt) - Abfahrt zwischen 6:00 und 14:00 in Fünferschritten."""
    rng = np.random.default_rng([int(seed), 6161])
    out = []
    while len(out) < k:
        s, t = (int(x) for x in rng.integers(0, tt.n, 2))
        if s != t:
            out.append((s, t, int(rng.integers(72, 168)) * 5))
    return out


def front_stats(tt, pairs):
    """Über die Paare: Anteil erreichbarer, mittlere Zahl Punkte auf der Front, Anteil mit mehr als einem Punkt, mittlere und größte Rundenzahl, mittlere Fahrzeit der schnellsten Verbindung, mittlere Zahl Fahrten der schnellsten."""
    fr, rounds, jt, trips, reach, gt1 = [], [], [], [], 0, 0
    for s, t, dep in pairs:
        r = alg.raptor(tt, s, t, dep)
        if not r.front:
            continue
        reach += 1
        fr.append(len(r.front))
        gt1 += len(r.front) > 1
        rounds.append(r.rounds)
        jt.append(r.front[-1][1] - dep)
        trips.append(r.front[-1][0])
    if not fr:
        return {"reach": 0.0, "front": 0.0, "multi": 0.0, "rounds": 0.0, "rounds_max": 0.0, "journey": 0.0, "trips": 0.0}
    return {"reach": reach / len(pairs), "front": float(np.mean(fr)), "multi": gt1 / len(fr), "rounds": float(np.mean(rounds)), "rounds_max": float(max(rounds)), "journey": float(np.mean(jt)), "trips": float(np.mean(trips))}


FRONT_CASES = [("Stadtnetz, ohne Fußwege", dict(net="city", side=6, headway=10, walk=0)), ("Stadtnetz, 3 min je Block zu Fuß", dict(net="city", side=6, headway=10, walk=3)),
               ("Stadtnetz, 5 min je Block zu Fuß", dict(net="city", side=6, headway=10, walk=5)), ("Stadtnetz, 10 min je Block zu Fuß", dict(net="city", side=6, headway=10, walk=10)),
               ("Stadtnetz, Takt 30, 5 min zu Fuß", dict(net="city", side=6, headway=30, walk=5)), ("Zufalls-Linien, 40 Halte", dict(net="random", nodes=40, lines=16, walk=0))]


def front_rows(cases=FRONT_CASES, seeds=C.SWEEP_SEEDS, pairs=C.PAIR_SAMPLES):
    """Wie viele Fahrten lohnen sich? Front-Statistik je Netzart, Mittel über die Sweep-Netze."""
    rows = []
    for label, kw in cases:
        acc = []
        for sd in seeds:
            tt = make_timetable(seed=sd, **kw)
            acc.append(front_stats(tt, sample_pairs(tt, pairs, sd)))
        rows.append({"label": label, **_mean(acc)})
    return rows


HEADWAYS = (5, 10, 15, 20, 30)


def headway_rows(headways=HEADWAYS, walk=5, side=6, seeds=C.SWEEP_SEEDS, pairs=C.PAIR_SAMPLES):
    """Takt gegen Fahrzeit der schnellsten Verbindung (inklusive Warten am Start) und Größe der Front; Stadtnetz mit Fußwegen, Mittel über die Sweep-Netze."""
    rows = []
    for h in headways:
        acc = []
        for sd in seeds:
            tt = make_timetable("city", side=side, headway=h, walk=walk, seed=sd)
            st = front_stats(tt, sample_pairs(tt, pairs, sd))
            acc.append({"journey": st["journey"], "front": st["front"], "trips": st["trips"], "stop_times": float(tt.n_stop_times())})
        rows.append({"headway": h, **_mean(acc)})
    return rows


SCAN_CASES = [("city", dict(side=4)), ("city", dict(side=5)), ("city", dict(side=6)), ("city", dict(side=7)), ("random", dict(nodes=40, lines=16)), ("random", dict(nodes=80, lines=24))]


def scan_rows(cases=SCAN_CASES, seeds=C.SWEEP_SEEDS[:3], pairs=C.PAIR_SAMPLES, headway=10, walk=0):
    """Aufwand einer Abfrage: gescannte Halte bei RAPTOR gegen gescannte Verbindungen beim Connection Scan und alle Haltezeiten des Fahrplans (Mittel über Paare und Netze; nur erreichbare Paare); die Ergebnisse werden verglichen."""
    rows = []
    for key, kw in cases:
        acc = []
        for sd in seeds:
            tt = make_timetable(key, headway=headway, walk=walk, seed=sd, **kw)
            sc, cs = [], []
            for s, t, dep in sample_pairs(tt, pairs, sd):
                r = alg.raptor(tt, s, t, dep)
                if not r.front:
                    continue
                a, c = alg.csa_earliest(tt, s, t, dep)
                assert a == r.front[-1][1]
                sc.append(r.counters["scanned"])
                cs.append(c)
            if sc:
                acc.append({"n": tt.n, "stop_times": float(tt.n_stop_times()), "raptor": float(np.mean(sc)), "csa": float(np.mean(cs))})
        rows.append({"key": key, "size": kw.get("side", kw.get("nodes")), **_mean(acc)})
    return rows


RANGE_CASES = [("city", dict(side=5)), ("city", dict(side=6)), ("city", dict(side=7)), ("random", dict(nodes=40, lines=16))]


def range_rows(cases=RANGE_CASES, seeds=C.SWEEP_SEEDS[:3], pairs=8, headway=10, walk=0):
    """Bereichsabfrage über 2 Stunden alle 5 Minuten: gescannte Halte mit gemeinsamen Labels (rRAPTOR) gegen 25 unabhängige Läufe, Stufen der Treppenfunktion; die Fronten stimmen in jedem Fall überein."""
    rows = []
    for key, kw in cases:
        acc = []
        for sd in seeds:
            tt = make_timetable(key, headway=headway, walk=walk, seed=sd, **kw)
            for s, t, dep in sample_pairs(tt, pairs * 2, sd)[:pairs * 2]:
                rng, rc = alg.range_raptor(tt, s, t, dep, dep + WINDOW, RANGE_STEP)
                if not any(f for _, f in rng):
                    continue
                ind, front_ok = 0, True
                for d, f in rng:
                    one = alg.raptor(tt, s, t, d)
                    ind += one.counters["scanned"]
                    front_ok &= one.front == f
                assert front_ok
                acc.append({"shared": float(rc["scanned"]), "independent": float(ind), "steps": float(_steps(rng))})
        rows.append({"key": key, "size": kw.get("side", kw.get("nodes")), **_mean(acc)})
    return rows
