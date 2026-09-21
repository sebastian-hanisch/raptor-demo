"""Fahrplanmodell: Haltestellen, Linien (feste Halteabfolge), Fahrten (eine Zeit je Halt, Minuten seit Mitternacht), Fußwege zwischen Haltestellen und eine Mindestumsteigezeit.

Innerhalb einer Linie fahren alle Fahrten mit denselben Fahrzeiten, eine spätere Fahrt ist also an jedem Halt später als eine frühere - es gibt kein Überholen. Das ist die Annahme, auf der RAPTOR beruht (die früheste passende Fahrt
ist die mit der kleinsten Nummer). Alle Zeiten sind ganze Minuten: Gleichstände sind exakt, Zähler und Zeiten plattformfest."""

import bisect
import math
from dataclasses import dataclass, field

import numpy as np

import rp_constants as C

INF = float("inf")


@dataclass
class Route:
    line: str                       # Name der Linie ("Bus 1", "S1", ...)
    kind: str                       # "Bus", "Express", "Bahn" (nur für die Zeichnung)
    stops: list                     # Haltestellen in Fahrtrichtung
    times: list                     # times[trip][j]: Zeit der Fahrt an Halt j (Ankunft = Abfahrt)
    cols: list = field(default_factory=list)      # cols[j] = Zeiten aller Fahrten an Halt j (aufsteigend)

    def __post_init__(self):
        self.cols = [[t[j] for t in self.times] for j in range(len(self.stops))]


@dataclass
class Timetable:
    names: tuple
    xy: np.ndarray
    routes: list
    footpaths: list                 # footpaths[p] = [(q, Minuten)]
    change: int                     # Mindestumsteigezeit in Minuten (nach einer Fahrt, vor der nächsten)
    stop_routes: list = field(default_factory=list)      # stop_routes[p] = [(Linie, Position)]
    _conns: list = field(default_factory=list, repr=False)

    def __post_init__(self):
        self.stop_routes = [[] for _ in self.names]
        for r, route in enumerate(self.routes):
            for j, p in enumerate(route.stops):
                self.stop_routes[p].append((r, j))

    @property
    def n(self):
        return len(self.names)

    def n_trips(self):
        return sum(len(r.times) for r in self.routes)

    def n_stop_times(self):
        return sum(len(r.times) * len(r.stops) for r in self.routes)

    def connections(self):
        """Alle Verbindungen (Abfahrt, Ankunft, von, bis, Fahrtnummer) nach Abfahrtszeit sortiert (für das Connection Scan der Referenz)."""
        if not self._conns:
            rows, tid = [], 0
            for route in self.routes:
                for trip in route.times:
                    for j in range(len(route.stops) - 1):
                        rows.append((trip[j], trip[j + 1], route.stops[j], route.stops[j + 1], tid))
                    tid += 1
            rows.sort()
            self._conns = rows
        return self._conns

    def earliest_trip(self, r, j, ready):
        """Nummer der frühesten Fahrt der Linie r, die an Halt j frühestens zur Zeit `ready` fährt (None: keine mehr)."""
        col = self.routes[r].cols[j]
        i = bisect.bisect_left(col, ready)
        return i if i < len(col) else None


def walking_closure(n, edges):
    """Fußwege als transitiv abgeschlossene Relation: aus einzelnen Fußwegen (p, q, Minuten) werden alle kürzesten Gehzeiten zwischen erreichbaren Haltestellen (Floyd-Warshall). RAPTOR setzt das voraus - nach einer Fahrt darf man einmal
    zu Fuß gehen, und dieser eine Weg muss so weit reichen wie jede Kette von Wegen. Rückgabe: footpaths[p] = [(q, Minuten)] ohne p selbst."""
    d = np.full((n, n), INF)
    np.fill_diagonal(d, 0.0)
    for p, q, m in edges:
        d[p, q] = min(d[p, q], m)
        d[q, p] = min(d[q, p], m)
    for k in range(n):
        d = np.minimum(d, d[:, k:k + 1] + d[k:k + 1, :])
    return [[(q, int(d[p, q])) for q in range(n) if q != p and d[p, q] < INF] for p in range(n)]


