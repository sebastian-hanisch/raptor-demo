"""RAPTOR - früher ankommen oder weniger umsteigen - interaktive Konzept-Demo
Sebastian Hanisch - Operations Research und Machine Learning

Anders als die Fall-Demos im Portfolio (ein Anwendungsfall, mehrere Verfahren im Vergleich) zeigt diese Demo EIN Verfahren - RAPTOR, die Fahrplanauskunft in Runden - und lässt stattdessen das Beispiel wachsen.
Zwölftes und letztes Stück der Kürzeste-Wege-Linie der "Konzepte"-Reihe: Kanten sind hier keine Straßen mit Kosten, sondern Fahrten mit festen Abfahrten; das Ergebnis ist wie bei den Mehrkriterien eine Pareto-Menge (Ankunft gegen Fahrten).
Siehe README für die Einordnung.

Lauffähig mit: streamlit run app.py
"""

import time

import numpy as np
import pandas as pd
import streamlit as st

import rp_constants as C
import rp_evaluation as ev
from rp_presets import (
    KEPT,
    apply_preset,
    bounds,
    init_session_state_defaults,
    load_permalink_settings,
    randomize_seed,
    sync_query_params,
)
from rp_timetable import make_timetable
from rp_visualization import (
    build_fronts,
    build_front,
    build_headway,
    build_network,
    build_range,
    build_range_rows,
    build_scan,
    journey_table,
    round_table,
)

st.set_page_config(page_title="RAPTOR – Sebastian Hanisch", layout="wide")


def _num(x):
    return f"{x:,.0f}".replace(",", ".")


@st.cache_resource(show_spinner=False, max_entries=8)
def _timetable(params):
    return make_timetable(*params)


@st.cache_resource(show_spinner=False, max_entries=16)
def _analysis(params, depart, distance):
    tt = _timetable(params)
    return ev.analyse(tt, depart, distance, params[-1], fixed=(0, 7) if params[0] == "small" else None)


@st.cache_data(show_spinner=False)
def _fronts():
    return ev.front_rows()


@st.cache_data(show_spinner=False)
def _headways():
    return ev.headway_rows()


@st.cache_data(show_spinner=False)
def _scans():
    return ev.scan_rows()


@st.cache_data(show_spinner=False)
def _ranges():
    return ev.range_rows()


st.title("🚌 RAPTOR – früher ankommen oder weniger umsteigen")
st.markdown(
    """
Eine Fahrplanauskunft ist kein Kürzeste-Wege-Problem mit festen Kosten: eine "Kante" ist eine **Fahrt mit fester Abfahrt**, und wer umsteigt, muss die nächste Abfahrt abwarten. Außerdem gibt es **zwei Ziele zugleich**: früh ankommen und wenig umsteigen - wie bei den Mehrkriterien-Routen ist die Antwort eine **Pareto-Menge**.
**RAPTOR** arbeitet in **Runden**: Runde $k$ bestimmt für jede Haltestelle die früheste Ankunft mit höchstens $k$ Fahrten. Dazu scannt sie jede Linie, die einen in der Vorrunde verbesserten Halt bedient, **einmal** ab dem frühesten solchen Halt und steigt in die früheste Fahrt ein, die man erreicht.
Es braucht weder Warteschlange noch Graphen - nur die Linien und ihre Fahrten. Die Zahl der Runden ist die Zahl der Fahrten, und jede weitere Fahrt muss die Ankunft verbessern, sonst gehört sie nicht zur Front.
"""
)
st.caption(
    "Anders als die Fall-Demos im Portfolio, die an einem Anwendungsfall mehrere Verfahren vergleichen, zeigt diese Demo - zwölftes und letztes Stück der Kürzeste-Wege-Linie der \"Konzepte\"-Reihe, Kind von Mehrkriterien-Routing und Dijkstra - **ein** Verfahren an einem wachsenden Beispiel. "
    "Das Verfahren geht auf Delling, Pajor und Werneck (2012) zurück, die Referenz auf das Connection Scan (Dibbelt, Pajor, Strasser, Wagner 2013); alle Fahrpläne, Netze und Zahlen dieser Demo sind eigene Konstruktionen und Messungen - keine echten Fahrplandaten (kein GTFS)."
)

