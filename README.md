# Energiemanager GSI for Home Assistant

Energiemanager GSI ist eine generische Home-Assistant-Integration für ein zentrales Energiemanagement. Sie verbindet vorhandene Home-Assistant-Entities mit einem getesteten Reglerkern und kann damit Peakshaving, PV-Überschussbetrieb und priorisierte Verbrauchersteuerung abbilden.

**Aktueller Stand: V3.3.0 · Home Assistant ab 2026.9**

## Neu in V3.3.0: Kreisgrafik und manuelle Verbrauchersteuerung

- Energieflussmonitor mit schwarzem Hintergrund, grünen/gelben Ringen und animierten Flusspunkten.
- Seitenleiste je Verbraucher: **AUTO / EIN / AUS** sowie frei einstellbarer **kW-Sollwert**.
- Manuelle Anforderungen durchlaufen weiterhin Prioritäten, technische Grenzen, PMAX und das gewählte Überschussbudget.
- Grundverbrauch automatisch aus **Netz + PV + Speicherleistung − Verbraucherleistungen**; Speicherentladung positiv, Speicherladung negativ. Alternativ ist ein separater Hausverbrauchszähler möglich.
- Fehlende Verbraucher-Istmessungen werden als Schätzung gekennzeichnet; Dry-Run-Sollwerte werden nicht als echter Verbrauch in die Hausbilanz eingerechnet.
- Neue HA-Entities für manuelle Anforderung und Betriebsart pro Verbraucher; Aktualisierung der Kartenzuordnung bei Registry-Änderungen.

Siehe [Einrichtung und Handsteuerung V3.3](SETUP_3_3.md). Die Beispielansicht verwendet Wärmepumpe, Wallbox 1, Wallbox 2 und Heizstab.

## Neu in V3.2.0: frei konfigurierbare Ein- und Ausgänge

- Individuelle Faktoren **0,001 / 0,01 / 0,1 / 1 / 10 / 100 / 1000** für Netz, PV, Batterie, SOC und Verbraucher-Ist-/Bedarfsleistung.
- Ausgangseinheit **A oder W** direkt wählbar, auch für EVSE; kW/MW bleiben verfügbar. A nutzt konfigurierbare Phasen und Spannung.
- Eigene **AN-/AUS-Werte**, beispielsweise **12 / 14**, für numerische Schaltlasten und separate Freigaben. Auch `select`-/`input_select`-Optionen sind möglich.
- Neue Strategie **Netzüberschuss** erhält den Hausverbrauch und die Batterieladung. Batterieentladung wird bei vorhandenem Batteriesensor aus dem Budget entfernt. Bestehende Einrichtungen behalten ihre PV-Budget-Strategie.
- Visueller Karteneditor für Titel, W/kW-Anzeige, sichtbare Bereiche, kompakte Darstellung und individuelle Verbrauchernamen/-symbole.
- Ausgangswert je Verbraucher im Energieflussmonitor; korrigierte Zuordnung von Gesamt-Sollwert und projizierter Netzleistung.

Die [Einrichtungsanleitung für V3.2](SETUP_3_2.md) enthält Beispiele für Skalierung, 12/14-Gerätebefehle, Prioritäten und beide Überschussstrategien. Alle Gerätezuordnungen bleiben frei konfigurierbar. Nach dem Start bleibt Live-Regelung aus, bis sie explizit aktiviert wird.

## Neu in V3.1.1: responsive Energiemanager GSI Dashboard Card

V3.1.1 verbessert die in V3.1.0 eingeführte Home-Assistant-Dashboard-Karte. Das Layout richtet sich jetzt nach der tatsächlichen Kartenbreite statt nach der Browserbreite und bleibt damit auch in schmalen Sections lesbar. Zusätzlich werden Summenwerte bei Bedarf aus den Verbraucher-Sollwerten abgeleitet, falls ein globaler Aggregat-Sensor kurzfristig nicht verfügbar ist. Die Regellogik bleibt unverändert.

Die Karte wird zusammen mit der HACS-Integration installiert und von Energiemanager GSI automatisch als Frontend-Modul bereitgestellt. Sie erkennt die Energiemanager GSI-Entities über die Home-Assistant-Entity-Registry und benötigt deshalb keine fest codierten Entity-IDs.

Angezeigt werden unter anderem:

- Betriebsart **Normal / Überschuss**
- sichere Live-Regelungs-Freigabe
- Netzleistung, PV-Leistung, Batterieleistung und Batterie-SOC
- effektives PMAX und verbleibender Headroom
- Basislast und verfügbares Regelbudget
- Energieflussübersicht
- alle konfigurierten regelbaren Verbraucher
- je Verbraucher: Priorität, Istleistung, Sollleistung, Anforderung, Verfügbarkeit sowie Peak-/PV-Freigabe
- aktive und begrenzte Verbraucher
- Netzmessungsstatus, Messwertalter, Ausgangspfad und Fail-Safe

Beim Aktivieren der Live-Regelung sowie bei einem Betriebsartwechsel während aktiver Live-Regelung fordert die Karte eine zusätzliche Bestätigung an.


## Grundprinzip

Energiemanager GSI implementiert bewusst keine gerätespezifische MQTT-, Modbus- oder Herstellerkommunikation. Solche Integrationen stellen in Home Assistant Mess- und Stell-Entities bereit. Energiemanager GSI liest diese Entities, rechnet intern ausschließlich in kW und schreibt anschließend auf die konfigurierten Home-Assistant-Ausgänge.

