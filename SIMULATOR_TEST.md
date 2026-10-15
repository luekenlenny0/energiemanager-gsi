# Energiedaten-Simulator – Test mit Power Manager V3.0

Dieses Dokument beschreibt den Testweg für den vorhandenen Energiedaten-Simulator, ohne Simulatorwerte in den Power-Manager-Code einzubauen.

## Simulator-Schnittstelle

Bei einer frischen Simulatorinstallation läuft:

```text
Web:  http://<SIMULATOR-IP>/
MQTT: <SIMULATOR-IP>:1883
```

Die Teilnehmer verwenden getrennte Topic-Bereiche, zum Beispiel:

```text
sim/t01/...
```

Messwerte werden vom Simulator zyklisch publiziert. Home Assistant verbindet sich mit dem externen Broker des Simulators; ein zweiter Mosquitto-Broker auf Home Assistant ist dafür nicht erforderlich.

## Relevante t01-Messwerttopics

Für den ersten Test sind besonders geeignet:

```text
sim/t01/state/grid/p_kw
sim/t01/state/pv/p_kw
sim/t01/state/battery/p_kw
sim/t01/state/battery/soc

sim/t01/state/hp/p_kw
sim/t01/state/hp/enabled
sim/t01/state/heater/p_kw
sim/t01/state/heater/enabled
sim/t01/state/wallbox/1/p_kw
sim/t01/state/wallbox/1/connected
sim/t01/state/wallbox/1/evse_state
```

Simulator-Konventionen:

```text
Netzleistung:      + Bezug / - Einspeisung
Batterieleistung:  + Entladen / - Laden
Batterie-SOC:      0…1
```

Für Power Manager wird beim SOC deshalb die Quellskalierung **Bruchteil 0…1** gewählt.


Da der Simulator Messwerte zyklisch auch bei unverändertem Zahlenwert sendet, sollten die verwendeten MQTT-Messsensoren in Home Assistant mit `force_update: true` angelegt werden. Sonst kann ein identischer Messwert älter wirken als der konfigurierte Power-Manager-Timeout und einen unnötigen Fail-Safe auslösen.

Ab V3.0.6 gilt im Überschussbetrieb: Die gemessene PV-Leistung ist das Rohbudget für freigegebene Überschussverbraucher. Eine bestehende Batterieladung wird nicht reserviert; Batterieentladung erhöht das PV-Budget nicht. Bei Erreichen oder Unterschreiten des konfigurierten Batterie-Reserve-SOC wechselt Power Manager automatisch auf **Normal** zurück.

## Relevante Stelltopics

Beispiele des Simulators:

```text
sim/t01/cmd/hp/kw
sim/t01/cmd/hp/enabled
sim/t01/cmd/heater/set_kw
sim/t01/cmd/heater/enabled
sim/t01/cmd/wallbox/1/set_kw
```

Wichtig: Der MQTT-Befehl `wallbox/1/set_kw` erwartet im Simulator bereits **kW**. Wird dieser MQTT-Weg verwendet, wird die Wallbox in Power Manager als **modulierbarer Verbraucher mit kW-Ausgang** konfiguriert. Der Power-Manager-EVSE-Modus kW→A ist dagegen für eine Home-Assistant-Entity vorgesehen, die tatsächlich Ampere erwartet, zum Beispiel eine passend konfigurierte Modbus-`number`-Entity.

## Empfohlener erster Test

1. MQTT-Integration in Home Assistant mit dem Broker des Simulators verbinden.
2. Unter `sim/t01/#` prüfen, ob Nachrichten ankommen.
3. Aus Netz, PV, Batterie und SOC Home-Assistant-Entities bereitstellen.
4. Power Manager installieren und nur die globalen Messwerte konfigurieren.
5. Dry-Run ohne Verbraucher prüfen.
6. Einen einzigen Verbraucher mit Istleistungsmessung hinzufügen.
7. Dry-Run-Zielwerte mit Simulatoranzeige vergleichen.
8. Fail-Safe testen.
9. Erst danach Live-Regelung für diesen einen Verbraucher aktivieren.
10. Wenn der Einzeltest stabil ist, weitere Verbraucher hinzufügen.

## Typischer Verbraucheraufbau über MQTT

Für einen modulierbaren Simulatorverbraucher werden in Home Assistant im Prinzip benötigt:

```text
Istleistung: sensor.*       ← sim/t01/state/.../p_kw
Sollwert:    number.*       → sim/t01/cmd/.../set_kw oder .../kw
Freigabe:    switch.*       → sim/t01/cmd/.../enabled   (falls benötigt)
```

Power Manager spricht anschließend nur mit diesen Home-Assistant-Entities. Die MQTT-Details bleiben außerhalb des Reglerkerns.

## Wallbox-Test

Über MQTT:

```text
Istleistung: sim/t01/state/wallbox/1/p_kw
Sollwert:    sim/t01/cmd/wallbox/1/set_kw
```

→ Power-Manager-Typ **modulierbar**, Ausgangseinheit kW.

Über eine echte Strom-Sollwert-Entity in A:

→ Power-Manager-Typ **EVSE**, mit konfigurierbaren Phasen, Spannung, Mindest-/Maximalstrom und Pausenstrom.

## Sicherheitsregel für den Test

Live-Regelung bleibt nach jedem Neustart und nach jedem Fail-Safe AUS. Vor jeder erneuten Freigabe zuerst prüfen, dass Netz- und Istleistungsmesswerte aktuell und plausibel sind.
