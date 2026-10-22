# Energiemanager GSI 3.4 – Modbus, MQTT und eigene Seitenleiste

Nach dem HACS-Update Home Assistant neu starten. Links erscheint **Energiemanager GSI** mit dem Symbol `mdi:home-lightning-bolt`. Die bestehende Dashboard-Karte funktioniert weiter. Die Mindestversion bleibt Home Assistant **2026.8.3**.

Im eigenen Bereich stehen Energiefluss, Prioritäten, AUTO/EIN/AUS und der manuelle kW-Wunsch pro Verbraucher bereit. Auch ein manueller Wunsch durchläuft Leistungsgrenzen und Prioritäten. **Ansicht anpassen** ändert Titel, Anzeigeeinheit, Symbole und sichtbare Verbraucher; diese Darstellung wird pro Benutzer im jeweiligen Browser gespeichert. Unter **Konfiguration** öffnest du die Gerätezuordnung.

## Mess- und Stellpunkte anlegen

**Einstellungen → Geräte & Dienste → Energiemanager GSI → Mess-/Stellpunkt hinzufügen**. Je nach HA-Ansicht befindet sich die Aktion im Menü des Integrationseintrags. Für jeden Messwert bzw. Ausgang einen Punkt anlegen:

| Entitätstyp | Verwendung |
|---|---|
| `sensor` | Netzbezug/Einspeisung, PV, Speicherleistung, SOC, tatsächlicher Verbrauch |
| `number` | Frei skalierbarer Sollwert, z. B. W, kW, A; alternativ numerischer EIN/AUS-Code |
| `switch` | Freigabe mit frei wählbarem EIN-/AUS-Payload oder Modbus-Registerwert |

Anschließend die erzeugten Entitäten in den globalen Einstellungen bzw. beim Verbraucher auswählen. Einen Sollwert-Ausgang niemals als Verbrauchsmessung verwenden: Eine Gerätebestätigung oder ein gesendeter Befehl ist kein tatsächlicher Verbrauch. Die Punkte werden unabhängig von DryRun gelesen; der GSI-Regler schreibt erst bei aktivierter Live-Regelung. Direkte HA-Serviceaufrufe an eine Stellpunkt-Entität sind hingegen unmittelbare Gerätebefehle.

Falls noch kein Netzsensor existiert, bei der Ersteinrichtung **Zuerst Modbus-/MQTT-Punkte anlegen** aktivieren. Dann den Zählerpunkt hinzufügen und seine Sensorentität in der globalen Konfiguration nachtragen. Ohne gültige, frische Netzleistungsmessung bleibt die Regelung im Fail-safe.

## Modbus TCP

Eigener TCP-Client, keine separate HA-Modbus-YAML-Konfiguration erforderlich. IP/Hostname, Port (üblicherweise 502), Unit ID, Registeradresse und Datentyp sind pro Punkt frei konfigurierbar. Adressen sind **0-basiert**: Eine Herstellerangabe wie 40001 muss gemäß Herstellerdokumentation in die tatsächliche Protokolladresse umgerechnet werden.

- Lesen: `holding` FC3, `input` FC4, `coil` FC1, `discrete` FC2.
- Schreiben: Holding-Register FC6 (`single`, nur 16 Bit) oder FC16 (`multiple`); Coils FC5. Input-/Discrete-Bereiche sind ausschließlich lesbar.
- Datentypen: uint16, int16, uint32, int32, float32, float64. Byte- und Wortreihenfolge jeweils big/little.
- Skalierung: **HA-Wert = Rohwert × Faktor**; Schreiben verwendet die Umkehrung. Faktor muss positiv sein. Vorzeichen bei Bedarf in der Zähler-/Verbraucherzuordnung invertieren.
- Ganzzahlregister akzeptieren nur exakt darstellbare Werte. Ein nicht darstellbarer Sollwert wird mit sichtbarem Fehler abgewiesen; GSI rundet eine Leistung nicht stillschweigend auf. Faktor und Geräteauflösung passend einstellen. Bei Bedarf einen vom Gerät unterstützten Float-Sollwert nutzen.
- Abfrageintervall und Antwort-Timeout sind einstellbar. Messwert-Timeout mindestens auf deren Summe setzen. Der globale Zähler-Timeout muss ebenfalls zur Abfragerate passen.
- Bei einem Switch im Holding-Register z. B. `uint16`, EIN `12`, AUS `14` einstellen. Bei Coils gelten deren binäre EIN/AUS-Werte.
- Rücklesen für Ausgänge ist abschaltbar. Ohne Rücklesen zeigt die Entität den zuletzt gesendeten Wert als **angenommenen Zustand**. Der Verbindungsstatus bestätigt dann nur die TCP-Erreichbarkeit, nicht die Umsetzung im Gerät.