def _trips(first, last, headway, offset, runtimes):
    """Fahrten einer Linie: erste Abfahrt `first + offset`, dann alle `headway` Minuten bis `last`; runtimes = Minuten zwischen aufeinanderfolgenden Halten."""
    out, t0 = [], first + offset
    while t0 <= last:
        t = [t0]
        for r in runtimes:
            t.append(t[-1] + r)
        out.append(t)
        t0 += headway
    return out


def make_route(line, kind, stops, runtimes, headway, offset=0, first=C.FIRST, last=C.LAST):
    return Route(line, kind, list(stops), _trips(first, last, headway, offset, runtimes))


def with_reverse(route_spec):
    """Dieselbe Linie in Gegenrichtung (eigene Linie, gleiche Fahrzeiten)."""
    line, kind, stops, runtimes, headway, offset = route_spec
    return (line + " ↔", kind, stops[::-1], runtimes[::-1], headway, offset)


# --- Kleines Netz -------------------------------------------------------------------------------------------------------------------------------------

SMALL_STOPS = [("Hbf", 0.0, 1.5), ("Nord", 1.5, 3.0), ("Markt", 1.5, 0.0), ("Uni", 3.4, 1.5), ("Park", 5.0, 3.0), ("Messe", 5.0, 0.0), ("Hafen", 6.6, 1.5), ("Flughafen", 8.2, 1.5)]
# (Linie, Art, Halte, Fahrzeiten zwischen den Halten in Minuten, Takt in Minuten, Versatz der ersten Abfahrt)
SMALL_LINES = [("Bus 1", "Bus", [0, 1, 2, 3, 4, 5, 6, 7], [7, 7, 7, 7, 6, 5, 7], 20, 19),          # hält überall, fährt direkt bis zum Flughafen
               ("S1", "Bahn", [0, 2, 4], [12, 12], 30, 3), ("S2", "Bahn", [4, 6, 7], [11, 10], 30, 0),                   # Bahn mit einem Umstieg in Park
               ("Bus 2", "Bus", [0, 1, 2], [3, 4], 15, 12), ("Bus 3", "Bus", [2, 3, 5], [3, 4], 20, 0), ("Bus 4", "Bus", [5, 6, 7], [6, 5], 15, 14)]      # Zubringer mit zwei Umstiegen


def small_timetable():
    names = tuple(s[0] for s in SMALL_STOPS)
    xy = np.array([(s[1], s[2]) for s in SMALL_STOPS])
    routes = [make_route(*spec) for spec in SMALL_LINES]
    return Timetable(names, xy, routes, [[] for _ in names], C.CHANGE)


# --- Stadtnetz ------------------------------------------------------------------------------------------------------------------------------------------

def city_timetable(side, headway, walk, seed):
    """Haltestellen auf einem Raster. Jede Zeile und Spalte ist eine Buslinie (alle Halte, 3 Minuten je Block, in beide Richtungen, Takt `headway`); jede dritte Zeile und Spalte hat zusätzlich einen Express (nur jeder dritte Halt und der letzte,
    2 Minuten je Block, doppelter Takt). `walk` > 0: Fußwege zwischen benachbarten Haltestellen (auch diagonal), `walk` Minuten je Block (aufgerundet), als abgeschlossene Relation (man darf beliebig weit gehen, aber nur einmal hintereinander)."""
    rng = np.random.default_rng([int(seed), 3131])
    n = side * side
    names = tuple(f"{chr(65 + i)}{j + 1}" for i in range(side) for j in range(side))
    xy = np.array([(j, i) for i in range(side) for j in range(side)], dtype=float)
    specs = []
    for axis in ("row", "col"):
        for k in range(side):
            stops = [k * side + j for j in range(side)] if axis == "row" else [i * side + k for i in range(side)]
            label = f"{'Z' if axis == 'row' else 'S'}{k + 1}"
            spec = (f"Bus {label}", "Bus", stops, [C.LOCAL_HOP] * (side - 1), headway, int(rng.integers(0, headway)))
            specs += [spec, with_reverse(spec)]
            if k % C.EXPRESS_EVERY == 0:
                keep = sorted(set(range(0, side, C.EXPRESS_EVERY)) | {side - 1})
                es = [stops[j] for j in keep]
                spec = (f"Express {label}", "Express", es, [C.EXPRESS_HOP * (b - a) for a, b in zip(keep[:-1], keep[1:])], C.EXPRESS_HEADWAY * headway, int(rng.integers(0, C.EXPRESS_HEADWAY * headway)))
                specs += [spec, with_reverse(spec)]
    routes = [make_route(*s) for s in specs]
    foot = [[] for _ in range(n)]
    if walk > 0:
        edges = [(p, q, int(math.ceil(walk * float(np.hypot(*(xy[p] - xy[q]))) - 1e-9))) for p in range(n) for q in range(p + 1, n) if float(np.hypot(*(xy[p] - xy[q]))) < 1.5]
        foot = walking_closure(n, edges)
    return Timetable(names, xy, routes, foot, C.CHANGE)


