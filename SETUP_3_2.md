# Energiemanager GSI 3.2 – Einrichtung

Diese Erweiterung ergänzt die vorhandene Integration um Skalierungsfaktoren, frei wählbare Gerätebefehle, A-/W-Ausgaben und einen anpassbaren Energieflussmonitor. Alle Sensoren und Verbraucher werden frei zugeordnet.

## Installation

Voraussetzung: Home Assistant Core ab 2026.9 und vorhandene Mess-/Stell-Entities der Geräte.

**Über HACS:** Das GitHub-Repository als benutzerdefiniertes Repository der Kategorie **Integration** hinzufügen. Für diese Version muss der neue Stand zuerst in den Hauptbranch übernommen oder als Release veröffentlicht sein. Danach Energiemanager GSI herunterladen und Home Assistant neu starten.

**Mit dem ZIP:** Den Ordner `custom_components/power_manager` aus `power-manager-3.2.0.zip` nach `/config/custom_components/power_manager` kopieren. Eine vorhandene Installation vorher sichern und den kompletten Komponentenordner ersetzen. Home Assistant anschließend neu starten.

Unter **Einstellungen → Geräte & Dienste → Integration hinzufügen → Energiemanager GSI** den Netzleistungssensor auswählen. Positive Netzleistung bedeutet Bezug, negative Einspeisung. Bei umgekehrten Vorzeichen die Invertierung einschalten.

## Peakshaving und Prioritäten

- **PMAX** begrenzt den gesamten Netzbezug in kW. Die Sicherheitsreserve wird davon abgezogen.
- Jeden Verbraucher über **Verbraucher hinzufügen** anlegen. Sensoren, Ausgänge, Bedarf und Verfügbarkeit frei auswählen.
- **Priorität 1** ist die höchste. Niedrigere Prioritäten werden zuerst reduziert. Gleiche Prioritäten teilen das Budget.
- Pro Verbraucher Mindest-/Maximalleistung konfigurieren. Eine Schaltlast benötigt immer ihre volle Nennleistung.
- Einschalt-/Ausschaltzeiten und Start-/Stop-Margen verhindern häufiges Schalten. PMAX hat Vorrang.

Die Netzgrenze gilt am gesamten Anschluss; dies ist keine getrennte Absicherung jeder Phase. Die Leistungsgrenzen je Verbraucher bleiben zusätzlich wirksam.

## Überschussladen

Die Betriebsart im Monitor auf **Überschuss** stellen. Die globale Konfiguration bietet zwei Strategien:

| Strategie | Verhalten |
| --- | --- |
| Netzüberschuss | Budget = bereits geregelte Istleistung − Netzbezug − Batterieentladung, mindestens 0. Sonstiger Hausverbrauch und vorhandene Batterieladung bleiben berücksichtigt. Standard für neue Einrichtungen. |
| PV-Budget | Bisherige Strategie: verteilt die PV-Erzeugung nach Priorität, begrenzt durch PMAX. Kann zusätzlichen Netzbezug erlauben. Bleibt bei bestehenden Konfigurationen erhalten. |

Beispiel: Der Lader verbraucht bereits 2 kW, der Zähler zeigt 1 kW Einspeisung. Ohne Batterieentladung stehen insgesamt 3 kW für die geregelten Verbraucher zur Verfügung. Nach der Erhöhung auf 3 kW bleibt das Budget bestehen, wenn der Netzbezug 0 ist.

Bei konfiguriertem Batterie-Reserve-SOC sperrt **Netzüberschuss** die Überschussverbraucher an oder unter der Grenze. **PV-Budget** behält den bisherigen Wechsel auf Normal bei. Der Regler steuert keine Batterie direkt. Um Batterieentladung zuverlässig aus dem Überschussbudget herauszurechnen, muss deren Leistungssensor zugeordnet sein. Ohne diesen Sensor kann er die Energiequelle einer Einspeisung nicht erkennen.

## Eingehende Werte skalieren

Für Netzleistung, PV-Leistung, Batterieleistung, Batterie-SOC, Verbraucher-Istleistung und numerische Bedarfsleistung sind unabhängig wählbar:

`0,001 · 0,01 · 0,1 · 1 · 10 · 100 · 1000`

Reihenfolge: **Rohwert × Faktor → Umrechnung anhand der Sensor-Einheit → Vorzeichenkorrektur**. Ein Leistungssensor braucht eine gültige Leistungseinheit, etwa W oder kW; der Faktor ersetzt diese Einheit nicht.

Beispiele:

- `5000 W × 0,1 = 500 W = 0,5 kW` intern.
- `5 kW × 1 = 5 kW` intern.
- SOC-Rohwert `750 % × 0,1 = 75 %`; bei Anteil-Skalierung wird danach noch von 0…1 auf Prozent umgerechnet.

