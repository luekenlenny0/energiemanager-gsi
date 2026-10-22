# HACS-Custom-Repository vorbereiten

Dieses Projekt ist so strukturiert, dass es als **HACS Custom Repository** verwendet werden kann.

## 1. GitHub-Repository anlegen

Erstelle auf GitHub ein **öffentliches** Repository, empfohlen mit dem Namen:

```text
power-manager
```

Repository-Beschreibung, zum Beispiel:

```text
Central peak-shaving and PV-surplus energy manager for Home Assistant.
```

Empfohlene GitHub-Topics:

```text
home-assistant
hacs
energy-management
peak-shaving
pv-surplus
ems
```

Issues sollten aktiviert sein.

## 2. Repository-Metadaten einsetzen

Im Projektordner ausführen:

```powershell
python .\prepare_hacs_repo.py luekenlenny0 energiemanager-gsi
```

Das Skript ersetzt die Platzhalter in `manifest.json` und der Dokumentation und prüft danach, dass keine Platzhalter übrig sind.

## 3. Lokal testen

```powershell
pytest -v
python -m json.tool .\custom_components\power_manager\manifest.json > $null
python -m json.tool .\hacs.json > $null
```

## 4. Git-Repository veröffentlichen

```powershell
git init
git branch -M main
git add .
git commit -m "Release Energiemanager GSI v3.0.0"
git remote add origin https://github.com/luekenlenny0/energiemanager-gsi.git
git push -u origin main
```

Wenn dein bestehender Projektordner bereits ein Git-Repository ist, **nicht erneut `git init` ausführen**. Stattdessen nur den Remote prüfen bzw. setzen und pushen.

## 5. GitHub Actions prüfen

Unter **Actions** sollten die enthaltenen Prüfungen laufen:

- HACS validation
- Hassfest

Für ein Custom Repository ist ein GitHub Release nicht zwingend erforderlich. Ohne Releases installiert HACS den Stand des Default-Branches. Für saubere Versionierung ist später ein Release `v3.0.0` empfehlenswert.

## 6. Bei einem Freund in HACS hinzufügen

In Home Assistant / HACS:

```text
HACS
→ ⋮
→ Custom repositories
→ Repository: https://github.com/luekenlenny0/energiemanager-gsi
→ Type: Integration
→ Add
```

Danach **Energiemanager GSI** in HACS installieren, Home Assistant neu starten und anschließend über **Einstellungen → Geräte & Dienste** hinzufügen.

## Hinweis zu Home Assistant Brands

Für eine spätere Aufnahme als reguläres HACS-Standard-Repository gelten zusätzliche Publisher-Anforderungen, unter anderem Home Assistant Brands. Für den ersten privaten/öffentlichen Test als Custom Repository konzentrieren wir uns zunächst auf die Repository-Struktur, das Manifest und die HACS-/Hassfest-Validierung.
