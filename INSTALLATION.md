# Installation und Inbetriebnahme – Energiemanager GSI V3.1

## Installation über HACS Custom Repository

Wenn das Projekt auf GitHub veröffentlicht wurde, kann es über HACS als Custom Repository installiert werden:

```text
HACS
→ ⋮
→ Custom repositories
→ GitHub-Repository-URL eintragen
→ Type: Integration
→ Add
```

Danach **Energiemanager GSI** in HACS installieren und Home Assistant vollständig neu starten.

Die Repository-Metadaten werden vor dem ersten Push mit `prepare_hacs_repo.py` gesetzt; Details stehen in `HACS_SETUP.md`.

## Manuelle Installation

### Dateien installieren

Für eine manuelle Installation wird der Ordner

```text
power_manager
```

nach

```text
/config/custom_components/power_manager
```

kopiert. Danach Home Assistant vollständig neu starten.

Die Installation muss anschließend mindestens diese Dateien enthalten:

```text
/config/custom_components/power_manager/
├── __init__.py
├── actuator.py
├── allocator.py
├── binary_sensor.py
├── config_flow.py
├── const.py
├── controller.py
├── coordinator.py
├── load_adapter.py
├── load_config.py
├── manifest.json
├── measurements.py
├── models.py
├── outputs.py
├── select.py
├── sensor.py
├── strings.json
├── switch.py
├── frontend/
│   └── power-manager-card.js
└── translations/
    ├── de.json
    └── en.json
```

## 2. Energiemanager GSI hinzufügen

In Home Assistant:

```text
Einstellungen
→ Geräte & Dienste
→ Integration hinzufügen
→ Energiemanager GSI
```

Global werden mindestens konfiguriert:

- Netzleistungs-Entity
- PMAX in kW
- Netz-Sicherheitsreserve in kW
- Netzsensor-Timeout

Optional:

- PV-Leistung
- Batterieleistung
- Batterie-SOC
- Mindest-SOC für Überschussbetrieb
- Vorzeicheninvertierungen
- SOC-Skalierung 0…100 oder 0…1

## 3. Verbraucher hinzufügen

Am Energiemanager GSI-Konfigurationseintrag werden Verbraucher als Untereinträge hinzugefügt.

Wichtige Felder:

- eindeutiger Name
- Typ: modulierbar / Schaltlast / EVSE
- Priorität (`1` = höchste)
- Mindest- und Maximalleistung
- Standard-Anforderung
- optionaler Istleistungssensor
- Timeout für den Istleistungssensor
- optionaler Anforderungseingang
- optionaler Verfügbarkeitseingang
- Ausgangs-Entity
- optionaler Freigabe-Ausgang
- sicherer Ausgangswert
- Peakshaving / Überschuss aktiv
- Start-/Stop-Margen
- Mindest-Ein-/Ausschaltzeit
- Einschwingzeit

Bei EVSE zusätzlich:

- Phasen
- Spannung
- Mindeststrom
- Maximalstrom
- Pausenstrom

## 4. Dry-Run prüfen

Die Entity **Live-Regelung** bleibt zunächst AUS.

Prüfen:

- Netzleistung stimmt mit dem Quellsensor überein.
- `Netzmessung gültig` ist EIN.
- `Fail-Safe aktiv` ist AUS.
- effektives PMAX = PMAX − Sicherheitsreserve.
- Basislast ist plausibel.
- Verbraucher-Sollwerte reagieren auf Laständerungen wie erwartet.
- prognostizierte Netzleistung bleibt innerhalb des berechneten Budgets, sofern die Basislast selbst beherrschbar ist.

## 5. Fail-Safe testen

Vor Livebetrieb den Netzsensor testweise ungültig/unavailable machen oder einen sehr kurzen Timeout verwenden.

Erwartung:

```text
Netzmessung gültig = AUS
Fail-Safe aktiv = EIN
Live-Regelung = AUS
```

Nach Wiederherstellung der Messung bleibt Live-Regelung absichtlich AUS und muss manuell neu freigegeben werden.

## 6. Ersten Verbraucher live testen

Empfohlen wird, zunächst nur einen Verbraucher zu konfigurieren und einen echten Istleistungssensor zu verwenden.

Vor der Freigabe kontrollieren:

- Ausgangs-Entity existiert und ist verfügbar.
- numerische Min-/Max-Werte passen zur Verbraucher-Konfiguration.
- sicherer Ausgangswert ist technisch wirklich sicher.
- bei EVSE stimmen Phasen, Spannung und Stromgrenzen.
- Netzsensor und Verbraucher-Istleistung aktualisieren sich zuverlässig.

Dann **Live-Regelung** einschalten. Energiemanager GSI validiert die Ausgänge erneut, verwirft Dry-Run-Laufzeitschätzungen und beginnt mit einem frischen Live-Regelzustand.

## 7. Verhalten bei Fehlern

Bei kritischem Messfehler oder Ausgangsfehler:

- normale Regelung stoppt,
- sichere Ausgänge werden bestmöglich gesetzt,
- Live-Regelung wird deaktiviert,
- alte Zielwertschätzungen werden verworfen,
- Diagnose-Entities zeigen Ursache und Ausgangszustand.

## 8. Dashboard Card hinzufügen

Seit V3.1.0 wird die Energiemanager GSI-Dashboard-Karte zusammen mit der Integration installiert. Ein separates HACS-Frontend-Repository ist nicht erforderlich.

Nach einem vollständigen Home-Assistant-Neustart:

```text
Dashboard
→ Bearbeiten
→ Karte hinzufügen
→ Energiemanager GSI
```

Falls die Karte unmittelbar nach einem Update noch nicht im Card Picker sichtbar ist, die Browserseite einmal hart neu laden.

Im YAML-Karteneditor kann die Karte auch direkt angelegt werden:

```yaml
type: custom:power-manager-card
```

Die Karte erkennt die Energiemanager GSI-Entities automatisch. Sie zeigt globale Mess- und Diagnosewerte sowie für jeden konfigurierten Verbraucher Ist-, Soll- und Anforderungsleistung, Priorität und Freigabestatus.

Die Live-Freigabe in der Karte bleibt sicherheitskritisch: Vor dem Einschalten erscheint eine zusätzliche Bestätigung.

## 9. Wichtiger Hinweis zur realen PMAX-Einhaltung

Der Regler kann keine physikalisch verzögerte oder fehlerhafte Geräteantwort verhindern. Für ernsthaftes Peakshaving sollten reale Istleistungswerte der geregelten Verbraucher vorhanden sein und die Zeitparameter passend zur Anlage gewählt werden. Vor einer realen Anlage zuerst Dry-Run und anschließend einen einzelnen Verbraucher unter kontrollierten Bedingungen testen.
