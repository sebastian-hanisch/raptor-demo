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
    tau: list                                   # tau[k][p]: früheste Ankunft an p mit höchstens k Fahrten (egal wie angekommen)
    via: list                                   # via[k][p]: 1 = die früheste Ankunft ist eine Fahrt-Ankunft (strikt früher als jede zu Fuß), 0 = Start oder zu Fuß (oder gleichzeitig)
    parent: dict                                # (k, p) -> ("start",) | ("trip", Linie, Fahrt, Einstiegsposition, Ausstiegsposition) | ("walk", von, Minuten): wie die früheste Ankunft zustande kam
    rounds_of: dict                             # p -> Runden, in denen tau an p verbessert wurde
    history: list                               # history[k] = {p: Ankunft}: in Runde k verbesserte Halte (Fahrt oder Fußweg)
    front: list                                 # [(Fahrten, Ankunft)] mit fallender Ankunft
    rounds: int                                 # Zahl der Runden, die gelaufen sind
    counters: dict = field(default_factory=dict)
    tau_walk: list = field(default_factory=list)    # tau_walk[k][p]: früheste Ankunft zu Fuß (oder am Start): man kann sofort einsteigen
    tau_trip: list = field(default_factory=list)    # tau_trip[k][p]: früheste Ankunft mit einer Fahrt: man braucht die Umsteigezeit
    parent_walk: dict = field(default_factory=dict)  # (k, p) -> Eintrag wie in parent, aber für die Fuß-Ankunft (auch wenn sie tau nicht verbessert)
    parent_trip: dict = field(default_factory=dict)  # dasselbe für die Fahrt-Ankunft
    rounds_walk: dict = field(default_factory=dict)  # p -> Runden, in denen tau_walk an p gesetzt wurde
    rounds_trip: dict = field(default_factory=dict)  # p -> Runden, in denen tau_trip an p gesetzt wurde

    def journey(self, trips):
        """Die Verbindung zur Front-Zahl `trips`: Liste von Etappen ("trip", Linie, Fahrt, von, bis, Abfahrt, Ankunft) und ("walk", von, bis, Minuten, Abfahrt, Ankunft), vom Start zum Ziel."""
        tt, legs = self.tt, []
        rounds = {"walk": self.rounds_walk, "trip": self.rounds_trip}
        parents = {"walk": self.parent_walk, "trip": self.parent_trip}
        arrivals = {"walk": self.tau_walk, "trip": self.tau_trip}
        p, k = self.t, trips
        k2 = max(r for r in self.rounds_of[p] if r <= k)
        mode = "trip" if self.parent[(k2, p)][0] == "trip" else "walk"
        while True:
            k2 = max(r for r in rounds[mode][p] if r <= k)
            rec = parents[mode][(k2, p)]
            if rec[0] == "start":
                break
            if rec[0] == "trip":
                _, r, trip, i, j = rec
                route = tt.routes[r]
                legs.append(("trip", r, trip, route.stops[i], route.stops[j], route.times[trip][i], route.times[trip][j]))
                p, k = route.stops[i], k2 - 1
                # Einstieg: mit der Fuß-Ankunft (sofort) oder der Fahrt-Ankunft (plus Umsteigezeit) der Vorrunde - die, die zur Abfahrt reicht (bei beiden: die der frühesten Ankunft)
                kb = max(r2 for r2 in self.rounds_of[p] if r2 <= k)
                first = "trip" if self.parent[(kb, p)][0] == "trip" else "walk"
                for m in (first, "walk" if first == "trip" else "trip"):
                    rs = [r2 for r2 in rounds[m].get(p, []) if r2 <= k]
                    if rs and arrivals[m][k][p] + (tt.change if m == "trip" else 0) <= route.times[trip][i]:
                        mode = m
                        break
                else:
                    raise AssertionError("kein gültiger Anschluss")
            else:
                _, q, minutes = rec
                arrival = self.tau_walk[k2][p]
                legs.append(("walk", q, p, minutes, arrival - minutes, arrival))
                p, k = q, k2
                mode = "walk" if k2 == 0 else "trip"
        return legs[::-1]