Beispiel Zähler: sensor, Modbus, Hersteller-IP, input, int32, Adresse laut Datenblatt, Einheit W, Faktor 1. Beispiel Wallbox-Sollwert: number, holding, passender Datentyp, Einheit A, geeignete Minimal-/Maximalwerte. Danach die number-Entität dem Wallbox-Ausgang zuweisen; Phasen und Spannung beim Verbraucher einstellen.

## MQTT

Zuerst **Home Assistants MQTT-Integration** mit dem gewünschten Broker einrichten. GSI nutzt deren Verbindung und Zugangsdaten. Es ist keine zusätzliche MQTT-YAML-Konfiguration und kein zweiter Broker nötig.

- Konkrete Messwert-/Rückmelde- und Befehls-Topics frei wählen, ohne Wildcards `+` oder `#`.
- Reine Zahl als Payload oder JSON-Pfad wie `data.power` bzw. `values.0.power`.
- Befehlsvorlage standardmäßig `{value}`. Für JSON z. B. `{"power":{value}}`; für Textwerte in JSON `{"state":"{value}"}`. Es wird nur `{value}` ersetzt, kein Programmcode ausgewertet.
- Switch-Payloads z. B. EIN `12`, AUS `14` oder EIN `ON`, AUS `OFF`.
- Nummern werden beim Lesen mit dem Faktor multipliziert und beim Schreiben durch ihn geteilt.
- QoS 0/1/2 und Befehls-Retain einstellbar. Standard: **Retain aus**. Retain-Befehle können bei einem Geräte-Neustart erneut wirksam werden.
- Retain-Messwerte werden als möglicherweise veraltet ignoriert. Für Zähler und Rückmeldungen muss das Gerät regelmäßig neue Nachrichten senden. Bei Ablauf des Messwert-Timeouts oder Broker-Trennung wird der Punkt nicht verfügbar. Nach Wiederverbindung wird ein frischer Messwert verlangt.
- Ohne Rückmelde-Topic ist ein number-/switch-Zustand nur angenommen. Ein Publish bestätigt keine physische Ausführung. Anlegen, Neuladen und Wiederverbinden publizieren selbst keine Gerätebefehle.

Beispiel Wärmepumpen-Freigabe: switch, MQTT, Befehls-Topic laut Gerät, EIN `12`, AUS `14`; Rückmelde-Topic optional. Diesen Switch als Freigabe/Schaltausgang des Verbrauchers wählen. Die Verbraucher-Codes sind für native Switch-Entitäten unerheblich; GSI ruft deren turn_on/turn_off auf und der Punkt übersetzt diese in die eingestellten Payloads.

## Grundverbrauch und Prüfung

Bei einem Netzbezugs-/Einspeisezähler gilt weiterhin: **Hausverbrauch = Netz + PV + Speicherentladung** (Laden negativ). **Grundverbrauch = Hausverbrauch − tatsächliche Verbraucherleistungen**. Dafür die Verbrauchsmesspunkte separat zuordnen; DryRun-Sollwerte zählen nicht als physischer Verbrauch.

Nach der Zuordnung zunächst im DryRun kontrollieren: Vorzeichen, Einheit, Skalierung, Ist-/Sollwerte, Prioritäten und sichere AUS-Werte. Danach kann die Live-Regelung über die GSI-Oberfläche aktiviert werden. Das Update aktiviert sie nicht automatisch. Änderungen an Punkten laden den Integrationseintrag neu; die Live-Freigabe fällt dabei wie bisher zurück.

Die Softwaretests prüfen lokale Modbus-TCP-Testserver, MQTT-API-Simulationen, Fehlerantworten, Verbindungsabbrüche, veraltete Messwerte, Skalierung und 12/14-Codes. Echte Geräte und ein echter MQTT-Broker wurden im Rahmen dieser Entwicklung nicht angesteuert.