with st.expander("So funktioniert RAPTOR", expanded=True):
    st.markdown(
        """
1. **Fahrplan:** Haltestellen, **Linien** (feste Halteabfolge, eigene Linie je Richtung) mit **Fahrten** (eine Zeit je Halt) und **Fußwegen** zwischen Haltestellen. Innerhalb einer Linie überholt keine Fahrt eine andere - die früheste passende Fahrt ist die mit der kleinsten Nummer.
2. **Runde 0:** wir stehen zur Abfahrtszeit am Start und dürfen einmal zu Fuß gehen. Jede erreichte Haltestelle bekommt eine früheste Ankunft $\\tau_0$.
3. **Runde $k$:** für jede Linie, die einen in Runde $k-1$ verbesserten Halt bedient, wird sie ab dem frühesten solchen Halt abgefahren. An jedem Halt: (a) mit der Fahrt, in der man sitzt, ankommen und $\\tau_k$ verbessern, falls das besser ist als alles bisher; (b) prüfen, ob man an diesem Halt mit dem Stand der Vorrunde eine **frühere Fahrt** erreicht (Umsteigezeit beachten). Danach ein Fußweg von den verbesserten Halten aus.
4. **Front:** die Ankunft am Ziel je Runde; nur Runden, die sie verbessern, sind Punkte der Pareto-Menge (Fahrten, Ankunft).
5. **Bereichsabfrage:** alle Abfahrtszeiten eines Fensters, von der spätesten zur frühesten; die Labels der späteren Abfahrten bleiben erhalten und dienen als Schranke (man kann am Start warten).
        """
    )

st.caption("🎯 Schnellstart – ein Beispielnetz laden:")
preset_cols = st.columns(len(C.PRESETS))
for i, name in enumerate(C.PRESETS.keys()):
    with preset_cols[i]:
        st.button(name, width="stretch", on_click=apply_preset, args=(name,), help=C.PRESET_HELP[name])

st.caption(
    "🔗 Die Adresszeile oben spiegelt Ihre aktuelle Konfiguration wider – einfach kopieren, "
    "um ein Szenario zu teilen."
)

load_permalink_settings()
init_session_state_defaults()

with st.sidebar:
    st.header("⚙️ Einstellungen")
    net_key = st.selectbox(
        "Netz", C.NETS, key="net_select", format_func=lambda k: C.NET_LABELS[k],
        help="Klein und fest (acht Haltestellen, sechs Linien, Hbf → Flughafen) oder erzeugt (Stadtnetz mit Bus- und Expresslinien auf einem Raster, Zufalls-Linien). Alle Zeiten sind ganze Minuten; Fahrpläne sind erfunden.",
    )
    depart = st.select_slider("Abfahrtszeit", C.DEPART_OPTIONS, key="depart_slider", format_func=C.hhmm,
                              help="Wann man am Start losgeht (Schritte von 5 Minuten, 6:00 bis 20:00). Im kleinen Netz hat die Front zu jeder vollen Stunde drei Punkte (65 / 51 / 40 Minuten), zur halben nur zwei - die Abfahrten der Linien liegen gegeneinander versetzt.")
    if net_key == "city":
        side = st.slider("Haltestellen je Seite", *bounds("side_slider"), key="side_slider", help="Größe des Rasters: n = Seite² Haltestellen; jede Zeile und Spalte ist eine Buslinie, jede dritte hat einen Express.")
        st.session_state[KEPT["side_slider"]] = side
        headway = st.slider("Takt der Buslinien [min]", *bounds("headway_slider"), key="headway_slider", step=5,
                            help="Alle wie viele Minuten eine Buslinie fährt (der Express halb so oft). Mit Fußwegen (5 Minuten je Block) sinkt die Zahl der Punkte auf der Front im Mittel von 1.9 (Takt 5) über 1.6 (Takt 10) und 1.4 (Takt 15) auf 1.3 (Takt 20 und 30); die Fahrzeit der schnellsten Verbindung steigt von 14.5 auf 16.8 min.")
        st.session_state[KEPT["headway_slider"]] = headway
    else:
        side = int(st.session_state.get(KEPT["side_slider"], C.DEFAULT_SIDE))
        headway = int(st.session_state.get(KEPT["headway_slider"], C.DEFAULT_HEADWAY))
    if net_key in ("city", "random"):
        walk = st.slider("Fußweg [min je Block]", *bounds("walk_slider"), key="walk_slider",
                         help="0 = keine Fußwege. Sonst darf man nach jeder Fahrt (und am Start) zu Fuß gehen, so viele Minuten je Block (diagonal entsprechend länger), beliebig weit, aber nur einmal hintereinander. Im 6 × 6-Stadtnetz (Takt 10, Mittel über fünf Netze): 0 min -> 3 % der Paare haben mehr als einen Punkt auf der Front, 5 min -> 58 %, 10 min -> 95 %.")
        st.session_state[KEPT["walk_slider"]] = walk
    else:
        walk = int(st.session_state.get(KEPT["walk_slider"], C.DEFAULT_WALK))
    if net_key == "random":
        nodes = st.slider("Haltestellen", *bounds("nodes_slider"), key="nodes_slider", step=10, help="Anzahl der Haltestellen n.")
        st.session_state[KEPT["nodes_slider"]] = nodes
        lines = st.slider("Linien", *bounds("lines_slider"), key="lines_slider", help="Zahl der Linien (jede mit Hin- und Rückrichtung); mit wenigen Linien sind viele Paare gar nicht verbunden.")
        st.session_state[KEPT["lines_slider"]] = lines
    else:
        nodes = int(st.session_state.get(KEPT["nodes_slider"], C.DEFAULT_NODES))
        lines = int(st.session_state.get(KEPT["lines_slider"], C.DEFAULT_LINES))
    if net_key in ("city", "random"):
        distance = st.slider("Entfernung des Ziels [Perzentil]", *bounds("distance_slider"), key="distance_slider", step=5,
                             help="Das Ziel ist die Haltestelle, deren früheste Ankunft dem Perzentil aller erreichbaren Haltestellen entspricht: 0 = die nächste, 100 = die am spätesten erreichte.")
        st.session_state[KEPT["distance_slider"]] = distance
        seed = st.number_input("Zufalls-Seed", *bounds("seed_input"), key="seed_input", step=1)
        st.session_state[KEPT["seed_input"]] = seed
        st.button("🎲 Neues Netz generieren", width="stretch", on_click=randomize_seed, help="Würfelt einen neuen Zufalls-Seed für den Fahrplan.")
    else:
        distance = int(st.session_state.get(KEPT["distance_slider"], C.DEFAULT_DISTANCE))
        seed = int(st.session_state.get(KEPT["seed_input"], C.DEFAULT_SEED))
        st.caption("Dieses Netz ist fest - Start Hbf, Ziel Flughafen, es gibt nichts zu erzeugen.")

