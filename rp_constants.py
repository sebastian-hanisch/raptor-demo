"""Konstanten und Grenzen der Regler. Die Zahlen in Hilfetexten und Tabellen der App sind in tests/test_claims.py belegt."""

FIRST, LAST = 300, 1320            # erste und letzte Abfahrt der Linien an ihrem ersten Halt (5:00 bis 22:00), Minuten seit Mitternacht
CHANGE = 2                         # Mindestumsteigezeit in Minuten (nach einer Fahrt)
LOCAL_HOP = 3                      # Minuten je Block bei den Buslinien im Stadtnetz
EXPRESS_HOP = 2                    # Minuten je Block beim Express
EXPRESS_HEADWAY = 2                # der Express fährt so viel seltener wie der Bus
EXPRESS_EVERY = 3                  # jede dritte Zeile und Spalte hat einen Express, er hält an jedem dritten Halt

NETS = ("small", "city", "random")
NET_LABELS = {
    "small": "🔀 Kleines Netz (acht Haltestellen, vier Linien)",
    "city": "🏙️ Stadtnetz (Raster mit Bus und Express)",
    "random": "🕸️ Zufalls-Linien (erzeugt)",
}
FIXED_NETS = ("small",)

SIDE_MIN, SIDE_MAX, DEFAULT_SIDE = 4, 7, 6                 # n = Seite² Haltestellen
HEADWAY_MIN, HEADWAY_MAX, DEFAULT_HEADWAY = 5, 30, 10      # Takt der Buslinien in Minuten
WALK_MIN, WALK_MAX, DEFAULT_WALK = 0, 10, 0                # Fußweg in Minuten je Block (0 = keine Fußwege)
NODES_MIN, NODES_MAX, DEFAULT_NODES = 20, 80, 40
LINES_MIN, LINES_MAX, DEFAULT_LINES = 6, 24, 16
DEPART_MIN, DEPART_MAX, DEFAULT_DEPART = 360, 1200, 480    # Abfahrtszeit in Minuten seit Mitternacht (6:00 bis 20:00, Schritt 5)
DISTANCE_MIN, DISTANCE_MAX, DEFAULT_DISTANCE = 0, 100, 80  # Ziel bei diesem Prozentrang der Ankunftszeiten vom Start
MAX_ROUNDS = 8                     # höchstens so viele Fahrten in einer Verbindung
DEFAULT_SEED = 7
DEFAULT_NET = "small"

DEPART_OPTIONS = tuple(range(DEPART_MIN, DEPART_MAX + 1, 5))


def hhmm(minutes):
    """Uhrzeit "8:05" aus Minuten seit Mitternacht (über 24:00 hinaus: am Folgetag)."""
    m = int(round(minutes))
    return f"{(m // 60) % 24}:{m % 60:02d}"


SWEEP_SEEDS = tuple(range(100000, 100005))
PAIR_SAMPLES = 40

COLORS = {"Bus": "#7f7f7f", "Express": "#ff7f0e", "Bahn": "#2ca02c", "walk": "#8c564b", "start": "#111111", "goal": "#d62728", "leg": ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#8c564b", "#e377c2", "#17becf", "#bcbd22"]}


ROUND_NAMES = ("Start", "1 Fahrt", "2 Fahrten", "3 Fahrten", "4 Fahrten", "5 Fahrten", "6 Fahrten", "7 Fahrten", "8 Fahrten")

_BASE = dict(side=DEFAULT_SIDE, headway=DEFAULT_HEADWAY, walk=DEFAULT_WALK, nodes=DEFAULT_NODES, lines=DEFAULT_LINES, depart=DEFAULT_DEPART, distance=DEFAULT_DISTANCE, seed=DEFAULT_SEED)
PRESETS = {
    "🔀 Kleines Netz": {**_BASE, "net": "small"},
    "🏙️ Stadtnetz": {**_BASE, "net": "city", "walk": 10, "seed": 2, "distance": 100},
    "🕸️ Zufalls-Linien": {**_BASE, "net": "random", "seed": 3, "distance": 80},
    "🐌 Seltener Takt": {**_BASE, "net": "city", "headway": 30, "walk": 10, "seed": 2, "distance": 100},
}
PRESET_HELP = {
    "🔀 Kleines Netz": "Kleines Netz (8 Haltestellen, 6 Linien, Hbf → Flughafen, Abfahrt 8:00): drei Punkte auf der Front - eine Fahrt (Bus 1 direkt, an 9:05, 65 min), zwei Fahrten (S1 und S2, Umstieg in Park, an 8:51, 51 min) oder drei Fahrten (S1, Bus 3, Bus 4, an 8:40, 40 min). Jede weitere Fahrt spart 14 und 11 min. RAPTOR läuft 4 Runden und scannt 52 Halte, das Connection Scan 34 Verbindungen.",
    "🏙️ Stadtnetz": "Stadtnetz (6 × 6, Takt 10, 10 min je Block zu Fuß, Seed 2, Abfahrt 8:00): von C2 nach F6 gibt es drei Verbindungen - zu Fuß in 55 min, mit einer Fahrt (zu Fuß, Express, zu Fuß) in 48 min und mit zwei Fahrten (Bus S2, Bus Z6) in 30 min. RAPTOR scannt 500 Halte in 4 Runden, das Connection Scan 388 Verbindungen.",
    "🕸️ Zufalls-Linien": "Zufalls-Linien (40 Haltestellen, 16 Linien, Seed 3, Abfahrt 8:00): von H7 nach H26 zwei Verbindungen - mit zwei Fahrten in 83 min oder mit drei Fahrten in 53 min: die dritte Fahrt spart 30 Minuten. RAPTOR scannt 330 Halte, das Connection Scan 669 Verbindungen.",
    "🐌 Seltener Takt": "Stadtnetz mit Takt 30 (sonst wie das Stadtnetz-Beispiel): von C2 nach A5 gehen zu Fuß in 40 min und die Fahrt (zu Fuß, Bus Z2, zu Fuß) in 38 min fast gleich schnell - bei seltenem Takt lohnt sich der Bus kaum. Das Connection Scan scannt hier nur 146 Verbindungen, RAPTOR 311 Halte.",
}
