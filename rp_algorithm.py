"""RAPTOR (Delling, Pajor, Werneck 2012): Fahrplanauskunft in Runden. Runde k findet für jede Haltestelle die früheste Ankunft mit höchstens k Fahrten. Jede Runde scannt jede Linie, die einen in der Vorrunde verbesserten Halt bedient,
einmal ab dem frühesten solchen Halt und steigt in die früheste Fahrt ein, die man erreicht; danach werden Fußwege von den in dieser Runde erreichten Halten aus verfolgt. Das Ergebnis am Ziel ist die **Pareto-Menge**
(Zahl der Fahrten, Ankunftszeit): jede weitere Fahrt muss die Ankunft verbessern, sonst ist sie nicht dabei.

Regeln (in allen Verfahren dieser Datei gleich): Zu Beginn stehen wir zur Abfahrtszeit an der Starthaltestelle und dürfen von dort aus einmal zu Fuß gehen. Wer mit einer Fahrt ankommt, braucht die Mindestumsteigezeit, bevor die nächste Fahrt abfährt;
wer zu Fuß ankommt, nicht. Nach einer Fahrt darf man einmal zu Fuß gehen (nicht mehrere Fußwege hintereinander).
Die Fußwege müssen transitiv abgeschlossen sein (rp_timetable.walking_closure): sonst kann ein zu Fuß erreichter Halt eine spätere Ankunft mit einer Fahrt verdecken, von der aus ein weiterer Fußweg möglich wäre - im Test gegen das Connection Scan aufgefallen.

Die Referenzen am Ende sind absichtlich naiv und unabhängig: alle Fahrten in jeder Runde ohne Markierungen (naive_rounds) und Connection Scan (Dibbelt u. a. 2013) über alle Verbindungen nach Abfahrtszeit."""

from dataclasses import dataclass, field

import rp_constants as C

INF = float("inf")


@dataclass
class RaptorResult:
    tt: object
    s: int
    t: int
    depart: float
    tau: list                                   # tau[k][p]: früheste Ankunft an p mit höchstens k Fahrten
    via: list                                   # via[k][p]: 1 = mit einer Fahrt angekommen (Umsteigezeit nötig), 0 = Start oder zu Fuß
    parent: dict                                # (k, p) -> ("start",) | ("trip", Linie, Fahrt, Einstiegsposition, Ausstiegsposition) | ("walk", von, Minuten)
    rounds_of: dict                             # p -> Runden, in denen p verbessert wurde
    history: list                               # history[k] = {p: Ankunft}: in Runde k verbesserte Halte (Fahrt oder Fußweg)
    front: list                                 # [(Fahrten, Ankunft)] mit fallender Ankunft
    rounds: int                                 # Zahl der Runden, die gelaufen sind
    counters: dict = field(default_factory=dict)

    def journey(self, trips):
        """Die Verbindung zur Front-Zahl `trips`: Liste von Etappen ("trip", Linie, Fahrt, von, bis, Abfahrt, Ankunft) und ("walk", von, bis, Minuten, Abfahrt, Ankunft), vom Start zum Ziel."""
        tt, legs = self.tt, []
        p, k = self.t, trips
        while True:
            k2 = max(r for r in self.rounds_of[p] if r <= k)
            rec = self.parent[(k2, p)]
            if rec[0] == "start":
                break
            if rec[0] == "trip":
                _, r, trip, i, j = rec
                route = tt.routes[r]
                legs.append(("trip", r, trip, route.stops[i], route.stops[j], route.times[trip][i], route.times[trip][j]))
                p, k = route.stops[i], k2 - 1
            else:
                _, q, minutes = rec
                legs.append(("walk", q, p, minutes, self.tau[k2][p] - minutes, self.tau[k2][p]))
                p, k = q, k2
        return legs[::-1]


def _ready(tt, tau, via, p, first_round):
    """Frühester Zeitpunkt, zu dem man an p in eine Fahrt einsteigen kann, wenn man mit `tau[p]` (Vorrunde) dort ist."""
    a = tau[p]
    if a == INF:
        return INF
    return a + (tt.change if via[p] else 0)