```text
Messgeräte / Geräte
        │
        │ MQTT / Modbus / Herstellerintegration
        ▼
Home-Assistant-Entities
        │
        ▼
Energiemanager GSI
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
- PV-Überschussbetrieb mit PV-Leistung als priorisiertem Verbraucherbudget
- Batterie-Reserve-SOC mit automatischer Rückkehr von Überschuss auf Normal
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

## Bisherige Überschussstrategie „PV-Budget“ ab V3.0.6

Die folgende Beschreibung gilt für **PV-Budget**. Für echtes Überschussladen ohne zusätzliches Netzbudget die neue Strategie **Netzüberschuss** wählen; Details siehe [Einrichtungsanleitung](SETUP_3_2.md).

Im Modus **Überschuss** bildet die gemessene PV-Leistung das Rohbudget für die als Überschussverbraucher freigegebenen Lasten. Die Leistung wird anschließend nach den konfigurierten Prioritäten verteilt; `1` ist die höchste Priorität. Batterieentladung erweitert dieses PV-Budget nicht.

Eine bereits laufende Batterieladung wird im Überschussbetrieb nicht mehr als zu erhaltende Last reserviert. Dadurch können priorisierte Verbraucher diese PV-Leistung übernehmen. Für die PMAX-Projektion wird die aktuell gemessene Batterieleistung im Überschussbetrieb aus der Basislast herausgerechnet, sodass weder eine laufende Ladung künstlich festgehalten noch eine aktuelle Entladung als dauerhafte PMAX-Stütze vorausgesetzt wird.

Ist ein Batterie-Reserve-SOC konfiguriert, bleibt Überschuss nur aktiv, solange der SOC **oberhalb** dieser Grenze liegt. Bei Erreichen oder Unterschreiten der Grenze wechselt die Home-Assistant-Integration automatisch auf **Normal** zurück. Das ist kein Fail-Safe, sondern die konfigurierte Betriebsstrategie.

Wichtig: Seit V3.0.6 steuert Energiemanager GSI keinen Batterie-Wechselrichter direkt. Sie reserviert im Überschussbetrieb keine Batterieladung und weist vorhandene PV-Leistung zuerst den freigegebenen Verbrauchern zu. Reicht deren Anforderung nicht aus, kann eine externe/automatische Batterieregelung verbleibende PV-Leistung weiterhin laden. Ein hartes Ladeverbot benötigt einen separat regelbaren Batterieaktor.

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

Energiemanager GSI kann garantieren, dass seine **berechneten und angeforderten** Sollwerte das verfügbare PMAX-Budget nicht absichtlich überschreiten. Reale Geräte und Netzwerke können Befehle jedoch verzögert, fehlerhaft oder gar nicht umsetzen. Für belastbares Peakshaving wird deshalb für jeden live geregelten Verbraucher ein echter Istleistungssensor dringend empfohlen. Ohne Istwert muss der Regler den vorherigen Sollwert als Schätzung verwenden.

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

Für Verbraucher mit einem numerischen Sollwert. Unterstützte Ausgangs-Entities sind `number` und `input_number`. Die Einheit kann automatisch aus der Entity gelesen oder explizit auf A, W, kW oder MW festgelegt werden.

### Schaltlast

Für reine Ein/Aus-Verbraucher. Unterstützte Ausgänge sind `switch`, `input_boolean`, `number`, `input_number`, `select` und `input_select`. Bei numerischen bzw. Auswahl-Ausgängen sind AN/AUS frei konfigurierbar. Die konfigurierte Maximalleistung ist gleichzeitig die technische Mindestleistung.

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
5. Repository hinzufügen und **Energiemanager GSI** installieren.
6. Home Assistant vollständig neu starten.
7. Unter **Einstellungen → Geräte & Dienste → Integration hinzufügen** den **Energiemanager GSI** einrichten.

Vor dem ersten Push muss einmal `prepare_hacs_repo.py` ausgeführt werden, damit GitHub-Benutzername und Repository-URL korrekt in `manifest.json` eingetragen werden.

## Dashboard Card verwenden

Nach Installation bzw. Update auf V3.1.0 und einem vollständigen Home-Assistant-Neustart:

1. Dashboard öffnen und **Bearbeiten** wählen.
2. **Karte hinzufügen** wählen.
3. Nach **Energiemanager GSI** suchen.
4. Die Community-Karte **Energiemanager GSI** auswählen.
5. Speichern.

Alternativ kann sie im YAML-Modus mit folgendem Minimalblock verwendet werden:

```yaml
type: custom:power-manager-card
```

Die Karte benötigt keine manuelle Zuordnung der Energiemanager GSI-Entities. Sie liest die zur Integration gehörenden Entities automatisch aus der Entity Registry.

## Installation

Siehe [INSTALLATION.md](INSTALLATION.md).

Für den vorhandenen Energiedaten-Simulator siehe [SIMULATOR_TEST.md](SIMULATOR_TEST.md).

## Tests

Die Regelungs-, Konvertierungs-, Adapter- und Paketlogik wird mit `pytest` getestet. Die Karte hat zusätzlich Verhaltenstests ohne externe Node-Abhängigkeiten:

```powershell
pytest -v
node --test test_frontend.cjs
```

Der V3.0-Stand enthält außerdem Paritätstests zwischen dem Referenz-Reglerkern und der im Home-Assistant-Paket eingebetteten Version.

## Projektstatus

V3.0 ist als vollständiger Test- und Inbetriebnahmestand für Home Assistant aufgebaut. Die reinen Python-Tests prüfen den Reglerkern und die protokollunabhängigen Adapter. Die endgültige Home-Assistant-Laufzeitprüfung der Config-Subentries, Entities und Service-Aufrufe erfolgt auf einer realen Home-Assistant-Instanz, bevor Live-Regelung an einer realen Anlage verwendet wird.
