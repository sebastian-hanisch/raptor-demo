"""Plotly-Abbildungen: Karte mit Linien, früheste Ankunft je Haltestelle nach jeder Runde und der gewählten Verbindung; Front (Fahrten gegen Ankunft), Treppenfunktion der Bereichsabfrage, Tabellen, Experimente.
Achsen sind gesperrt (fixedrange), damit Touch-Geräte beim Scrollen nicht zoomen."""

import numpy as np
import plotly.graph_objects as go

import rp_constants as C
import rp_evaluation as ev

INF = float("inf")


def _base(fig, height):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=-0.18), plot_bgcolor="rgba(0,0,0,0)")
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def _lines(tt, pairs):
    x = np.full(3 * len(pairs), None, dtype=object)
    y = np.full(3 * len(pairs), None, dtype=object)
    for i, (u, v) in enumerate(pairs):
        x[3 * i], x[3 * i + 1] = tt.xy[u, 0], tt.xy[v, 0]
        y[3 * i], y[3 * i + 1] = tt.xy[u, 1], tt.xy[v, 1]
    return x, y


def build_network(a, k, trips=None, height=480):
    """Die Karte nach Runde k: die Linien (grau Bus, orange Express, grün Bahn), die Haltestellen gefärbt nach den Minuten seit der Abfahrt (früheste Ankunft mit höchstens k Fahrten; grau: noch nicht erreicht), die in Runde k verbesserten
    Halte mit Ring. Bei `trips` (Zahl der Fahrten einer Front-Verbindung) die Etappen dieser Verbindung, jede in eigener Farbe."""
    tt = a.tt
    small = tt.n <= 12
    fig = go.Figure()
    seen = {}
    for route in tt.routes:
        for p, q in zip(route.stops[:-1], route.stops[1:]):
            seen[(min(p, q), max(p, q), route.kind)] = (p, q)
    for kind, name in (("Bus", "Bus"), ("Express", "Express"), ("Bahn", "Bahn")):
        pairs = [v for (lo, hi, kd), v in seen.items() if kd == kind]
        if pairs:
            x, y = _lines(tt, pairs)
            fig.add_trace(go.Scatter(x=x, y=y, mode="lines", name=name, line=dict(color=C.COLORS[kind], width=1.5 if kind == "Bus" else 3), hoverinfo="skip", opacity=0.55))
    tau, improved = ev.state_at(a, k)
    arr = np.array([t - a.depart if t < INF else np.nan for t in tau])
    reached = ~np.isnan(arr)
    size = 15 if small else 9
    hover = [f"{tt.names[p]}<br>{'erreicht ' + str(int(arr[p])) + ' min nach der Abfahrt' if reached[p] else 'noch nicht erreicht'}" for p in range(tt.n)]
    text = [f"{tt.names[p]}<br>{int(arr[p])} min" if reached[p] else tt.names[p] for p in range(tt.n)] if small else None
    fig.add_trace(go.Scatter(x=tt.xy[:, 0], y=tt.xy[:, 1], mode="markers+text" if small else "markers", text=text, textposition="top center", showlegend=False, hovertext=hover, hoverinfo="text",
                             marker=dict(size=size, color=np.where(reached, arr, np.nan) if reached.any() else "white", colorscale="Viridis", cmin=0, cmax=max(float(np.nanmax(arr)) if reached.any() else 1.0, 1.0),
                                         colorbar=None if small else dict(title="Minuten<br>seit Abfahrt", thickness=12, len=0.6), line=dict(color="gray", width=1.5))))
    imp = [p for p in improved if k > 0]
    if imp:
        fig.add_trace(go.Scatter(x=tt.xy[imp, 0], y=tt.xy[imp, 1], mode="markers", name=f"in Runde {k} verbessert", hoverinfo="skip", marker=dict(size=size + 7, color="rgba(255,255,255,0)", line=dict(color=C.COLORS["goal"], width=2))))
    if trips is not None and trips in a.journeys:
        for i, leg in enumerate(a.journeys[trips]):
            if leg[0] == "trip":
                route = tt.routes[leg[1]]
                i0, i1 = route.stops.index(leg[3]), route.stops.index(leg[4])
                nodes = route.stops[i0:i1 + 1]
                name, dash = route.line, "solid"
            else:
                nodes = [leg[1], leg[2]]
                name, dash = "zu Fuß", "dash"
            pts = tt.xy[nodes]
            fig.add_trace(go.Scatter(x=pts[:, 0], y=pts[:, 1], mode="lines", name=f"{i + 1}. {name}", line=dict(color=C.COLORS["leg"][i % 8] if dash == "solid" else C.COLORS["walk"], width=6, dash=dash), hoverinfo="skip", opacity=0.8))
    for node, name, color, symbol in ((a.s, "Start", C.COLORS["start"], "square"), (a.t, "Ziel", C.COLORS["goal"], "x")):
        fig.add_trace(go.Scatter(x=[tt.xy[node, 0]], y=[tt.xy[node, 1]], mode="markers", name=f"{name}: {tt.names[node]}", hoverinfo="skip", marker=dict(size=size + 4, color=color, symbol=symbol, line=dict(color="white", width=1.5))))
    fig.update_xaxes(visible=False)
    if "A1" in tt.names:
        fig.update_xaxes(scaleanchor="y", scaleratio=1)
    fig.update_yaxes(visible=False)
    if small:
        lo, hi = tt.xy.min(axis=0), tt.xy.max(axis=0)
        pad = 0.16 * (hi - lo)
        fig.update_xaxes(range=[lo[0] - pad[0], hi[0] + 1.2 * pad[0]])
        fig.update_yaxes(range=[lo[1] - 1.8 * pad[1], hi[1] + 1.8 * pad[1]])
    return _base(fig, height)


