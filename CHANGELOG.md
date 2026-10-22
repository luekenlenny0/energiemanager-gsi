# Changelog

## Projektname: Energiemanager GSI

HACS, Integration, Konfigurationsdialoge und Dashboard-Karte verwenden den neuen Namen. Bestehende Standard-Konfigurationseinträge werden beim Laden umbenannt; individuelle Titel bleiben erhalten. Technische Domain, Entity-Kennungen und Kartentyp bleiben kompatibel.

## 3.3.0

- Radialer Energieflussmonitor mit Flussrichtung und grünen/gelben Geräteknoten.
- Manuelle Verbrauchersteuerung AUTO/EIN/AUS mit kW-Anforderung in der Seitenleiste.
- Eigene number-/select-Entities je Verbraucher; Bedienung auch über native HA-Aktionen möglich.
- Haus-/Grundverbrauch aus dem Netzzähler, PV, Speicher und tatsächlichen Verbraucherleistungen.
- Optionale Zuordnung eines separaten Hausverbrauchszählers mit Skalierungsfaktor.
- Diagnose bei unplausibler Hausbilanz und Kennzeichnung von Schätzwerten.
- Integrationstests des Coordinators und seiner manuellen HA-Entities mit Zustands-/Aktions-Doubles.

## 3.2.0

- Unabhängige Eingangs-Skalierung mit sieben wählbaren Faktoren.
- A-/W-Ausgänge für modulierbare Verbraucher und EVSE.
- Frei wählbare AN/AUS-Befehle für number/input_number und select/input_select; auch als separate Freigabe.
- Neue Netzüberschussstrategie ohne zusätzliches Netzbudget oder angerechnete Batterieentladung.
- Visueller Editor für den Energieflussmonitor und Verbraucherdarstellung.
- Korrigierte Registry-Zuordnung von Gesamt-Sollwert und projizierter Netzleistung.
- Prüfung mehrfach zugeordneter Ausgänge sowie sichtbare Fehler bei Kartenaktionen.
- Python-Verhaltenstests und Node-Tests für die Dashboard-Karte.
- Mindestversion Home Assistant 2026.9 explizit in HACS-Metadaten angegeben.

## 3.0.0

- vollständige Home-Assistant-Regelstrecke vom Entity-Eingang bis zum optionalen Live-Ausgang
- beliebig viele Verbraucher über Config Subentries
- modulierbare Lasten, Schaltlasten und EVSE-kW→A-Adapter
- Laufzeitumschaltung Normal / Überschuss
- sicherheitsgesperrte Live-Regelung; nach Neustart standardmäßig AUS
- Validierung aller Aktoren vor Live-Freigabe
- Fail-Safe bei fehlendem, ungültigem oder veraltetem kritischem Netzmesswert
- Aktualitätsüberwachung optionaler Verbraucher-Istleistungsmessungen
- sichere Ausgangszustände bei Fail-Safe oder Aktorfehler
- automatische Live-Deaktivierung und Zustandsreset nach Fail-Safe/Aktorfehler
- Zustandsreset beim Wechsel von Dry-Run zu Live zur Vermeidung alter Schätzwerte
- Lastreduzierungen werden vor Laststeigerungen gesendet
- Diagnose-Entities und Verbraucher-Sollwertsensoren
- Batterie-SOC-Quellskalierung 0…100 % oder 0…1
- strengere EVSE- und Ausgangsvalidierung; keine stille Sollwertbegrenzung
- V1.5-Reglerkern unverändert als getestete kW-Regelbasis eingebettet

## 2.4.0

- kritischer Netzsensor-Timeout und Fail-Safe

## 2.3.0

- Home-Assistant-Diagnose-Sensoren und Binary Sensors

## 2.2.0

- Home-Assistant-Messwert-/Coordinator-Schicht

## 2.0.0

- Home-Assistant-/HACS-Grundgerüst und eingebetteter getesteter Reglerkern