# nicht zum Netz gehörende Regler ändern den Fahrplan nicht: sonst würden gleiche Fahrpläne unter verschiedenen Schlüsseln mehrfach berechnet
d = dict(side=C.DEFAULT_SIDE, headway=C.DEFAULT_HEADWAY, walk=C.DEFAULT_WALK, nodes=C.DEFAULT_NODES, lines=C.DEFAULT_LINES, seed=C.DEFAULT_SEED)
if net_key == "city":
    d.update(side=int(side), headway=int(headway), walk=int(walk), seed=int(seed))
elif net_key == "random":
    d.update(nodes=int(nodes), lines=int(lines), walk=int(walk), seed=int(seed))
params = (net_key, d["side"], d["headway"], d["walk"], d["nodes"], d["lines"], d["seed"])
dist_pct = int(distance) if net_key != "small" else C.DEFAULT_DISTANCE
with st.spinner("Rechne ..."):
    a = _analysis(params, int(depart), dist_pct)
tt, m, res = a.tt, a.metrics, a.res
front = m["front"]
F = len(front)
small = tt.n <= 12
view_key = (params, int(depart), dist_pct)
if st.session_state.get("rp_owner") != view_key:
    st.session_state["rp_owner"] = view_key
    st.session_state["point_slider"] = 0
with st.sidebar:
    if F > 1:
        point = st.slider("Verbindung auf der Front (0 = wenigste Fahrten)", 0, F - 1, key="point_slider",
                          help="Welche Verbindung Karte und Tabelle zeigen: 0 hat die wenigsten Fahrten (und kommt am spätesten an), ganz rechts die meisten (und kommt am frühesten an).")
    else:
        point = 0
        if m["reachable"]:
            st.caption("Nur eine Verbindung auf der Front - kein Zielkonflikt.")
sync_query_params({"net_select": net_key, "depart_slider": int(depart), "side_slider": int(side), "headway_slider": int(headway), "walk_slider": int(walk), "nodes_slider": int(nodes), "lines_slider": int(lines),
                   "distance_slider": int(distance), "seed_input": int(seed)})