def raptor(tt, s, t, depart, max_rounds=C.MAX_ROUNDS):
    """RAPTOR von s nach t bei Abfahrt zur Zeit `depart`. Ergebnis: RaptorResult mit Front, Etappen und Zählern (gescannte Halte je Linie, gescannte Linien, verbesserte Labels)."""
    n = tt.n
    tau = [[INF] * n]
    via = [[0] * n]
    best = [INF] * n
    goal = t if t is not None and t >= 0 else None                       # ohne Ziel: alle Haltestellen (keine Zielschranke, keine Front)
    parent, rounds_of, history = {}, {}, [{}]
    counters = {"routes_scanned": 0, "scanned": 0, "improved": 0, "footpaths": 0, "boardings": 0}

    def set_label(k, p, a, kind_via, rec):
        tau[k][p] = a
        via[k][p] = kind_via
        best[p] = a
        parent[(k, p)] = rec
        rs = rounds_of.setdefault(p, [])
        if not rs or rs[-1] != k:
            rs.append(k)
        history[k][p] = a
        counters["improved"] += 1

    def walk_from(k, sources):
        marked = set()
        for p in sources:
            for q, d in tt.footpaths[p]:
                counters["footpaths"] += 1
                a = tau[k][p] + d
                if a < best[q] and (goal is None or a < best[goal]):
                    set_label(k, q, a, 0, ("walk", p, d))
                    marked.add(q)
        return marked

    set_label(0, s, float(depart), 0, ("start",))
    marked = {s} | walk_from(0, [s])
    rounds = 0
    for k in range(1, max_rounds + 1):
        if not marked:
            break
        rounds = k
        tau.append(list(tau[k - 1]))
        via.append(list(via[k - 1]))
        history.append({})
        queue = {}
        for p in marked:
            for r, i in tt.stop_routes[p]:
                if i < len(tt.routes[r].stops) - 1 and (r not in queue or i < queue[r]):
                    queue[r] = i
        improved = set()
        for r, i0 in queue.items():
            route = tt.routes[r]
            counters["routes_scanned"] += 1
            trip, board = None, -1
            for j in range(i0, len(route.stops)):
                p = route.stops[j]
                counters["scanned"] += 1
                if trip is not None:
                    a = route.times[trip][j]
                    if a < best[p] and (goal is None or a < best[goal]):
                        set_label(k, p, a, 1, ("trip", r, trip, board, j))
                        improved.add(p)
                rdy = _ready(tt, tau[k - 1], via[k - 1], p, k == 1)
                if rdy < INF and (trip is None or rdy <= route.times[trip][j]):
                    cand = tt.earliest_trip(r, j, rdy)
                    if cand is not None and (trip is None or cand < trip):
                        trip, board = cand, j
                        counters["boardings"] += 1
        marked = improved | walk_from(k, sorted(improved))
    front, prev = [], INF
    for k in range(len(tau)):
        a = tau[k][goal] if goal is not None else INF
        if a < prev:
            front.append((k, a))
            prev = a
    return RaptorResult(tt, s, t, float(depart), tau, via, parent, rounds_of, history, front, rounds, counters)


# --- Bereichsabfrage (rRAPTOR) ---------------------------------------------------------------------------------------------------------------------------

def range_raptor(tt, s, t, t0, t1, step=5, max_rounds=C.MAX_ROUNDS):
    """Alle Abfahrtszeiten t0, t0 + step, ..., t1 (absteigend abgearbeitet): die Labels der späteren Abfahrten gelten auch bei früherer Abfahrt (man kann warten) und bleiben erhalten, so dass jede Abfahrt nur noch verbessern muss.
    Anders als in einem einzelnen Lauf gilt die Schranke je Runde: eine Ankunft muss besser sein als die mit höchstens k Fahrten (tau[k]), nicht als die mit beliebig vielen - sonst würde eine Ankunft mit mehr Fahrten aus einer späteren
    Abfahrt eine gleich frühe Ankunft mit weniger Fahrten verdecken. Rückgabe: Liste (Abfahrt, Front) nach Abfahrt aufsteigend und die Zähler; die Fronten sind die von unabhängigen Läufen je Abfahrt (in den Tests geprüft)."""
    n = tt.n
    K = max_rounds
    tau = [[INF] * n for _ in range(K + 1)]
    via = [[0] * n for _ in range(K + 1)]
    counters = {"routes_scanned": 0, "scanned": 0, "improved": 0, "runs": 0}
    out = []

    def dense(k):
        """tau[k] = früheste Ankunft mit höchstens k Fahrten: nie später als tau[k - 1]."""
        for p in range(n):
            if tau[k][p] > tau[k - 1][p]:
                tau[k][p], via[k][p] = tau[k - 1][p], via[k - 1][p]

    def walk_from(k, sources):
        marked = set()
        for p in sources:
            for q, d in tt.footpaths[p]:
                a = tau[k][p] + d
                if a < tau[k][q] and a < tau[k][t]:
                    tau[k][q], via[k][q] = a, 0
                    counters["improved"] += 1
                    marked.add(q)
        return marked

    for depart in range(int(t1), int(t0) - 1, -int(step)):
        counters["runs"] += 1
        tau[0][s], via[0][s] = float(depart), 0
        marked = {s} | walk_from(0, [s])
        for k in range(1, K + 1):
            dense(k)
            if not marked:
                continue
            queue = {}
            for p in marked:
                for r, i in tt.stop_routes[p]:
                    if i < len(tt.routes[r].stops) - 1 and (r not in queue or i < queue[r]):
                        queue[r] = i
            improved = set()
            for r, i0 in queue.items():
                route = tt.routes[r]
                counters["routes_scanned"] += 1
                trip = None
                for j in range(i0, len(route.stops)):
                    p = route.stops[j]
                    counters["scanned"] += 1
                    if trip is not None:
                        a = route.times[trip][j]
                        if a < tau[k][p] and a < tau[k][t]:
                            tau[k][p], via[k][p] = a, 1
                            counters["improved"] += 1
                            improved.add(p)
                    rdy = _ready(tt, tau[k - 1], via[k - 1], p, k == 1)
                    if rdy < INF and (trip is None or rdy <= route.times[trip][j]):
                        cand = tt.earliest_trip(r, j, rdy)
                        if cand is not None and (trip is None or cand < trip):
                            trip = cand
            marked = improved | walk_from(k, sorted(improved))
        front, prev = [], INF
        for k in range(K + 1):
            a = tau[k][t]
            if a < prev:
                front.append((k, a))
                prev = a
        out.append((depart, front))
    return out[::-1], counters


