# RAPTOR – früher ankommen oder weniger umsteigen – Streamlit-Demo

**[→ Demo live ausprobieren](https://sebastianhanisch-raptor-demo.streamlit.app/)**

Zwölftes und letztes Stück der Kürzeste-Wege-Linie der "Konzepte"-Reihe für die Website "Sebastian Hanisch – Operations Research und Machine Learning", Kind von [Mehrkriterien-Routing](../multicriteria-demo) und [Dijkstra](../dijkstra-demo):
anders als die Fall-Demos im Portfolio (ein Anwendungsfall, mehrere Verfahren im Vergleich) zeigt diese Demo **ein** Verfahren – **RAPTOR**, die Fahrplanauskunft in Runden – an einem wachsenden Beispiel.
Eine Fahrplanauskunft ist kein Kürzeste-Wege-Problem mit festen Kosten: eine "Kante" ist eine **Fahrt mit fester Abfahrt**, und wer umsteigt, muss die nächste Abfahrt abwarten. Außerdem gibt es **zwei Ziele zugleich** – früh ankommen und wenig umsteigen –, die Antwort ist eine **Pareto-Menge**.
RAPTOR arbeitet in **Runden**: Runde *k* bestimmt für jede Haltestelle die früheste Ankunft mit höchstens *k* Fahrten, indem sie jede Linie, die einen in der Vorrunde verbesserten Halt bedient, **einmal** ab dem frühesten solchen Halt abfährt. Keine Warteschlange, kein Graph – nur Linien und ihre Fahrten.

**Einordnung in die Reihe (die Kanten des Graphen):** die Linie ist damit komplett.
```
bfs-demo (Wurzel: Kanten zählen, nicht Kosten)                                       [gebaut]
  └─ dijkstra-demo (Kosten korrekt, blind in alle Richtungen)                        [gebaut]
       ├─ bidirectional-demo → contraction-hierarchies-demo                          [gebaut]
       │                         ├─ hub-labeling-demo (die Suche vorwegnehmen)       [gebaut]
       │                         └─ customizable-ch-demo (Kosten wechseln)           [gebaut]
       ├─ bellman-ford-demo ─┐                                                       [gebaut]
       │   floyd-warshall-demo ─┴→ johnson-demo (Konvergenz: Umgewichtung)           [gebaut]
       ├─ multicriteria-demo (Zeit gegen CO₂, Pareto) ──┐                            [gebaut]
       ├─ time-dependent-demo (Kosten hängen von der Uhrzeit ab)                     [gebaut]
       └─ raptor-demo (Fahrplan: Fahrten statt Kanten, Pareto aus Ankunft und Fahrten) [dieses Stück]
```

## Quellen

| Bestandteil | Quelle |
|---|---|
| Verfahren (RAPTOR, Runden, Pareto-Menge aus Fahrten und Ankunft, Bereichsabfrage) | Delling, Pajor und Werneck (2012); die Bücher (*Grokking Algorithms*, *Optimization Algorithms*) behandeln keine Fahrplanauskunft, es gibt kein Buchbeispiel zu spiegeln |
| Referenz (Connection Scan) | Dibbelt, Pajor, Strasser und Wagner (2013) |
| Umsetzung, naive Runden als zweite Referenz, Bereichsabfrage mit Schranke je Runde, Fußwegabschluss, Messreihen | eigen |
| Alle Fahrpläne | **eigene Erzeuger und erfundene Zeiten**: kleines Netz mit sechs Linien, Stadtnetz mit Bus- und Expresslinien auf einem Raster, Zufalls-Linien – **keine echten Fahrplandaten, kein GTFS** |
| Zahlen | **eigene Messungen** an diesen Fahrplänen |

Aus den Büchern stammt keine Zahl, kein Fahrplan und kein Text. Keine fremden Daten, also keine Lizenzpflichten.

## Ergebnis (Zahlen aus den Tests)

| Frage | Ergebnis |
|---|---|
| Kleines Netz (8 Haltestellen, 6 Linien, Hbf → Flughafen, Abfahrt 8:00) | ✅ **drei Punkte auf der Front**: eine Fahrt (Bus 1 direkt, an 9:05, 65 min), zwei Fahrten (S1 und S2, Umstieg in Park, an 8:51, 51 min) oder drei Fahrten (S1, Bus 3, Bus 4, an 8:40, 40 min) – jede weitere Fahrt spart 14 und 11 min. Zu jeder vollen Stunde dieselben drei Punkte, zur halben nur zwei. RAPTOR läuft 4 Runden und scannt 52 Halte, das Connection Scan 34 Verbindungen |
| Stadtnetz (6 × 6, Takt 10, 10 min je Block zu Fuß, Seed 2) | ✅ von C2 nach F6 drei Verbindungen: **zu Fuß 55 min**, mit einer Fahrt (zu Fuß, Express, zu Fuß) **48 min**, mit zwei Fahrten (Bus S2, Bus Z6) **30 min**; 500 gescannte Halte gegen 388 Verbindungen |
| Zufalls-Linien (40 Halte, 16 Linien, Seed 3) | ✅ von H7 nach H26 zwei Fahrten in 83 min oder drei in 53 min: die dritte Fahrt spart 30 Minuten; RAPTOR 330 Halte, Connection Scan 669 Verbindungen |
| Wie oft gibt es einen Zielkonflikt? (6 × 6-Stadtnetz, Takt 10, Mittel über 5 Fahrpläne × 40 Paare) | ⚠️ ohne Fußwege **3 %** der Paare mit mehr als einem Punkt auf der Front (zwei Fahrten in L-Form sind fast immer die beste Antwort); mit 5 min je Block zu Fuß **58 %**, mit 10 min **95 %** (im Mittel 2.4 Punkte). In den erfundenen Netzen entstehen Zielkonflikte erst durch Fußwege, seltenen Takt oder Linien unterschiedlicher Geschwindigkeit |
| Runden | ✅ höchstens 4 Runden in den Stadtnetzen (bis 5.6 im Mittel über die Fahrpläne bei den Zufalls-Linien) – die Zahl der Fahrten bleibt klein, deshalb ist RAPTOR schnell |
| Takt (mit Fußwegen, 5 min je Block) | ⚠️ Takt 5 / 10 / 15 / 20 / 30: **1.92 / 1.62 / 1.41 / 1.27 / 1.27** Punkte auf der Front, die Fahrzeit der schnellsten Verbindung 14.5 bis 16.8 min (nur 2.3 min mehr, weil bei seltenem Takt zu Fuß gehen die bessere Antwort wird: 0.98 Fahrten gegen 0.27) bei einem sechsmal kleineren Fahrplan |
| Aufwand (ohne Fußwege, Mittel über 3 Fahrpläne) | ⚠️ RAPTOR scannt im 7 × 7-Stadtnetz **269** Halte, das Connection Scan **366** Verbindungen (der Fahrplan hat 21 853 Haltezeiten); im 4 × 4-Netz ist das Connection Scan leicht schneller (75 gegen 80); bei den Zufalls-Linien mit 80 Halten scannt RAPTOR nur **26 %** so viel (212 gegen 800). Das Connection Scan liefert nur die früheste Ankunft, RAPTOR die ganze Front |
| Bereichsabfrage (25 Abfahrten, alle 5 Minuten über 2 Stunden) | ✅ mit gemeinsamen Labels **33 bis 50 % weniger** gescannte Halte als 25 unabhängige Läufe (6 × 6-Netz: 2 915 gegen 4 531), die Fronten sind je Abfahrt **identisch**; die früheste Ankunft ist eine Treppenfunktion mit im Mittel 16.8 Stufen |
| Korrektheit | ✅ die Front stimmt in jedem geprüften Fahrplan mit den **naiven Runden** (alle Fahrten in jeder Runde, ohne Markierungen) überein, die früheste Ankunft mit dem **Connection Scan**; jede Verbindung wird aus den Fahrplandaten **nachgespielt** (Anschlüsse, Zeiten, Umsteigezeit, Fußwege nur nach einer Fahrt); die Bereichsabfrage liefert für jede Abfahrt die Front eines unabhängigen Laufs (Regressionstest: mit der Schranke über alle Runden verdeckte eine Ankunft mit mehr Fahrten aus einer späteren Abfahrt eine gleich frühe mit weniger Fahrten) |

Die Zähler (gescannte Halte, Verbindungen) sind Schritte des Verfahrens und plattformfest. Laufzeiten stehen in der App nur als Messwerte (reines Python) und werden nirgends behauptet oder getestet.

**Zwei Annahmen von RAPTOR, die die Demo prüft:** (1) *kein Überholen* auf einer Linie (die früheste passende Fahrt ist die mit der kleinsten Nummer); (2) **Fußwege sind abgeschlossen** – nach einer Fahrt darf man einmal zu Fuß gehen, und dieser Weg muss so weit reichen wie jede Kette von Wegen. Auf einen kleinen Radius beschränkt, verpasste RAPTOR Verbindungen (im Test gegen das Connection Scan aufgefallen); die Demo schließt die Fußwege per Floyd-Warshall ab.

## Was die Demo zeigt

1. **RAPTOR in Aktion:** ein Regler über die **Runden** (+ Abspielen): die Karte mit den Linien (grau Bus, orange Express, grün Bahn), die Haltestellen gefärbt nach der frühesten Ankunft mit höchstens so vielen Fahrten wie die Runde, die in dieser Runde verbesserten Halte mit Ring; dazu eine Tabelle der verbesserten Halte (wie man hinkommt). In der letzten Runde die gewählte Verbindung mit ihren Etappen (jede in eigener Farbe, Fußwege gestrichelt) als Tabelle.
2. **Früher ankommen oder weniger umsteigen:** Punkte auf der Front, schnellste Verbindung, wenigste Fahrten (und wie viel später), gescannte Halte gegen gescannte Verbindungen; das Urteil unterscheidet Zielkonflikt (Front mit mehreren Punkten), nur ein Punkt, zu Fuß konkurrenzfähig und nicht erreichbar; die **Front** als Diagramm (Fahrten gegen Ankunft) und die **Bereichsabfrage** als Treppenfunktion.
3. **Vergleich** (Expander: RAPTOR, Connection Scan, Bereichsabfrage mit gemeinsamen Labels und mit unabhängigen Läufen); **Experimente auf Knopfdruck**: Front und Runden je Netzart, Takt gegen Fahrzeit, Aufwand gegen Netzgröße, Bereichsabfrage.
4. **Wo die Annahmen enden** (Tabelle; kein Überholen, abgeschlossene Fußwege, starrer Fahrplan, zwei Ziele, erfundene Netze) und **Mathematische Formulierung** (Modell, Runde, Korrektheit, Schranken, Bereichsabfrage, Aufwand als Lehrbuchwert gekennzeichnet).

Bedienung: Beispielnetz per Schnellstart-Knopf laden oder in der Seitenleiste Netz und Abfahrtszeit (6:00 bis 20:00) wählen; beim Stadtnetz Größe, Takt und Fußweg, bei Zufalls-Linien Haltestellen, Linien und Fußweg, bei beiden Ziel (Perzentil der Ankunftszeiten) und Seed; bei mehreren Punkten auf der Front die **Verbindung auf der Front**. Die Adresszeile spiegelt die Konfiguration (Permalink). Höchstens 49 Haltestellen im Stadtnetz, 80 bei den Zufalls-Linien.

## Dateien

| Datei | Inhalt |
|---|---|
| `app.py` | Streamlit-Oberfläche |
| `rp_timetable.py` | Fahrplan (Haltestellen, Linien, Fahrten, Fußwege), Fußwegabschluss, Erzeuger: kleines Netz, Stadtnetz, Zufalls-Linien |
| `rp_algorithm.py` | RAPTOR (Runden, Front, Verbindungen), Bereichsabfrage, naive Runden und Connection Scan als Referenzen |
| `rp_evaluation.py` | Kennzahlen, Front, Bildfolge der Runden, Messreihen |
| `rp_visualization.py`, `rp_presets.py`, `rp_constants.py` | Abbildungen, Presets und Permalink, Konstanten |

## Lokal starten

```bash
pip install -r requirements.txt
streamlit run app.py
```

Tests: `pip install -r requirements-dev.txt` und `python -m pytest tests/`. Jede Zahl in Hilfetexten, Presets und Tabellen ist in `tests/test_claims.py` belegt; die Kreuzprobe läuft gegen zwei unabhängige Verfahren (naive Runden, Connection Scan) und spielt jede Verbindung nach (Fahrpläne mit Fußwegen, mit und ohne Überschneidung der Takte, unerreichbare Ziele, Abfahrt nach der letzten Fahrt, Umsteigezeit 0); ein Regressionstest klickt "▶️ Abspielen" auf Netzen mit mehreren Bildern.