chosen = min(st.session_state.get("point_slider", 0), F - 1) if F else None
trips = front[chosen][0] if F else None
frame_list = ev.frames(a)
last_step = len(frame_list) - 1
if st.session_state.get("rp_step_owner") != view_key:
    st.session_state["rp_step_owner"] = view_key
    st.session_state["rp_step"] = last_step

# --- RAPTOR in Aktion ------------------------------------------------------------------------------------------------------------------------------------

st.markdown("## 🎯 RAPTOR in Aktion")
st.caption(f"Start {tt.names[a.s]}, Ziel {tt.names[a.t]}, Abfahrt {C.hhmm(a.depart)}. Die Farbe der Haltestellen zeigt die früheste Ankunft mit höchstens so vielen Fahrten wie die Runde; Runde 0 ist der Start mit den Fußwegen.")
step_col, play_col = st.columns([5, 2])
with step_col:
    step = st.slider("Runde", 0, last_step, key="rp_step",
                     help="Wie viele Runden RAPTOR schon gelaufen ist: 0 = Start (mit Fußwegen), Runde k = früheste Ankunft mit höchstens k Fahrten; ganz rechts die letzte Runde, die etwas verbessert hat. Dann erscheint die gewählte Verbindung.")
with play_col:
    auto_play = st.button("▶️ Abspielen", width="stretch")
view_slot = st.empty()


def _render(current):
    k = frame_list[current]
    final = k >= last_step
    with view_slot.container():
        st.plotly_chart(build_network(a, k, trips if final and m["reachable"] else None, height=400 if small else 460), width="stretch", key=f"net_chart_{current}")
        rows = round_table(a, k)
        if rows:
            imp = len(res.history[k]) if k < len(res.history) else 0
            st.markdown(f"**Runde {k}:** {imp} Halt{'e' if imp != 1 else ''} verbessert (früheste zuerst).")
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        if final and m["reachable"]:
            k_, t_ = front[chosen]
            st.markdown(f"**Verbindung mit {k_} Fahrt{'en' if k_ != 1 else ''}:** Ankunft {C.hhmm(t_)}, {t_ - a.depart:g} min nach der Abfahrt.")
            st.dataframe(pd.DataFrame(journey_table(a, k_)), hide_index=True, width="stretch")


if auto_play:
    n_frames = last_step + 1
    for kk in range(n_frames):
        _render(kk)
        time.sleep(min(0.9, 6.0 / n_frames))
    step = last_step
else:
    _render(step)

st.markdown("---")

# --- Früher ankommen oder weniger umsteigen ------------------------------------------------------------------------------------------------------------

st.markdown("## 🎯 Früher ankommen oder weniger umsteigen")
st.caption("**Zähler** = Schritte: gescannte Halte (ein Halt einer Linie, den RAPTOR in einer Runde besucht) und gescannte Verbindungen beim Connection Scan. Sie sind plattformfest. Laufzeiten stehen nur als Messwerte im Vergleich unten.")
code = ev.verdict(a)
if code == "unreachable":
    st.warning("⚠️ Das Ziel ist mit diesem Fahrplan von diesem Start aus nicht erreichbar - wählen Sie ein anderes Ziel (Entfernung, Seed) oder mehr Linien.")