def raptor(tt, s, t, depart, max_rounds=C.MAX_ROUNDS):
    """RAPTOR von s nach t bei Abfahrt zur Zeit `depart`. Ergebnis: RaptorResult mit Front, Etappen und Zählern (gescannte Halte je Linie, gescannte Linien, verbesserte Labels).

    Je Halt und Runde gibt es zwei Ankünfte: zu Fuß (oder am Start; man kann sofort einsteigen) und mit einer Fahrt (man braucht die Umsteigezeit). Eine spätere Fuß-Ankunft kann den Anschluss erreichen,
    den die frühere Fahrt-Ankunft wegen der Umsteigezeit verpasst - mit nur einem Label je Halt ging diese Verbindung verloren. tau ist das Minimum der beiden."""
    n = tt.n
    tauW, tauT = [[INF] * n], [[INF] * n]
    tau, via = [[INF] * n], [[0] * n]
    best = [INF] * n
    goal = t if t is not None and t >= 0 else None                       # ohne Ziel: alle Haltestellen (keine Zielschranke, keine Front)
    parent, parent_w, parent_t, history = {}, {}, {}, [{}]
    rounds_of, rounds_w, rounds_t = {}, {}, {}
    counters = {"routes_scanned": 0, "scanned": 0, "improved": 0, "footpaths": 0, "boardings": 0}

    def set_label(k, p, a, trip_mode, rec):
        (tauT if trip_mode else tauW)[k][p] = a
        (parent_t if trip_mode else parent_w)[(k, p)] = rec
        rs = (rounds_t if trip_mode else rounds_w).setdefault(p, [])
        if not rs or rs[-1] != k:
            rs.append(k)
        if a < tau[k][p]:
            tau[k][p] = a
            best[p] = a
            parent[(k, p)] = rec
            history[k][p] = a
            rs = rounds_of.setdefault(p, [])
            if not rs or rs[-1] != k:
                rs.append(k)
        via[k][p] = 1 if tauT[k][p] < tauW[k][p] else 0
        counters["improved"] += 1

    def walk_from(k, sources):
        marked = set()
        for p in sources:
            base = tauW[0][p] if k == 0 else tauT[k][p]                  # nach einer Fahrt (oder am Start) einmal zu Fuß
            for q, d in tt.footpaths[p]:
                counters["footpaths"] += 1
                a = base + d
                if a < tauW[k][q] and a < tauT[k][q] + tt.change and (goal is None or a < best[goal]):
                    set_label(k, q, a, False, ("walk", p, d))
                    marked.add(q)
        return marked

    set_label(0, s, float(depart), False, ("start",))
    marked = {s} | walk_from(0, [s])
    rounds = 0
    for k in range(1, max_rounds + 1):
        if not marked:
            break
        rounds = k
        for arr in (tauW, tauT, tau, via):
            arr.append(list(arr[k - 1]))
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
                        set_label(k, p, a, True, ("trip", r, trip, board, j))
                        improved.add(p)
                rdy = min(tauW[k - 1][p], tauT[k - 1][p] + tt.change)       # frühester Einstieg mit dem Stand der Vorrunde
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
    return RaptorResult(tt, s, t, float(depart), tau, via, parent, rounds_of, history, front, rounds, counters, tauW, tauT, parent_w, parent_t, rounds_w, rounds_t)


# --- Bereichsabfrage (rRAPTOR) ---------------------------------------------------------------------------------------------------------------------------

