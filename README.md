# Power Manager for Home Assistant

Power Manager ist eine generische Home-Assistant-Integration für ein zentrales Energiemanagement. Sie verbindet vorhandene Home-Assistant-Entities mit einem getesteten Reglerkern und kann damit Peakshaving, PV-Überschussbetrieb und priorisierte Verbrauchersteuerung abbilden.

**Aktueller Stand: V3.0.2**

## Grundprinzip

Power Manager implementiert bewusst keine gerätespezifische MQTT-, Modbus- oder Herstellerkommunikation. Solche Integrationen stellen in Home Assistant Mess- und Stell-Entities bereit. Power Manager liest diese Entities, rechnet intern ausschließlich in kW und schreibt anschließend auf die konfigurierten Home-Assistant-Ausgänge.

```text
Messgeräte / Geräte
        │
        │ MQTT / Modbus / Herstellerintegration
        ▼
Home-Assistant-Entities
        │
        ▼
Power Manager
  ├─ Messwertadapter
  ├─ zentraler Reglerkern
  └─ Ausgangsadapter
        │
        ▼
number / input_number / switch / input_boolean
```

Dadurch bleibt die Regelstrategie unabhängig von einem bestimmten Hersteller, Protokoll, Leistungsbereich oder einer bestimmten Anlage.

## Funktionen von V3.0

- konfigurierbares PMAX und zusätzliche Netz-Sicherheitsreserve
- positive Netzleistung = Bezug, negative Netzleistung = Einspeisung
- Normalbetrieb mit Peakshaving
- PV-Überschussbetrieb
- optionaler Batterie-SOC-Schutz für Überschussverbraucher
- beliebig viele Verbraucher als Home-Assistant-Config-Subentries
- Prioritäten; `1` ist die höchste Priorität
- dynamische Mindest- und Maximalleistung
- dynamische Start-/Stop-Margen
- Mindest-Ein-/Ausschaltzeit und Einschwingzeit
- Lasttypen:
  - modulierbare Leistung
  - Schaltlast
  - EVSE/Wallbox mit Umrechnung kW → A
- optionaler Istleistungssensor je Verbraucher
- optionaler Anforderungs- und Verfügbarkeitseingang
- frei konfigurierbare Home-Assistant-Ausgänge
- Dry-Run und explizite Live-Freigabe
- Diagnose-Sensoren für Budgets, PMAX, Sollwerte, Fail-Safe und Ausgangszustand
- kritische Aktualitätsüberwachung des Netzleistungsmesswerts
- Aktualitätsüberwachung optionaler Istleistungsmesswerte
- Fail-Safe mit sicherem Ausgangszustand
- automatische Deaktivierung der Live-Regelung nach einem Fail-Safe oder Ausgangsfehler
- Ausgangsbefehle werden nur bei tatsächlicher Wertänderung gesendet
- Lastreduzierungen werden vor Laststeigerungen ausgeführt

## Sicherheitsprinzip

Die konfigurierte Netzgrenze hat höchste Priorität.

```text
1. kritischer Messwert / Fail-Safe
2. PMAX minus Sicherheitsreserve
3. technische Min-/Max-Grenzen
4. Prioritäten
5. Hysterese, Mindestzeiten und Komfort
```

Hysterese, Mindestlaufzeit, Mindestauszeit und Einschwingzeit dürfen den Regler nicht dazu veranlassen, absichtlich ein Leistungsbudget oberhalb von PMAX freizugeben. Wenn bereits die nicht regelbare Basislast oberhalb der Netzgrenze liegt, meldet der Regler `grid_limit_unachievable`.

### Fail-Safe

Der Netzleistungsmesswert ist kritisch. Ist er `unknown`, `unavailable`, ungültig oder älter als der konfigurierte Timeout, wird kein normaler Regelzyklus ausgeführt. War Live-Regelung aktiv, werden die konfigurierten sicheren Ausgangszustände bestmöglich gesetzt, die Live-Regelung wird deaktiviert und der interne Laufzeitzustand verworfen. Eine erneute Live-Freigabe muss danach bewusst erfolgen.

Auch bei einem Ausgangsfehler werden alle Ausgänge bestmöglich in ihren sicheren Zustand gefahren und Live-Regelung wird deaktiviert.

### Physikalische Grenze der Softwaregarantie

Power Manager kann garantieren, dass seine **berechneten und angeforderten** Sollwerte das verfügbare PMAX-Budget nicht absichtlich überschreiten. Reale Geräte und Netzwerke können Befehle jedoch verzögert, fehlerhaft oder gar nicht umsetzen. Für belastbares Peakshaving wird deshalb für jeden live geregelten Verbraucher ein echter Istleistungssensor dringend empfohlen. Ohne Istwert muss der Regler den vorherigen Sollwert als Schätzung verwenden.

## Dry-Run und Live-Regelung

Nach jedem Neustart bzw. Reload ist die Live-Regelung **AUS**. Der Regler berechnet trotzdem alle Sollwerte und Diagnosewerte, schreibt aber nichts auf Geräte.