else:
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Punkte auf der Front", F, delta=f"{front[0][0]} bis {front[-1][0]} Fahrten", delta_color="off", help="Verbindungen, die man nicht in Ankunft und Fahrten zugleich verbessern kann.")
    p2.metric("Schnellste Verbindung", f"{m['fastest']:g} min", delta=f"{front[-1][0]} Fahrten, an {C.hhmm(front[-1][1])}", delta_color="off", help="Dauer ab der Abfahrtszeit (mit Warten am Start).")
    if F > 1:
        p3.metric("Wenigste Fahrten", f"{front[0][0]}", delta=f"+{front[0][1] - front[-1][1]:g} min gegen die schnellste", delta_color="off", help="Die Verbindung mit den wenigsten Fahrten und wie viel später sie ankommt als die schnellste.")
    else:
        p3.metric("Wenigste Fahrten", f"{front[0][0]}", delta="= schnellste", delta_color="off")
    p4.metric("Gescannte Halte", _num(m["scanned"]), delta=f"Connection Scan: {_num(m['csa_scanned'])} Verbindungen", delta_color="off", help=f"RAPTOR scannt in {m['rounds']} Runden {m['routes_scanned']} Linien; der Fahrplan hat {_num(m['stop_times'])} Haltezeiten.")
    if code == "walk":
        st.warning(f"🚶 Zu Fuß ist hier konkurrenzfähig: der Fußweg ({front[0][1] - a.depart:g} min) steht als Punkt mit 0 Fahrten auf der Front" + (f", jede weitere Fahrt spart bis zur schnellsten Verbindung {front[0][1] - front[-1][1]:g} min." if F > 1 else "."))
    elif code == "front":
        gains = [front[i][1] - front[i + 1][1] for i in range(F - 1)]
        st.success(f"✅ **Zielkonflikt: {F} Verbindungen auf der Front** - {front[0][0]} Fahrt{'en' if front[0][0] != 1 else ''}: Ankunft {C.hhmm(front[0][1])}, " + ", ".join(f"{front[i + 1][0]} Fahrten: {C.hhmm(front[i + 1][1])} ({gains[i]:g} min früher)" for i in range(F - 1)) + f". "
                   f"Die Bereichsabfrage zeigt in den nächsten {ev.WINDOW // 60} Stunden {m['range_steps']} verschiedene früheste Ankünfte (Stufen).")
    else:
        st.info(f"ℹ️ Nur eine Verbindung auf der Front: {front[0][0]} Fahrt{'en' if front[0][0] != 1 else ''}, Ankunft {C.hhmm(front[0][1])} - jede weitere Fahrt würde die Ankunft nicht verbessern. Zielkonflikte entstehen bei Fußwegen, seltenem Takt oder Linien unterschiedlicher Geschwindigkeit (siehe Schnellstart).")
    c1, c2 = st.columns(2)
    c1.markdown("**Die Front am Ziel**")
    c1.plotly_chart(build_front(a, chosen), width="stretch", key="front_chart")
    c2.markdown(f"**Bereichsabfrage: Abfahrten von {C.hhmm(a.depart)} bis {C.hhmm(a.depart + ev.WINDOW)}**")
    c2.plotly_chart(build_range(a), width="stretch", key="range_chart")

st.markdown("---")

# --- Vergleich -------------------------------------------------------------------------------------------------------------------------------------

with st.expander("🔧 Wie wir das erreichen – RAPTOR und Connection Scan im Vergleich"):
    if m["reachable"]:
        st.table({"Verfahren": ["RAPTOR (eine Abfahrtszeit)", "Connection Scan (Referenz)", f"Bereichsabfrage: gemeinsame Labels ({m['range_points']} Abfahrten)", f"Bereichsabfrage: {m['range_points']} unabhängige RAPTOR-Läufe"],
                  "Zähler": [f"{_num(m['scanned'])} Halte in {m['routes_scanned']} Linien-Scans", f"{_num(m['csa_scanned'])} Verbindungen", f"{_num(m['range_scanned'])} Halte", f"{_num(m['range_independent'])} Halte"],
                  "Laufzeit [ms]": [f"{a.seconds['raptor'] * 1000:.2f}", f"{a.seconds['csa'] * 1000:.2f}", f"{a.seconds['range'] * 1000:.1f}", "–"]})
        st.caption(f"Der Fahrplan hat {m['routes']} Linien, {_num(m['trips'])} Fahrten und {_num(m['stop_times'])} Haltezeiten. Die Laufzeiten sind Messwerte dieses Laufs (reines Python, ein Lauf, schwankend). Das Connection Scan geht alle Verbindungen nach Abfahrtszeit durch, bis das Ziel erreicht ist, und liefert "
                   f"nur die früheste Ankunft ({'stimmt' if m['exact'] else 'STIMMT NICHT'} mit dem letzten Punkt der Front überein), keine Front. Bei der Bereichsabfrage sind die Fronten je Abfahrt in jedem Fall dieselben wie bei unabhängigen Läufen.")

st.markdown("---")

# --- Experimente -----------------------------------------------------------------------------------------------------------------------------------

st.subheader("📐 Wie viele Fahrten lohnen sich?")
if st.button("Front und Runden je Netzart messen (dauert einen Moment)", key="fronts_start"):
    st.session_state["fronts_on"] = True