def range_raptor(tt, s, t, t0, t1, step=5, max_rounds=C.MAX_ROUNDS):
    """Alle Abfahrtszeiten t0, t0 + step, ..., t1 (absteigend abgearbeitet): die Labels der späteren Abfahrten gelten auch bei früherer Abfahrt (man kann warten) und bleiben erhalten, so dass jede Abfahrt nur noch verbessern muss.
    Anders als in einem einzelnen Lauf gilt die Schranke je Runde: eine Ankunft muss besser sein als die mit höchstens k Fahrten (tau[k]), nicht als die mit beliebig vielen - sonst würde eine Ankunft mit mehr Fahrten aus einer späteren
    Abfahrt eine gleich frühe Ankunft mit weniger Fahrten verdecken. Wie in `raptor` gibt es je Halt zwei Ankünfte (zu Fuß / mit einer Fahrt). Rückgabe: Liste (Abfahrt, Front) nach Abfahrt aufsteigend und die Zähler; die Fronten sind die von unabhängigen Läufen je Abfahrt (in den Tests geprüft)."""
    n = tt.n
    K = max_rounds
    tauW = [[INF] * n for _ in range(K + 1)]
    tauT = [[INF] * n for _ in range(K + 1)]
    counters = {"routes_scanned": 0, "scanned": 0, "improved": 0, "runs": 0}
    out = []

    def dense(k):
        """tau[k] = früheste Ankunft mit höchstens k Fahrten: nie später als tau[k - 1] (je Art der Ankunft)."""
        for p in range(n):
            if tauW[k][p] > tauW[k - 1][p]:
                tauW[k][p] = tauW[k - 1][p]
            if tauT[k][p] > tauT[k - 1][p]:
                tauT[k][p] = tauT[k - 1][p]

    def walk_from(k, sources):
        marked = set()
        for p in sources:
            base = tauW[0][p] if k == 0 else tauT[k][p]
            for q, d in tt.footpaths[p]:
                a = base + d
                if a < tauW[k][q] and a < tauT[k][q] + tt.change and a < min(tauW[k][t], tauT[k][t]):
                    tauW[k][q] = a
                    counters["improved"] += 1
                    marked.add(q)
        return marked

    for depart in range(int(t1), int(t0) - 1, -int(step)):
        counters["runs"] += 1
        tauW[0][s] = float(depart)
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
                        if a < min(tauW[k][p], tauT[k][p]) and a < min(tauW[k][t], tauT[k][t]):
                            tauT[k][p] = a
                            counters["improved"] += 1
                            improved.add(p)
                    rdy = min(tauW[k - 1][p], tauT[k - 1][p] + tt.change)
                    if rdy < INF and (trip is None or rdy <= route.times[trip][j]):
                        cand = tt.earliest_trip(r, j, rdy)
                        if cand is not None and (trip is None or cand < trip):
                            trip = cand
            marked = improved | walk_from(k, sorted(improved))
        front, prev = [], INF
        for k in range(K + 1):
            a = min(tauW[k][t], tauT[k][t])
            if a < prev:
                front.append((k, a))
                prev = a
        out.append((depart, front))
    return out[::-1], counters


# --- Referenzen für die Tests (absichtlich naiv, unabhängig) ---------------------------------------------------------------------------------------------

def naive_rounds(tt, s, t, depart, max_rounds=C.MAX_ROUNDS):
    """Dieselben Runden ohne Markierungen und ohne Suche nach der frühesten Fahrt: in jeder Runde jede Fahrt jeder Linie an jedem Halt als möglichen Einstieg probieren. Zu Fuß und mit einer Fahrt Angekommene
    werden getrennt geführt (Umsteigezeit nur nach einer Fahrt). Rückgabe: tau je Runde (das Minimum beider)."""
    n = tt.n
    walk, trip_arr = [INF] * n, [INF] * n
    walk[s] = float(depart)
    for q, d in tt.footpaths[s]:
        walk[q] = min(walk[q], depart + d)
    tau = [[min(walk[p], trip_arr[p]) for p in range(n)]]
    for k in range(1, max_rounds + 1):
        ready = [min(walk[p], trip_arr[p] + tt.change) for p in range(n)]
        new_trip = list(trip_arr)
        for route in tt.routes:
            for trip in route.times:
                for i, p in enumerate(route.stops[:-1]):
                    if ready[p] > trip[i]:
                        continue
                    for j in range(i + 1, len(route.stops)):
                        q = route.stops[j]
                        new_trip[q] = min(new_trip[q], trip[j])
        new_walk = list(walk)
        for p in range(n):
            if new_trip[p] < INF:
                for q, d in tt.footpaths[p]:
                    new_walk[q] = min(new_walk[q], new_trip[p] + d)
        walk, trip_arr = new_walk, new_trip
        tau.append([min(walk[p], trip_arr[p]) for p in range(n)])
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