Vor dem Einschalten der Live-Regelung validiert die Integration alle konfigurierten Ausgänge. Dry-Run-Zielwerte werden beim Übergang zu Live nicht als physisch bereits umgesetzte Leistungen übernommen; der Laufzeitzustand wird für den ersten Live-Zyklus zurückgesetzt.

Empfohlene Inbetriebnahme:

1. Messwerte prüfen.
2. Verbraucher hinzufügen.
3. Dry-Run beobachten.
4. Ist-Netzleistung, berechnete Sollwerte und PMAX vergleichen.
5. Zunächst nur einen Verbraucher live testen.
6. Erst danach weitere Verbraucher freigeben.

## Verbraucherarten

### Modulierbare Leistung

Für Verbraucher mit einem numerischen Sollwert. Unterstützte Ausgangs-Entities sind `number` und `input_number`. Die Einheit kann automatisch aus der Entity gelesen oder explizit auf W, kW oder MW festgelegt werden.

### Schaltlast

Für reine Ein/Aus-Verbraucher. Unterstützte Ausgänge sind `switch` und `input_boolean`. Die konfigurierte Maximalleistung ist gleichzeitig die technische Mindestleistung.

### EVSE / Wallbox

Der Regler arbeitet weiter in kW. Der Adapter rechnet den kW-Sollwert mit konfigurierbarer Phasenzahl und Spannung in Ampere um.

```text
I = P * 1000 / (Phasen * Spannung)
```

Mindeststrom, Maximalstrom und Pausenstrom sind frei konfigurierbar. Ein Ziel unterhalb des technischen Mindeststroms wird **nicht nach oben gerundet**, sondern als Pause ausgegeben. Ein Ziel oberhalb der konfigurierten Stromgrenze führt zu einem Fehler und damit zum Fail-Safe statt zu einer stillen Begrenzung.

Hinweis für Simulatoren: Wenn deren MQTT-Schnittstelle direkt einen Leistungs-Sollwert in kW erwartet, sollte die Wallbox dort als **modulierbare Leistung** konfiguriert werden. Der EVSE-Modus ist für eine HA-Entity gedacht, die tatsächlich einen Stromwert in A erwartet.

## Messwerte und Vorzeichen

Intern gelten:

- Netz: positiv = Bezug, negativ = Einspeisung
- Batterie: positiv = Entladen, negativ = Laden
- Verbraucher-Istleistung: nichtnegativ
- Batterie-SOC intern: 0…100 %

Vorzeichen von Netz, PV, Batterie und Verbraucher-Istwert können bei Bedarf über die Konfiguration angepasst werden. Für den Batterie-SOC kann gewählt werden, ob die Quell-Entity Prozent (`0…100`) oder einen Bruchteil (`0…1`) liefert.

## Keine anlagenspezifischen Konstanten im Reglerkern

PMAX, Netzreserve, Leistungen, Prioritäten, Hysterese, Zeitparameter, Wallbox-Spannung/-Phasen/-Ströme und Sensor-Timeouts sind Konfigurationswerte. Der Reglerkern enthält keine Leistungswerte einer konkreten Prüfungs- oder Simulatoranlage.


## Installation über HACS als Custom Repository

Dieses Repository ist für die Installation als HACS Custom Repository vorbereitet.

Nach dem Veröffentlichen auf GitHub:

1. In HACS oben rechts das Menü öffnen.
2. **Custom repositories** wählen.
3. `https://github.com/ww118-rgb/power-manager` eintragen.
4. Kategorie **Integration** wählen.
5. Repository hinzufügen und **Power Manager** installieren.
6. Home Assistant vollständig neu starten.
7. Unter **Einstellungen → Geräte & Dienste → Integration hinzufügen** den **Power Manager** einrichten.

Vor dem ersten Push muss einmal `prepare_hacs_repo.py` ausgeführt werden, damit GitHub-Benutzername und Repository-URL korrekt in `manifest.json` eingetragen werden.

## Installation

Siehe [INSTALLATION.md](INSTALLATION.md).

Für den vorhandenen Energiedaten-Simulator siehe [SIMULATOR_TEST.md](SIMULATOR_TEST.md).

## Tests

Die reine Regelungs-, Konvertierungs- und Paketlogik wird mit `pytest` getestet.

```powershell
pytest -v
```

Der V3.0-Stand enthält außerdem Paritätstests zwischen dem Referenz-Reglerkern und der im Home-Assistant-Paket eingebetteten Version.

## Projektstatus

V3.0 ist als vollständiger Test- und Inbetriebnahmestand für Home Assistant aufgebaut. Die reinen Python-Tests prüfen den Reglerkern und die protokollunabhängigen Adapter. Die endgültige Home-Assistant-Laufzeitprüfung der Config-Subentries, Entities und Service-Aufrufe erfolgt auf einer realen Home-Assistant-Instanz, bevor Live-Regelung an einer realen Anlage verwendet wird.