if st.session_state.get("fronts_on"):
    with st.spinner("Rechne 6 Netzarten × 5 Fahrpläne × 40 Paare ..."):
        frows = _fronts()
    c1, c2 = st.columns([3, 2])
    c1.plotly_chart(build_fronts(frows), width="stretch", key="fronts_chart")
    c2.table({"Netz": [r["label"].replace("Stadtnetz, ", "").replace(" je Block zu Fuß", " zu Fuß") for r in frows], "Mehr als 1 Punkt": [f"{r['multi']:.0%}" for r in frows], "Runden max": [f"{r['rounds_max']:.0f}" for r in frows]})
    a0, a5, a10 = frows[0], frows[2], frows[3]
    st.caption(f"Zufällige Paare und Abfahrten (6:00 bis 14:00), Mittel über 5 Fahrpläne. Im 6 × 6-Stadtnetz gibt es ohne Fußwege fast nie einen Zielkonflikt ({a0['multi']:.0%} der Paare haben mehr als einen Punkt auf der Front; die schnellste Verbindung braucht im Mittel {a0['trips']:.1f} Fahrten): "
               f"zwei Fahrten in L-Form sind fast immer die beste Antwort. Erst Fußwege schaffen Zielkonflikte: mit 5 min je Block {a5['multi']:.0%}, mit 10 min {a10['multi']:.0%} (im Mittel {a10['front']:.1f} Punkte). Die Zahl der Runden bleibt klein: höchstens {max(r['rounds_max'] for r in frows):.0f} in allen Netzarten - deshalb ist RAPTOR schnell.")

st.markdown("---")

st.subheader("🔬 Takt und Fahrzeit")
if st.button("Takt gegen Fahrzeit messen (dauert einen Moment)", key="headway_start"):
    st.session_state["headway_on"] = True
if st.session_state.get("headway_on"):
    with st.spinner("Rechne 5 Takte × 5 Fahrpläne × 40 Paare ..."):
        hrows = _headways()
    c1, c2 = st.columns([3, 2])
    c1.plotly_chart(build_headway(hrows), width="stretch", key="headway_chart")
    c2.table({"Takt [min]": [str(r["headway"]) for r in hrows], "Fahrzeit [min]": [f"{r['journey']:.1f}" for r in hrows], "Front": [f"{r['front']:.2f}" for r in hrows]})
    st.caption(f"6 × 6-Stadtnetz mit Fußwegen (5 min je Block), Mittel über 5 Fahrpläne. Die schnellste Verbindung braucht bei Takt {hrows[0]['headway']} im Mittel {hrows[0]['journey']:.1f} min, bei Takt {hrows[-1]['headway']} {hrows[-1]['journey']:.1f} min - nur {hrows[-1]['journey'] - hrows[0]['journey']:.1f} min mehr, weil bei seltenem Takt "
               f"zu Fuß gehen die bessere Antwort wird: die mittlere Zahl Fahrten der schnellsten Verbindung sinkt von {hrows[0]['trips']:.2f} auf {hrows[-1]['trips']:.2f}, die Front von {hrows[0]['front']:.2f} auf {hrows[-1]['front']:.2f} Punkte. Der Fahrplan wird dabei sechsmal kleiner ({_num(hrows[0]['stop_times'])} auf {_num(hrows[-1]['stop_times'])} Haltezeiten).")

st.markdown("---")

st.subheader("🔬 Wie viel scannt RAPTOR?")
if st.button("Aufwand gegen Netzgröße messen (dauert einen Moment)", key="scan_start"):
    st.session_state["scan_on"] = True
if st.session_state.get("scan_on"):
    with st.spinner("Rechne 6 Fahrpläne × 3 Seeds × 40 Paare ..."):
        srows = _scans()
    c1, c2 = st.columns([3, 2])
    c1.plotly_chart(build_scan(srows), width="stretch", key="scan_chart")
    c2.table({"Netz": [f"{'Stadt' if r['key'] == 'city' else 'Zufall'} {r['n']:.0f}" for r in srows], "RAPTOR": [_num(r["raptor"]) for r in srows], "Connection Scan": [_num(r["csa"]) for r in srows]})
    st.caption(f"Mittel über 40 Paare in 3 Fahrplänen, ohne Fußwege, nur erreichbare Paare (Ergebnis in jedem Fall mit dem Connection Scan verglichen). RAPTOR scannt im 7 × 7-Stadtnetz im Mittel {_num(srows[3]['raptor'])} Halte, das Connection Scan {_num(srows[3]['csa'])} Verbindungen - bei {_num(srows[3]['stop_times'])} Haltezeiten im ganzen Fahrplan. "
               f"Der Unterschied ist klein: in kleinen Netzen ist das Connection Scan sogar etwas schneller ({_num(srows[0]['csa'])} gegen {_num(srows[0]['raptor'])} im 4 × 4-Netz). Bei den Zufalls-Linien (wenige, lange Linien) scannt RAPTOR nur {srows[5]['raptor'] / srows[5]['csa']:.0%} so viel wie das Connection Scan ({_num(srows[5]['raptor'])} gegen {_num(srows[5]['csa'])}); "
               "das Connection Scan liefert zudem nur die früheste Ankunft, RAPTOR die ganze Front.")