# --- Zufalls-Linien --------------------------------------------------------------------------------------------------------------------------------------

def random_timetable(n, lines, walk, seed):
    """Zufällig verteilte Haltestellen; jede Linie ist ein Zufallsweg über die vier nächsten Nachbarn (5 bis 9 Halte, beginnend bei einem Halt ohne Linie, in beide Richtungen), Takt zufällig 10, 15, 20 oder 30 Minuten, Fahrzeit nach Entfernung.
    `walk` > 0: Fußwege zwischen Haltestellen im Abstand unter 1.2 (Einheit = mittlerer Abstand), `walk` Minuten je Einheit (aufgerundet), als abgeschlossene Relation."""
    rng = np.random.default_rng([int(seed), 5151])
    xy = rng.random((n, 2)) * 10.0
    names = tuple(f"H{i + 1}" for i in range(n))
    dist = np.hypot(*(xy[:, None, :] - xy[None, :, :]).transpose(2, 0, 1))
    knn = [list(np.argsort(dist[p])[1:5]) for p in range(n)]
    specs, tries, covered = [], 0, set()
    while len(specs) < 2 * lines and tries < 40 * lines:
        tries += 1
        length = int(rng.integers(5, 10))
        uncovered = [v for v in range(n) if v not in covered]
        path = [int(rng.choice(uncovered)) if uncovered else int(rng.integers(0, n))]      # zuerst Halte ohne Linie: das Netz hängt eher zusammen
        while len(path) < length:
            options = [int(q) for q in knn[path[-1]] if int(q) not in path]
            if not options:
                break
            path.append(options[int(rng.integers(0, len(options)))])
        if len(path) < 4:
            continue
        covered |= set(path)
        headway = int(rng.choice([10, 15, 20, 30]))
        runtimes = [max(2, int(math.ceil(dist[a, b] * 2.5))) for a, b in zip(path[:-1], path[1:])]
        spec = (f"Linie {len(specs) // 2 + 1}", "Bus", path, runtimes, headway, int(rng.integers(0, headway)))
        specs += [spec, with_reverse(spec)]
    routes = [make_route(*s) for s in specs]
    foot = [[] for _ in range(n)]
    if walk > 0:
        edges = [(p, q, int(math.ceil(walk * dist[p, q] - 1e-9))) for p in range(n) for q in range(p + 1, n) if dist[p, q] < 1.2]
        foot = walking_closure(n, edges)
    return Timetable(names, xy, routes, foot, C.CHANGE)


def make_timetable(net, side=C.DEFAULT_SIDE, headway=C.DEFAULT_HEADWAY, walk=C.DEFAULT_WALK, nodes=C.DEFAULT_NODES, lines=C.DEFAULT_LINES, seed=C.DEFAULT_SEED):
    if net == "small":
        return small_timetable()
    if net == "city":
        return city_timetable(int(side), int(headway), int(walk), int(seed))
    if net == "random":
        return random_timetable(int(nodes), int(lines), int(walk), int(seed))
    raise ValueError(net)