def round_table(a, k, top=8):
    """Die in Runde k verbesserten Halte (früheste zuerst): Halt, Ankunft, wie man dorthin kommt."""
    tt, res = a.tt, a.res
    rows = []
    if k >= len(res.history):
        return rows
    for p, t in sorted(res.history[k].items(), key=lambda x: (x[1], x[0]))[:top]:
        rec = res.parent[(k, p)]
        if rec[0] == "start":
            how = "Start"
        elif rec[0] == "trip":
            route = tt.routes[rec[1]]
            how = f"{route.line} ab {tt.names[route.stops[rec[3]]]} {C.hhmm(route.times[rec[2]][rec[3]])}"
        else:
            how = f"zu Fuß von {tt.names[rec[1]]} ({rec[2]} min)"
        rows.append({"Halt": tt.names[p], "Ankunft": C.hhmm(t), "Wie": how})
    return rows


def journey_table(a, trips):
    """Die Etappen einer Front-Verbindung: (Etappe, Linie oder Fußweg, von → nach)."""
    tt = a.tt
    rows = []
    for i, leg in enumerate(a.journeys.get(trips, [])):
        if leg[0] == "trip":
            rows.append({"Etappe": i + 1, "Linie": tt.routes[leg[1]].line, "Fahrt": f"{tt.names[leg[3]]} {C.hhmm(leg[5])} → {tt.names[leg[4]]} {C.hhmm(leg[6])}"})
        else:
            rows.append({"Etappe": i + 1, "Linie": "zu Fuß", "Fahrt": f"{tt.names[leg[1]]} {C.hhmm(leg[4])} → {tt.names[leg[2]]} {C.hhmm(leg[5])} ({leg[3]} min)"})
    return rows


def build_front(a, chosen=None, height=300):
    """Die Pareto-Front am Ziel: Zahl der Fahrten gegen Ankunftszeit; gewählter Punkt hervorgehoben."""
    front = a.metrics["front"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[C.hhmm(x[1]) if False else x[1] / 60.0 for x in front], y=[x[0] for x in front], mode="markers+lines", line=dict(shape="hv", color="#bbbbbb"), name="Front",
                             marker=dict(size=13, color="#1f77b4"), text=[f"{k} Fahrten, an {C.hhmm(t)}" for k, t in front], hoverinfo="text"))
    if chosen is not None:
        k, t = front[chosen]
        fig.add_trace(go.Scatter(x=[t / 60.0], y=[k], mode="markers", name="gewählt", marker=dict(size=20, color="rgba(255,255,255,0)", line=dict(color="#d62728", width=3)), hoverinfo="skip"))
    fig.update_layout(xaxis_title="Ankunft am Ziel [h]", yaxis_title="Fahrten")
    fig.update_yaxes(dtick=1, range=[-0.5, max(x[0] for x in front) + 0.5])
    return _base(fig, height)