st.markdown("---")

st.subheader("🔬 Die Bereichsabfrage")
if st.button("Gemeinsame Labels gegen unabhängige Läufe messen (dauert einen Moment)", key="range_start"):
    st.session_state["range_on"] = True
if st.session_state.get("range_on"):
    with st.spinner("Rechne 4 Fahrpläne × 3 Seeds × 16 Paare × 25 Abfahrten ..."):
        rrows = _ranges()
    c1, c2 = st.columns([3, 2])
    c1.plotly_chart(build_range_rows(rrows), width="stretch", key="range_exp_chart")
    c2.table({"Netz": [f"{'Stadt' if r['key'] == 'city' else 'Zufall'} {r['size']}" for r in rrows], "Gemeinsam": [_num(r["shared"]) for r in rrows], "Stufen": [f"{r['steps']:.1f}" for r in rrows]})
    saving = [1 - r["shared"] / r["independent"] for r in rrows]
    st.caption(f"25 Abfahrten (2 Stunden alle 5 Minuten), Mittel über 3 Fahrpläne und Paare, ohne Fußwege. Die Bereichsabfrage mit gemeinsamen Labels scannt {min(saving):.0%} bis {max(saving):.0%} weniger Halte als 25 unabhängige Läufe; die Fronten sind in jedem Fall dieselben. "
               f"Die früheste Ankunft ist eine Treppenfunktion der Abfahrtszeit mit im Mittel {rrows[1]['steps']:.0f} Stufen im 6 × 6-Netz: wer eine Minute zu spät kommt, wartet auf die nächste Fahrt.")

st.markdown("---")

# --- Grenzen -----------------------------------------------------------------------------------------------------------------------------------------

st.subheader("🚧 Wo die Annahmen enden")
st.markdown(
    """
| Annahme | Was passiert, wenn sie verletzt ist | Wer setzt an |
|---|---|---|
| **Keine Fahrt überholt eine andere** | Auf einer Linie müssen spätere Fahrten an jedem Halt später sein; sonst ist die früheste passende Fahrt nicht mehr die mit der kleinsten Nummer. Überholende Züge werden in Linien mit gleicher Halteabfolge aufgeteilt (Literatur). | Aufteilung der Linien |
| **Fußwege sind abgeschlossen** | Nach einer Fahrt darf man einmal zu Fuß gehen, und dieser Weg muss so weit reichen wie jede Kette von Wegen - sonst kann eine spätere Fahrt an einem zu Fuß erreichten Halt verdeckt werden. Die Demo schließt die Fußwege ab (beliebig weit gehen, aber nur einmal); auf kleinen Radius beschränkt würde RAPTOR Verbindungen verpassen. | abgeschlossene Fußwegrelation |
| **Der Fahrplan ist bekannt und starr** | Verspätungen und Ausfälle machen die Labels ungültig; RAPTOR wird für jede Abfrage neu gerechnet (das ist billig), Vorberechnung gibt es nicht. Echte Fahrpläne haben Kalender, Zeitzonen, Umsteigezeiten je Bahnhof und Fahrzeugumläufe (Literatur, nicht gebaut). | Verspätungsmodelle |
| **Zwei Ziele: Ankunft und Fahrten** | Weitere Ziele (Preis, Komfort, Fußweg) machen die Front größer; die Ziel-Zahl der Fahrten ist hier die Rundenzahl. Mit Zielen, die keine Runde sind, braucht man Labels wie im Mehrkriterien-Routing. | McRAPTOR (Literatur), Mehrkriterien-Demo |
| **Erfundene Netze sind wie echte** | Die erfundenen Netze (Raster, Zufallslinien) haben selten Zielkonflikte: im 6 × 6-Netz ohne Fußwege haben nur 3 % der Paare mehr als einen Punkt auf der Front. Echte Netze mit Schnellbahn und Nebenlinien haben mehr - die Demo zeigt das am kleinen Netz. | echte Fahrplandaten (GTFS, nicht verwendet) |
"""
)
st.caption("Damit endet die Kürzeste-Wege-Linie. Gebaut sind: Breitensuche, Dijkstra, bidirektionale Suche, Contraction Hierarchies, Bellman-Ford, Floyd-Warshall, Johnson, Mehrkriterien-Routing, zeitabhängiges Routing, Hub Labeling, Customizable Contraction Hierarchies und RAPTOR.")

