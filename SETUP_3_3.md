# Power Manager 3.3 – Energiefluss und Handsteuerung

Die neue Karte orientiert sich an einer Kreisgrafik: schwarzer Hintergrund, grüne Ringe für PV und Speicher, gelbe Ringe für Netz und Verbraucher. Animierte Punkte zeigen die Leistungsrichtung. Die Kreise zeigen **Istwerte**, die Seitenleiste zusätzlich die **berechneten Sollwerte**.

## Update

`custom_components/power_manager` aus dem ZIP nach `/config/custom_components/power_manager` kopieren und die bisherige Komponente vollständig ersetzen. Vorherige Konfiguration sichern, dann Home Assistant neu starten. Voraussetzung bleibt Home Assistant Core ab 2026.9.

Im Dashboard die Karte `custom:power-manager-card` verwenden und nach dem Update die Browserseite vollständig neu laden. Der visuelle Karteneditor bleibt verfügbar. Für die Seitenleiste neben der Grafik eine ausreichend breite Karte wählen; auf schmalen Karten stehen die Bedienelemente unter der Grafik.

HACS zeigt diese Version erst nach Übernahme des neuen Stands in den Hauptbranch bzw. nach einem passenden Release. Das ZIP und der Entwicklungsbranch dienen bis dahin zur manuellen Testinstallation.

## Testverbraucher

Die Vorschau enthält vier simulierte Verbraucher. In der echten Integration weiterhin eigene Sensor-/Stell-Entities frei zuordnen; die Vorschau erzeugt keine Geräte auf deiner Home-Assistant-Instanz.

| Verbraucher | Priorität | Beispiel-Typ | Technische Grenze | Beispiel-Anforderung |
| --- | --- | --- | --- | --- |
| Wärmepumpe | 1 | modulierend, W | 0,5–5 kW | 2 kW |
| Wallbox 1 | 2 | EVSE, A | 1,38–7,36 kW | 2,2 kW |
| Wallbox 2 | 3 | EVSE, A | 1,38–7,36 kW | manuell 3,68 kW vorbereitet |
| Heizstab | 4 | modulierend, W | 0–3 kW | manuell 3 kW vorbereitet |

Die Wallbox-Beispiele verwenden **eine Phase, 230 V und 6–32 A**. An reale Geräte ihre tatsächlichen Phasen-, Strom- und Leistungsgrenzen anpassen. Ein reiner Ein/Aus-Heizstab wird als Schaltlast eingerichtet; dann sind nur 0 oder seine volle Nennleistung möglich.

## Handsteuerung in der Seitenleiste

- **AUTO:** Bedarf aus der konfigurierten Bedarfs-Entity bzw. Standardanforderung verwenden.
- **EIN:** Den manuellen kW-Wert als Bedarf an den Regler geben.
- **AUS:** Bedarf auf 0 setzen. Die konfigurierte AUS-Aktion bzw. der sichere Ausgangswert wird bei aktiver Live-Regelung gesendet.
- **Setzen:** Den eingegebenen manuellen kW-Wert übernehmen. In EIN wirkt die Änderung sofort auf die nächste Berechnung; in AUTO/AUS wird der Wert für später vorbereitet. Beim Klick auf EIN wird ein noch nicht übernommener Eingabewert zuerst gespeichert.

EIN garantiert keine bestimmte Istleistung. Priorität, Geräteverfügbarkeit, technische Mindestleistung, Mindest-Auszeit, Netzlimit und das gewählte Überschussbudget gelten weiterhin. Beispielsweise bleibt ein manueller Verbraucher im Überschussmodus ohne verfügbaren Überschuss aus. Im Peakshaving-Modus kann die Anforderung innerhalb von PMAX auch Netzstrom nutzen.

Nach Neustart/Reload stehen die Verbraucher auf AUTO, und Live-Regelung bleibt AUS. Die Handsteuerung schreibt erst nach expliziter Live-Freigabe auf Geräte. Die Befehle 12/14 und die A-/W-Umrechnung aus V3.2 bleiben wirksam.