# --- Referenzen für die Tests (absichtlich naiv, unabhängig) ---------------------------------------------------------------------------------------------

def naive_rounds(tt, s, t, depart, max_rounds=C.MAX_ROUNDS):
    """Dieselben Runden ohne Markierungen und ohne Suche nach der frühesten Fahrt: in jeder Runde jede Fahrt jeder Linie an jedem Halt als möglichen Einstieg probieren. Rückgabe: tau je Runde."""
    n = tt.n
    tau, via = [[INF] * n], [[0] * n]
    tau[0][s] = float(depart)
    for p in [s]:
        for q, d in tt.footpaths[p]:
            if depart + d < tau[0][q]:
                tau[0][q] = depart + d
    for k in range(1, max_rounds + 1):
        cur, cv = list(tau[k - 1]), list(via[k - 1])
        improved = set()
        for route in tt.routes:
            for trip in route.times:
                for i, p in enumerate(route.stops[:-1]):
                    a0 = tau[k - 1][p]
                    if a0 == INF or a0 + (tt.change if via[k - 1][p] else 0) > trip[i]:
                        continue
                    for j in range(i + 1, len(route.stops)):
                        q = route.stops[j]
                        if trip[j] < cur[q]:
                            cur[q], cv[q] = trip[j], 1
                            improved.add(q)
        for p in sorted(improved):
            for q, d in tt.footpaths[p]:
                if cur[p] + d < cur[q]:
                    cur[q], cv[q] = cur[p] + d, 0
        tau.append(cur)
        via.append(cv)
    return tau


def csa_earliest(tt, s, t, depart):
    """Connection Scan: früheste Ankunft am Ziel mit beliebig vielen Fahrten (Verbindungen einmal nach Abfahrtszeit durchgehen). Rückgabe: (früheste Ankunft, gescannte Verbindungen)."""
    n = tt.n
    arr_trip = [INF] * n                 # früheste Ankunft mit einer Fahrt (Umsteigezeit nötig)
    arr_walk = [INF] * n                 # früheste Ankunft zu Fuß oder am Start (keine Umsteigezeit)
    arr_walk[s] = float(depart)
    for q, d in tt.footpaths[s]:
        arr_walk[q] = min(arr_walk[q], depart + d)
    reached = set()
    scanned = 0
    for dep, arr, a, b, tid in tt.connections():
        if dep < depart:
            continue
        best = min(arr_trip[t], arr_walk[t])
        if dep >= best:
            break
        scanned += 1
        if tid not in reached and not (dep >= arr_walk[a] or dep >= arr_trip[a] + tt.change):
            continue
        reached.add(tid)
        if arr < arr_trip[b]:
            arr_trip[b] = arr
            for q, d in tt.footpaths[b]:
                if arr + d < arr_walk[q]:
                    arr_walk[q] = arr + d
    return min(arr_trip[t], arr_walk[t]), scanned


def earliest_all(tt, s, depart, max_rounds=C.MAX_ROUNDS):
    """Früheste Ankunft an allen Haltestellen mit beliebig vielen Fahrten (RAPTOR ohne Ziel): Liste je Haltestelle (inf: nicht erreichbar) und die Zähler."""
    res = raptor(tt, s, None, depart, max_rounds)
    return list(res.tau[-1]), res.counters