def build_range(a, height=300):
    """Bereichsabfrage: früheste Ankunft (schnellste Verbindung) und Ankunft der Verbindung mit den wenigsten Fahrten gegen die Abfahrtszeit im Fenster."""
    rng = a.rng
    fig = go.Figure()
    x = [d / 60.0 for d, _ in rng]
    fig.add_trace(go.Scatter(x=x, y=[f[-1][1] / 60.0 if f else None for _, f in rng], mode="lines+markers", line=dict(shape="hv"), name="früheste Ankunft"))
    fig.add_trace(go.Scatter(x=x, y=[f[0][1] / 60.0 if f else None for _, f in rng], mode="lines", line=dict(shape="hv", dash="dot"), name="Ankunft mit den wenigsten Fahrten"))
    fig.add_vline(x=a.depart / 60.0, line=dict(color="#111111", dash="dash", width=1))
    fig.update_layout(xaxis_title="Abfahrtszeit [h]", yaxis_title="Ankunft [h]")
    return _base(fig, height)


def build_fronts(rows):
    fig = go.Figure()
    x = [r["label"] for r in rows]
    fig.add_trace(go.Bar(x=x, y=[r["front"] for r in rows], name="Punkte auf der Front (Mittel)"))
    fig.add_trace(go.Bar(x=x, y=[r["rounds"] for r in rows], name="Runden (Mittel)"))
    fig.update_layout(barmode="group", yaxis_title="Zahl")
    fig.update_xaxes(tickangle=-25)
    return _base(fig, 360)


def build_headway(rows):
    fig = go.Figure()
    x = [r["headway"] for r in rows]
    fig.add_trace(go.Scatter(x=x, y=[r["journey"] for r in rows], mode="lines+markers", name="Fahrzeit der schnellsten Verbindung [min]"))
    fig.add_trace(go.Scatter(x=x, y=[r["front"] for r in rows], mode="lines+markers", name="Punkte auf der Front", yaxis="y2", line=dict(dash="dot")))
    fig.update_layout(xaxis_title="Takt der Buslinien [min]", yaxis_title="Fahrzeit [min]", yaxis2=dict(title="Front", overlaying="y", side="right", fixedrange=True))
    return _base(fig, 320)


def build_scan(rows):
    fig = go.Figure()
    for key, label, dash in (("city", "Stadtnetz", "solid"), ("random", "Zufalls-Linien", "dot")):
        r = [x for x in rows if x["key"] == key]
        for col, name in (("raptor", "RAPTOR: gescannte Halte"), ("csa", "Connection Scan: gescannte Verbindungen"), ("stop_times", "alle Haltezeiten")):
            fig.add_trace(go.Scatter(x=[x["n"] for x in r], y=[x[col] for x in r], mode="lines+markers", name=f"{name} ({label})", line=dict(dash=dash)))
    fig.update_layout(xaxis_title="Haltestellen", yaxis_title="Schritte einer Abfrage")
    fig.update_yaxes(type="log")
    return _base(fig, 360)


def build_range_rows(rows):
    fig = go.Figure()
    x = [f"{'Stadt' if r['key'] == 'city' else 'Zufall'} {r['size']}" for r in rows]
    fig.add_trace(go.Bar(x=x, y=[r["independent"] for r in rows], name="25 unabhängige Läufe"))
    fig.add_trace(go.Bar(x=x, y=[r["shared"] for r in rows], name="gemeinsame Labels (rRAPTOR)"))
    fig.update_layout(barmode="group", yaxis_title="gescannte Halte")
    return _base(fig, 320)