Je Verbraucher werden eine **number-Entity für den manuellen kW-Sollwert** und eine **select-Entity mit `auto`, `manual`, `off`** erstellt. Damit ist dieselbe Bedienung auch über native HA-Aktionen oder eigene Automationen möglich. Die Karte findet diese Entities über die Registry; Umbenennen der Entity-ID ist möglich.

## Grundverbrauch mit deinem Netzbezug-/Einspeisezähler

Den Netzleistungssensor wie bisher zuordnen. Das neue optionale Feld **Hausverbrauchszähler leer lassen**, weil dein Zähler Netzbezug/Einspeisung misst.

Vorzeichen:

- Netz: Bezug positiv, Einspeisung negativ.
- PV: Erzeugung positiv.
- Speicher: Entladung positiv, Ladung negativ.

Berechnung:

```text
Hausverbrauch = Netzleistung + PV-Leistung + Speicherleistung
Grundverbrauch = Hausverbrauch − Summe aller Verbraucher-Istleistungen
```

Beispiel aus der Vorschau:

```text
Netz              +0,002 kW
PV                +7,500 kW
Speicher lädt     −2,760 kW
Haus gesamt        4,742 kW
Wärmepumpe        −2,000 kW
Wallbox 1         −2,200 kW
Wallbox 2          0,000 kW
Heizstab           0,000 kW
Grundverbrauch     0,542 kW = 542 W
```

PV- und Speichersensor zuordnen, wenn diese Energieflüsse in der Anlage vorhanden sind. Ohne ihre Messwerte lässt sich aus einem Netzzähler allein kein vollständiger Hausverbrauch ermitteln. Die bisherigen Skalierungsfaktoren und Vorzeichenkorrekturen gelten vor der Bilanzbildung.

Für genaue Werte braucht jeder geregelte Verbraucher einen eigenen Istleistungssensor. Fehlt einer, wird der Grundverbrauch als **geschätzt** gekennzeichnet und für diesen Verbraucher der vorherige physische Sollbefehl verwendet, soweit vorhanden. Ein Dry-Run-Sollwert zählt nicht als tatsächlicher Verbrauch.

Ist die Verbrauchersumme größer als der berechnete Hausverbrauch, zeigt die Karte eine Bilanzmeldung; negative Grundverbrauchswerte werden für die Anzeige auf 0 begrenzt. Der Rohwert bleibt am Grundverbrauchssensor als Diagnoseattribut erhalten. Bei fehlenden/ungültigen Messwerten bleibt die Bilanz unbekannt. Die interne netzbezogene Basislast des Peakshaving-Reglers ist ein eigener Diagnosewert und kann bei Einspeisung negativ sein.

## Darstellung

```yaml
type: custom:power-manager-card
title: Energiefluss
power_unit: auto
show_pv: true
show_battery: true
show_diagnostics: true
```

`auto` zeigt kleine Leistungen in W und größere in kW. Alternativ lassen sich W oder kW fest vorgeben. Titel, Symbole, Verbrauchernamen und Sichtbarkeit werden im Karteneditor geändert. Das Ausblenden eines Verbrauchers betrifft nur die Darstellung; er bleibt im Regler und in der Grundverbrauchsberechnung enthalten.

Die neue Steuerung und Bilanzbildung sind automatisiert mit Test-Doubles für HA-Zustände und Aktionen geprüft; die Karte ist zusätzlich im Browser mit den vier Beispielen geprüft. Ein Test mit realen Geräten auf deiner Home-Assistant-Instanz steht noch aus.

Ergänzende Referenzen: [HA Number-Entities](https://contributors.home-assistant.io/core/entities/number/) und [Config-Subentries](https://contributors.home-assistant.io/core/integrations/subentries/). Für Skalierung und Gerätebefehle siehe [V3.2-Anleitung](SETUP_3_2.md).