st.markdown("---")

with st.expander("📐 Mathematische Formulierung"):
    st.markdown(
        r"""
**Modell.** Haltestellen $P$, Linien $R$ mit Halteabfolge $(p_0,\dots,p_{\ell-1})$ und Fahrten $T_r=(\text{trip}_1,\dots)$; $\text{time}(\text{trip},i)$ ist die Zeit der Fahrt am Halt $p_i$. Ohne Überholen gilt $\text{time}(\text{trip}_a,i)\le \text{time}(\text{trip}_b,i)$ für $a<b$ an jedem $i$.
Fußwege $f(p,q)\ge0$ sind transitiv abgeschlossen: $f(p,r)\le f(p,q)+f(q,r)$ (sonst wird die Relation vorher abgeschlossen). Die Mindestumsteigezeit nach einer Fahrt ist $\Delta$.

**Ziel.** Bei Abfahrtszeit $\tau_0$ am Start $s$: $\tau_k(p)$ = früheste Ankunft an $p$ mit **höchstens $k$ Fahrten**. Gesucht ist die Menge der Paare $(k,\tau_k(t))$ mit $\tau_k(t)<\tau_{k-1}(t)$ - die Pareto-Menge aus Fahrten und Ankunft.

**Runde $k$.** Ausgehend von $\tau_{k-1}$: für jede Linie $r$ und jeden Halt $p_i$ mit verbessertem $\tau_{k-1}(p_i)$ wird $r$ ab dem frühesten solchen $i$ gescannt. Man hält die aktuelle Fahrt $e$; an $p_j$ gilt (a) $\tau_k(p_j)\leftarrow\min(\tau_k(p_j),\,\text{time}(e,j))$, (b) ist $\tau_{k-1}(p_j)+\Delta\le\text{time}(e',j)$ für eine frühere Fahrt $e'$ von $r$ (gefunden per Suche in der Spalte der Zeiten), wird $e'$ die aktuelle Fahrt. Danach $\tau_k(q)\leftarrow\min(\tau_k(q),\tau_k(p)+f(p,q))$.

**Korrektheit.** Induktion über $k$: Eine Verbindung mit $k$ Fahrten besteht aus einer Verbindung mit $k-1$ Fahrten bis zu einem Halt $p$ (Ankunft $\ge\tau_{k-1}(p)$) und einer Fahrt ab $p$. Wegen des fehlenden Überholens ist die früheste erreichbare Fahrt der Linie an $p$ optimal, und jede Fahrt, die dort später einsteigt, kommt an keinem folgenden Halt früher an. Der Abschluss der Fußwege sorgt dafür, dass ein einziger Fußweg nach der Fahrt genügt.

**Schranken.** Ein Label wird nur gesetzt, wenn es besser ist als $\tau^*(p)=\min_{k'\le k}\tau_{k'}(p)$ und als die beste Ankunft am Ziel; sonst wäre die Verbindung dominiert. Bei der Bereichsabfrage muss die Schranke je Runde gelten ($\tau_k$, nicht $\min$ über alle Runden), weil Labels aus späteren Abfahrten mit mehr Fahrten sonst gleich frühe Ankünfte mit weniger Fahrten verdecken würden.

**Bereichsabfrage.** Man arbeitet die Abfahrtszeiten von der spätesten zur frühesten ab und behält die Labels: wer später abfährt, kann bei früherer Abfahrt am Start warten, alle Labels bleiben also gültige obere Schranken.

**Aufwand.** Jede Runde scannt jede Linie höchstens einmal, ab dem frühesten verbesserten Halt: $O(K\cdot\sum_r|r|)$ Halte plus die Suche nach der frühesten Fahrt (Lehrbuchwert; gemessen: siehe Experimente).

Implementiert in `rp_timetable.py` (Fahrplan, Fußwegabschluss, Erzeuger), `rp_algorithm.py` (RAPTOR, Bereichsabfrage, naive Referenz und Connection Scan), `rp_evaluation.py` (Kennzahlen, Front, Bildfolge, Experimente).
        """
    )

st.markdown("---")

st.caption(
    "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
    "Operations Research und Machine Learning. Interesse an einer maßgeschneiderten Lösung für "
    "Ihr Unternehmen? [Kontakt aufnehmen](https://sebastianhanisch.net/kontakt.html)"
)