Boolesche Anforderungs-/Verfügbarkeitszustände werden nicht skaliert. Faktor 1 ist der Standard und erhält bestehende Messwerte.

## Ausgang in Ampere oder Watt

Beim Verbraucher **Einheit des Leistungsausgangs** auf **A** oder **W** stellen; kW und MW bleiben verfügbar. **Auto** liest die Einheit aus der Entity, bei EVSE bleibt A der Standard.

Für A-Ausgänge Phasenanzahl und Phasenspannung konfigurieren:

`I = P[kW] × 1000 / (Phasen × Spannung[V])`

Bei drei Phasen und 230 V entsprechen 6,9 kW einem Sollwert von 10 A. Die Umrechnung nimmt Leistungsfaktor 1 und eine gleichmäßige Phasenverteilung an. Für eine Wallbox zusätzlich Typ **EVSE** und die technischen Stromgrenzen passend zur Mindest-/Maximalleistung einstellen. Alternativ kann dieselbe Wallbox bei einem W-Sollwerteingang W erhalten.

## Eigene AN-/AUS-Befehle

Für eine Schaltlast oder eine separate Freigabe sind folgende Entity-Typen möglich:

| Ausgang | Ausführung |
| --- | --- |
| `switch`, `input_boolean` | Native Aktionen `turn_on` / `turn_off`. |
| `number`, `input_number` | `set_value` mit den konfigurierten numerischen Befehlen. |
| `select`, `input_select` | `select_option` mit exakt den konfigurierten Optionstexten. |

Beispiel für einen Gerätemodus:

```yaml
load_type: switch
output_entity: number.geraet_betriebsart
command_on: "12"
command_off: "14"
max_kw: 2.0
```

Das Beispiel zeigt die gespeicherten Felder; die Einrichtung erfolgt über die Oberfläche. Bei einem modulierbaren Gerät den Leistungs-Sollwert als Hauptausgang und beispielsweise `number.geraet_betriebsart` als **separate Freigabe** wählen. Dann wird vor dem Einschalten der Sollwert geschrieben; beim Ausschalten zuerst die Freigabe mit `14` zurückgenommen.

AN und AUS müssen verschieden und vom Gerät akzeptiert sein. Die Freigabewerte gelten für Schaltlast bzw. separate Freigabe; der sichere numerische Sollwert für den Leistungsausgang ist ein eigenes Feld. Beim Fail-Safe wird derselbe konfigurierte AUS-Befehl verwendet. MQTT-/Modbus-Register werden über ihre vorhandenen HA-Entities angebunden.

## Energieflussmonitor anpassen

Dashboard bearbeiten → Karte hinzufügen → **Energiemanager GSI**. Die Karte wird mit der Integration bereitgestellt.

Im visuellen Karteneditor lassen sich Titel, Anzeige in W/kW, PV-/Batterie-/Diagnosebereiche und die kompakte Ansicht ändern. Jeder Verbraucher kann einen Anzeigenamen und ein `mdi:`-Symbol erhalten oder ausgeblendet werden. Das Ausblenden ändert nur die Darstellung; der Verbraucher bleibt im Regler aktiv.

Die Prioritäten werden bei den Verbrauchern unter Geräte & Dienste geändert. Sie bestimmen zugleich deren Reihenfolge im Monitor. Der Monitor zeigt Istleistung, Sollleistung, Bedarf und den Ausgangswert in A/W bzw. den Schaltcode.

```yaml
type: custom:power-manager-card
title: Mein Energiefluss
power_unit: W
show_pv: true
show_battery: true
show_diagnostics: true
compact: false
loads:
  sensor.wallbox_target_power:
    name: Auto
    icon: mdi:ev-station
    hidden: false
```

Die Entity-ID im Beispiel durch den tatsächlichen Sollleistungssensor des Verbrauchers ersetzen. Sichtbarkeit und Namen ändern die Regelstrategie nicht.

## Prüfung vor dem Betrieb

Nach Start oder Reload bleibt Live-Regelung ausgeschaltet. Zuerst im Dry-Run Vorzeichen, Einheiten, Faktoren und Sollwerte kontrollieren. Anschließend einen Verbraucher gezielt testen, bevor weitere freigegeben werden.

Der Stand wurde mit Python-Tests für Regler, Skalierung und Ausgangsadapter sowie einer Browserprüfung der Karte mit Beispieldaten geprüft. Ein Test auf der konkreten Home-Assistant-Instanz mit realen Geräten steht noch aus. Software-Peakshaving ersetzt keine elektrische Absicherung und kann Verzögerungen von Messgeräten und Aktoren nicht verhindern.

Entwicklungsreferenzen: [HA Config Flows](https://contributors.home-assistant.io/core/integrations/config-flow/) und [HACS Integrationen](https://www.hacs.dev/docs/publish/integration/).
