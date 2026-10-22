const POWER_MANAGER_CARD_VERSION = "3.3.0";

class PowerManagerCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = {};
    this._entityMap = null;
    this._loadEntityIds = [];
    this._registryLoading = false;
    this._registryError = null;
    this._actionBusy = false;
    this._actionError = null;
    this._loadControls = {};
    this._draftPowers = {};
  }

  static getStubConfig() {
    return { title: "Energiefluss", power_unit: "auto", show_diagnostics: true };
  }

  static getConfigElement() {
    return document.createElement("power-manager-card-editor");
  }

  setConfig(config) {
    if (config.power_unit && !["auto", "W", "kW"].includes(config.power_unit)) {
      throw new Error("Anzeigeeinheit muss auto, W oder kW sein.");
    }
    this._config = config || {};
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._subscribeRegistry();
    if (!this._entityMap && !this._registryLoading) {
      this._loadRegistry();
    }
    this._render();
  }

  connectedCallback() { this._subscribeRegistry(); }

  disconnectedCallback() {
    this._registryUnsubscribe?.();
    this._registryUnsubscribe = null;
    this._subscriptionGeneration = (this._subscriptionGeneration || 0) + 1;
  }

  async _subscribeRegistry() {
    if (!this.isConnected || !this._hass?.connection?.subscribeEvents || this._registryUnsubscribe || this._subscribing) return;
    this._subscribing = true;
    const generation = this._subscriptionGeneration || 0;
    try {
      const unsubscribe = await this._hass.connection.subscribeEvents(() => this._loadRegistry(), "entity_registry_updated");
      if (!this.isConnected || generation !== (this._subscriptionGeneration || 0)) unsubscribe();
      else this._registryUnsubscribe = unsubscribe;
    } catch (_) {
      // Registry discovery still works; a dashboard reload can retry events.
    } finally { this._subscribing = false; }
  }

  getCardSize() {
    return 9;
  }

  async _loadRegistry() {
    if (!this._hass) {
      return;
    }
    if (this._registryLoading) { this._registryDirty = true; return; }

    this._registryLoading = true;
    this._registryError = null;

    try {
      const entries = await this._hass.callWS({ type: "config/entity_registry/list" });
      const powerManagerEntries = entries.filter(
        (entry) => entry.platform === "power_manager"
      );

      const map = {};
      const loadIds = [];
      const loadPrefixes = {};
      const manualEntities = {};

      const knownKeys = [
        "operating_mode",
        "live_control",
        "grid_power",
        "grid_measurement_age",
        "fail_safe_reason",
        "last_output_error",
        "configured_load_count",
        "pv_power",
        "battery_power",
        "battery_soc",
        "effective_grid_limit",
        "base_load",
        "house_power",
        "house_base_power",
        "peak_budget",
        "raw_surplus_budget",
        "surplus_budget",
        "available_budget",
        "unused_budget",
        "projected_grid_power",
        "grid_headroom",
        "total_requested_power",
        "total_target_power",
        "measured_controlled_power",
        "estimated_controlled_power",
        "battery_discharge",
        "active_load_count",
        "limited_load_count",
        "settling_load_count",
        "grid_measurement_healthy",
        "fail_safe_active",
        "output_healthy",
        "peak_shaving_active",
        "surplus_active",
        "hard_grid_limit_exceeded",
        "grid_limit_unachievable",
        "battery_soc_blocking_surplus"
      ];

      for (const entry of powerManagerEntries) {
        const uniqueId = entry.unique_id || "";

        const manualKey = ["manual_mode", "manual_power"].find(key => uniqueId.endsWith("_" + key));
        if (manualKey) {
          const prefix = uniqueId.slice(0, -(manualKey.length + 1));
          (manualEntities[prefix] ||= {})[manualKey] = entry.entity_id;
          continue;
        }

        const key = [...knownKeys].sort((a, b) => b.length - a.length)
          .find((key) => uniqueId.endsWith("_" + key));
        if (key) {
          map[key] = entry.entity_id;
        } else if (uniqueId.endsWith("_target_power")) {
          loadIds.push(entry.entity_id);
          loadPrefixes[entry.entity_id] = uniqueId.slice(0, -"_target_power".length);
        }
      }

      this._entityMap = map;
      this._loadEntityIds = loadIds;
      this._loadControls = Object.fromEntries(loadIds.map(id => [id, manualEntities[loadPrefixes[id]] || {}]));
    } catch (err) {
      this._registryError = String(err);
      this._entityMap = {};
      this._loadEntityIds = [];
    } finally {
      this._registryLoading = false;
      this._render();
      if (this._registryDirty) { this._registryDirty = false; this._loadRegistry(); }
    }
  }

  _state(key) {
    if (!this._hass || !this._entityMap) {
      return null;
    }
    const entityId = this._entityMap[key];
    return entityId ? this._hass.states[entityId] || null : null;
  }

  _num(key) {
    const state = this._state(key);
    if (!state || ["unknown", "unavailable", "none", ""].includes(state.state)) {
      return null;
    }
    const value = Number(state.state);
    if (!Number.isFinite(value)) return null;
    const unit = state.attributes?.unit_of_measurement;
    return unit === "W" ? value / 1000 : unit === "MW" ? value * 1000 : value;
  }

  _bool(key) {
    const state = this._state(key);
    if (!state) {
      return null;
    }
    if (state.state === "on") {
      return true;
    }
    if (state.state === "off") {
      return false;
    }
    return null;
  }

  _fmt(value, unit = "kW", digits = 1) {
    if (value === null || value === undefined || !Number.isFinite(Number(value))) {
      return "—";
    }
    if (unit === "kW" && this._config.power_unit === "W") {
      value = Number(value) * 1000;
      unit = "W";
      digits = 0;
    }
    return Number(value).toLocaleString("de-DE", {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits
    }) + (unit ? " " + unit : "");
  }

  _fmtSigned(value, unit = "kW", digits = 1) {
    if (value === null || value === undefined || !Number.isFinite(Number(value))) {
      return "—";
    }
    const number = Number(value);
    const prefix = number > 0 ? "+" : "";
    return prefix + this._fmt(number, unit, digits);
  }

  _labelMode(value) {
    return value === "surplus" ? "Überschuss" : "Normal";
  }

  _loads() {
    if (!this._hass) {
      return [];
    }

    const loads = this._loadEntityIds
      .map((entityId) => {
        const state = this._hass.states[entityId];
        if (!state) {
          return null;
        }

        const a = state.attributes || {};
        const override = (this._config.loads || {})[entityId] || {};
        if (override.hidden) return null;
        const controls = this._loadControls[entityId] || {};
        const modeState = this._hass.states[controls.manual_mode];
        const powerState = this._hass.states[controls.manual_power];
        return {
          entityId,
          name: override.name || a.load_name || a.friendly_name || entityId,
          icon: override.icon || (a.load_type === "evse" ? "mdi:ev-station" : "mdi:power-plug"),
          manualModeEntity: controls.manual_mode,
          manualPowerEntity: controls.manual_power,
          manualMode: modeState?.state || a.manual_mode || "auto",
          manualPower: this._nullableNumber(powerState?.state ?? a.manual_power_kw ?? a.max_kw),
          outputUnit: a.output_unit || "auto",
          commandValue: a.command_value,
          commandUnit: a.command_unit || "",
          commandOn: a.command_on ?? "1",
          commandOff: a.command_off ?? "0",
          safeOutput: Number(a.safe_output_value || 0),
          pauseCurrent: Number(a.pause_current_a ?? 0.01),
          phases: Number(a.phases || 3),
          voltage: Number(a.voltage_v || 230),
          type: a.load_type || "",
          priority: Number.isFinite(Number(a.priority)) ? Number(a.priority) : 999,
          requested: this._nullableNumber(a.requested_kw),
          actual: this._nullableNumber(a.actual_kw),
          target: this._nullableNumber(state.state) === null ? null : Number(state.state) * (a.unit_of_measurement === "W" ? 0.001 : a.unit_of_measurement === "MW" ? 1000 : 1),
          commanded: this._nullableNumber(a.commanded_target_kw),
          min: this._nullableNumber(a.min_kw),
          max: this._nullableNumber(a.max_kw),
          available: a.available !== false,
          peakEnabled: a.peak_shaving_enabled !== false,
          surplusEnabled: a.surplus_enabled !== false,
          outputEntity: a.output_entity || "",
          enableEntity: a.enable_entity || "",
          inputError: a.input_error || "",
          commandError: a.command_error || ""
        };
      })
      .filter(Boolean);

    loads.sort((a, b) => {
      if (a.priority !== b.priority) {
        return a.priority - b.priority;
      }
      return a.name.localeCompare(b.name, "de");
    });

    return loads;
  }

  _nullableNumber(value) {
    if (value === null || value === undefined || value === "") {
      return null;
    }
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  _loadStatus(load) {
    if (load.commandError || load.inputError) {
      return { text: "Fehler", cls: "danger" };
    }
    if (!load.available) {
      return { text: "nicht verfügbar", cls: "muted" };
    }
    if ((load.target || 0) <= 0.01) {
      if ((load.actual || 0) > 0.05 && (load.requested || 0) <= 0) return { text: "stoppt", cls: "warning" };
      if ((load.requested || 0) > 0) return { text: "wartet", cls: "warning" };
      return { text: "inaktiv", cls: "muted" };
    }
    if (
      load.requested !== null &&
      load.target !== null &&
      load.requested > load.target + 0.05
    ) {
      return { text: "begrenzt", cls: "warning" };
    }
    if (load.actual !== null && load.actual > 0.05) {
      return { text: "aktiv", cls: "success" };
    }
    return { text: "wartend", cls: "info" };
  }

  async _setMode(mode) {
    const entityId = this._entityMap && this._entityMap.operating_mode;
    if (!entityId || !this._hass || this._actionBusy) {
      return;
    }

    const live = this._bool("live_control") === true;
    if (
      live &&
      !window.confirm(
        "Die Live-Regelung ist aktiv. Betriebsart wirklich auf " +
          this._labelMode(mode) +
          " umschalten?"
      )
    ) {
      return;
    }

    this._actionBusy = true;
    this._render();

    try {
      await this._hass.callService("select", "select_option", {
        entity_id: entityId,
        option: mode
      });
      this._actionError = null;
    } catch (err) {
      this._actionError = String(err?.message || err);
    } finally {
      this._actionBusy = false;
      this._render();
    }
  }

  async _toggleLive() {
    const entityId = this._entityMap && this._entityMap.live_control;
    if (!entityId || !this._hass || this._actionBusy) {
      return;
    }

    const live = this._bool("live_control") === true;
    if (
      !live &&
      !window.confirm(
        "Live-Regelung aktivieren? Der Energiemanager GSI darf danach reale Ausgangswerte schreiben."
      )
    ) {
      return;
    }

    this._actionBusy = true;
    this._render();

    try {
      await this._hass.callService("switch", live ? "turn_off" : "turn_on", {
        entity_id: entityId
      });
      this._actionError = null;
    } catch (err) {
      this._actionError = String(err?.message || err);
    } finally {
      this._actionBusy = false;
      this._render();
    }
  }

  _icon(icon) {
    return '<ha-icon icon="' + this._esc(icon) + '"></ha-icon>';
  }

  _esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c]));
  }

  _outputLabel(load) {
    if (load.type === "switch") {
      const isSwitch = /^(switch|input_boolean)\./.test(load.outputEntity);
      return isSwitch ? ((load.target || 0) > 0 ? "AN" : "AUS")
        : this._esc((load.target || 0) > 0 ? load.commandOn : load.commandOff);
    }
    if (load.commandValue !== null && load.commandValue !== undefined) {
      return this._esc(load.commandValue) + " " + this._esc(load.commandUnit);
    }
    const state = this._hass.states[load.outputEntity];
    const unit = load.outputUnit === "auto"
      ? (load.type === "evse" ? "A" : state?.attributes?.unit_of_measurement) : load.outputUnit;
    if (!unit || load.target === null) return "—";
    const value = load.target <= 0 ? (unit === "A" && load.type === "evse" ? load.pauseCurrent : load.safeOutput)
      : unit === "A" ? load.target * 1000 / (load.phases * load.voltage)
      : unit === "W" ? load.target * 1000 : unit === "MW" ? load.target / 1000 : load.target;
    return this._fmt(value, unit, 2);
  }

  _flowValue(value) {
    if (value === null || value === undefined || !Number.isFinite(value)) return "—";
    if ((!this._config.power_unit || this._config.power_unit === "auto") && Math.abs(value) < 1) {
      return this._fmt(value * 1000, "W", 0);
    }
    return this._fmt(value, "kW", 2);
  }

  _radialFlow(loads) {
    const battery = this._num("battery_power");
    const grid = this._num("grid_power");
    const soc = this._num("battery_soc");
    const baseState = this._state("house_base_power");
    const nodes = [];
    if (this._config.show_pv !== false) nodes.push({ name: "PV", value: this._num("pv_power"), icon: "mdi:solar-power", color: "#84c85b", incoming: true });
    if (this._config.show_battery !== false) nodes.push({ name: "Speicher", value: battery, icon: "mdi:battery-high", color: "#84c85b", incoming: battery > 0, detail: soc === null ? "" : this._fmt(soc, "%", 0), direction: battery === null ? "" : battery < -0.002 ? "lädt" : battery > 0.002 ? "entlädt" : "Ruhe" });
    nodes.push({ name: "Netz", value: grid, icon: "mdi:transmission-tower", color: "#f6bd64", incoming: grid > 0, direction: grid === null ? "" : grid < -0.002 ? "Einspeisung" : grid > 0.002 ? "Bezug" : "ausgeglichen" });
    for (const load of [...loads].reverse()) {
      const value = load.actual ?? load.commanded;
      nodes.push({ name: load.name, value, icon: load.icon, color: "#f6bd64", incoming: false,
        detail: load.actual === null && value !== null ? "geschätzt" : "", entityId: load.entityId });
    }
    nodes.push({ name: "Grundverbrauch", value: this._num("house_base_power"), icon: "mdi:home-lightning-bolt", color: "#f6bd64", incoming: false,
      detail: baseState?.attributes?.estimated ? "geschätzt" : "Zähler − Verbraucher" });
    const radius = Math.max(210, nodes.length * 25);
    const center = radius + 120;
    const size = center * 2;
    const count = nodes.length;
    const edges = [], circles = [];
    nodes.forEach((node, index) => {
      const angle = (-90 + index * 360 / count) * Math.PI / 180;
      const x = center + Math.cos(angle) * radius;
      const y = center + Math.sin(angle) * radius;
      const endX = center + Math.cos(angle) * (radius - 45);
      const endY = center + Math.sin(angle) * (radius - 45);
      const active = node.value !== null && Math.abs(node.value) >= 0.002;
      const path = node.incoming ? `M${endX},${endY} L${center},${center}` : `M${center},${center} L${endX},${endY}`;
      edges.push(`<path d="M${center},${center} L${endX},${endY}" class="flow-line"/>`);
      if (active) {
        const duration = 2.5 + index * 0.17;
        const phase = (Date.now() / 1000) % duration;
        edges.push(`<circle r="4.5" fill="${node.color}" class="flow-dot"><animateMotion begin="-${phase}s" dur="${duration}s" repeatCount="indefinite" path="${path}"/></circle>`);
      }
      const top = Math.sin(angle) < -0.35;
      const labelY = top ? y - 92 : y + 69;
      circles.push(`<g class="flow-node ${active ? "active" : "idle"}" ${node.entityId ? `data-node="${this._esc(node.entityId)}"` : ""}>
        <title>${this._esc(node.name)}: ${this._flowValue(node.value)}${node.direction ? ", " + node.direction : ""}</title>
        <circle cx="${x}" cy="${y}" r="44" fill="#0d0e10" stroke="${node.value === null ? "#666" : node.color}" stroke-width="3.5"/>
        <foreignObject x="${x - 22}" y="${y - 22}" width="44" height="44"><div xmlns="http://www.w3.org/1999/xhtml" class="flow-icon">${this._icon(node.icon)}</div></foreignObject>
        <text x="${x}" y="${labelY}" class="flow-power">${this._flowValue(node.value === null ? null : Math.abs(node.value))}</text>
        <text x="${x}" y="${labelY + 23}" class="flow-name">${this._esc(node.name)}</text>
        <text x="${x}" y="${labelY + 42}" class="flow-detail">${this._esc([node.detail, node.direction].filter(Boolean).join(" · "))}</text>
      </g>`);
    });
    return `<svg class="energy-flow" viewBox="0 0 ${size} ${size + 12}" role="img" aria-label="Energiefluss zwischen PV, Speicher, Netz, Grundverbrauch und Verbrauchern">
      ${edges.join("")}<circle cx="${center}" cy="${center}" r="7" fill="#929497"/>${circles.join("")}</svg>`;
  }

  _consumerControl(load) {
    const status = this._loadStatus(load);
    const editable = Boolean(load.manualModeEntity && load.manualPowerEntity);
    const value = this._draftPowers[load.entityId] ?? load.manualPower ?? load.max ?? 0;
    const disabled = !editable || this._actionBusy ? "disabled" : "";
    const modes = [["auto", "AUTO"], ["manual", "EIN"], ["off", "AUS"]].map(([mode, text]) =>
      `<button data-manual="${mode}" data-load="${this._esc(load.entityId)}" class="mode-${mode} ${load.manualMode === mode ? "selected" : ""}" aria-label="${text} ${this._esc(load.name)}" aria-pressed="${load.manualMode === mode}" ${disabled}>${text}</button>`).join("");
    return `<section class="consumer-control">
      <div class="consumer-heading"><div>${this._icon(load.icon)}<strong>${this._esc(load.name)}</strong></div><span class="priority">P${load.priority}</span></div>
      <div class="consumer-readings"><span>Ist <b>${this._flowValue(load.actual)}</b></span><span>Soll <b>${this._flowValue(load.target)}</b></span><span class="status ${status.cls}">${status.text}</span></div>
      <div class="manual-buttons">${modes}</div>
      <div class="power-setting"><label>Sollwert <span><input type="number" inputmode="decimal" min="0" max="${load.max || 0}" step="0.01" value="${this._esc(value)}" data-power="${this._esc(load.entityId)}" aria-label="kW Sollwert ${this._esc(load.name)}" ${disabled}/> kW</span></label><button class="apply" data-apply="${this._esc(load.entityId)}" aria-label="Sollwert übernehmen ${this._esc(load.name)}" ${disabled}>Setzen</button></div>
      <div class="device-output">${editable ? "Ausgang: " + this._outputLabel(load) + " · " + (load.manualMode === "auto" ? "Automatik" : load.manualMode === "off" ? "Manuell AUS" : "Manuell EIN") : "Integration ab Version 3.3 erforderlich"}</div>
      ${(load.min || 0) > 0 ? `<div class="device-output">Technisch: 0 oder ${this._fmt(load.min, "kW", 2)} bis ${this._fmt(load.max, "kW", 2)}</div>` : ""}
      ${load.inputError || load.commandError ? `<div class="error">${this._esc(load.inputError || load.commandError)}</div>` : ""}
    </section>`;
  }

  async _setManualMode(entityId, mode) {
    const load = this._loads().find(load => load.entityId === entityId);
    if (!load?.manualModeEntity || this._actionBusy) return;
    this._actionBusy = true;
    this._actionError = null;
    this._render();
    try {
      if (mode === "manual" && Object.hasOwn(this._draftPowers, entityId)) {
        await this._writeManualPower(load);
      }
      await this._hass.callService("select", "select_option", { entity_id: load.manualModeEntity, option: mode });
    } catch (err) {
      this._actionError = String(err?.message || err);
    } finally {
      this._actionBusy = false;
      this._render();
    }
  }

  async _writeManualPower(load) {
    const raw = this._draftPowers[load.entityId] ?? load.manualPower;
    const value = typeof raw === "string" && !raw.trim() ? NaN : Number(String(raw).replace(",", "."));
    if (!Number.isFinite(value) || value < 0 || value > load.max) throw new Error(`Sollwert muss zwischen 0 und ${load.max} kW liegen.`);
    if (value > 0 && value < load.min - 0.000001) throw new Error(`Mindestleistung für ${load.name}: ${load.min} kW. Alternativ 0 wählen.`);
    await this._hass.callService("number", "set_value", { entity_id: load.manualPowerEntity, value });
    delete this._draftPowers[load.entityId];
  }

  async _applyManualPower(entityId) {
    const load = this._loads().find(load => load.entityId === entityId);
    if (!load?.manualPowerEntity || this._actionBusy) return;
    this._actionBusy = true;
    this._actionError = null;
    this._render();
    try { await this._writeManualPower(load); }
    catch (err) { this._actionError = String(err?.message || err); }
    finally { this._actionBusy = false; this._render(); }
  }

  _render() {
    if (!this.shadowRoot) return;
    const style = `
      :host{display:block;color:#ededf0;font-family:var(--paper-font-body1_-_font-family,Roboto,Arial,sans-serif);min-width:0}
      *{box-sizing:border-box}ha-card{display:block;background:#050506;border-radius:var(--ha-card-border-radius,20px);overflow:hidden;container-type:inline-size;border:1px solid #252629}
      .wrap{padding:22px}.header{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:17px}.header h2{margin:0;font-size:23px;letter-spacing:-.4px;overflow-wrap:anywhere}.subtitle{font-size:11px;color:#8a8b91;margin-top:6px}.badge{padding:6px 10px;border-radius:20px;font-size:11px;white-space:nowrap;background:#19231a;color:#9cda7f}.badge.danger{background:#381d1d;color:#ffa39a}.badge.dry{background:#29241b;color:#efc47c}
      .toolbar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding-bottom:18px;border-bottom:1px solid #242528}.toolbar .spacer{flex:1}.summary{font-size:12px;color:#999ba2}.summary b{color:#eee;margin-left:5px}.toolbar button{font-size:12px}
      button{font:inherit;color:#a9abb0;background:#17181b;border:1px solid #333438;border-radius:8px;padding:8px 11px;cursor:pointer;transition:background .15s}button:hover{background:#282a2e}button.selected,button.active{color:#f6bd64;background:#30281c;border-color:#725c39}button:disabled{opacity:.4;cursor:default}button:focus-visible,input:focus-visible{outline:2px solid #84c85b;outline-offset:2px}
      .main-grid{display:grid;grid-template-columns:minmax(0,1fr);gap:18px}.diagram{min-width:0;padding-top:12px}.energy-flow{display:block;width:100%;max-width:760px;margin:0 auto;overflow:visible}.flow-line{fill:none;stroke:#74767a;stroke-width:2.2}.flow-node.idle circle{stroke-opacity:.55}.flow-node.idle .flow-power{fill:#b3b3b9}.flow-power{font-size:20px;font-weight:700;fill:#f7f7fa;text-anchor:middle}.flow-name{font-size:18px;fill:#96969e;text-anchor:middle}.flow-detail{font-size:11px;fill:#757780;text-anchor:middle}.flow-icon{display:flex;align-items:center;justify-content:center;height:44px;width:44px;color:#eeedf2}.flow-icon ha-icon{--mdc-icon-size:38px}.hub-status{text-align:center;color:#8c8e95;font-size:11px;margin-top:-4px}
      .sidebar{border:1px solid #292b2f;border-radius:13px;background:#0f1012;padding:15px;min-width:0}.sidebar-header{display:flex;align-items:baseline;justify-content:space-between;gap:10px;margin-bottom:5px}.sidebar h3{font-size:15px;margin:0}.sidebar-header span{font-size:10px;color:#777b83}.consumer-control{padding:16px 0;border-bottom:1px solid #2a2b2f}.consumer-control:last-of-type{border:0}.consumer-heading,.consumer-heading>div{display:flex;align-items:center;gap:8px}.consumer-heading{justify-content:space-between}.consumer-heading strong{font-size:13px;overflow-wrap:anywhere}.consumer-heading ha-icon{--mdc-icon-size:19px;color:#babcc2}.priority{font-size:10px;color:#888b93}.consumer-readings{display:flex;flex-wrap:wrap;gap:7px 12px;font-size:10px;margin:10px 0;color:#8c8f98}.consumer-readings b{color:#dfe0e4;margin-left:4px;font-weight:500}.status{margin-left:auto;color:#8fd26c}.status.warning{color:#f6bd64}.status.danger{color:#ff9c92}.status.muted{color:#7a7d85}.manual-buttons{display:grid;grid-template-columns:1.2fr 1fr 1fr;gap:5px}.manual-buttons button{font-size:10px;font-weight:700;padding:7px}.mode-off.selected{color:#ffaca2;background:#311d1c;border-color:#7a4942}.mode-manual.selected{color:#a4db89;background:#1d2a1b;border-color:#517d43}.power-setting{display:flex;gap:7px;margin-top:10px;align-items:center}.power-setting label{font-size:11px;color:#999ca5;display:flex;justify-content:space-between;align-items:center;flex:1;gap:8px}.power-setting label span{white-space:nowrap}input{font:inherit;font-size:13px;color:#f2f2f5;background:#08090b;border:1px solid #383b42;border-radius:6px;padding:7px 6px;width:78px;text-align:right}input:disabled{opacity:.5}.apply{font-size:10px;padding:8px}.device-output{font-size:9px;color:#777c85;margin-top:8px;line-height:1.5;overflow-wrap:anywhere}.sidebar-note{font-size:10px;color:#858992;line-height:1.55;margin:12px 0 0}.error{color:#ffaba1;font-size:12px;line-height:1.5;background:#2e1818;border:1px solid #5d3330;border-radius:8px;padding:10px;margin:12px 0;overflow-wrap:anywhere}
      .balance-strip{border-top:1px solid #242528;margin-top:16px;padding-top:14px;display:flex;flex-wrap:wrap;gap:9px 24px;font-size:11px;color:#7f838c}.balance-strip strong{color:#dbdde2;font-weight:500}.diagnostics{font-size:10px;color:#747985;margin-top:13px;line-height:1.6}.empty{padding:36px 20px;text-align:center;color:#92959f;font-size:13px}.compact .diagnostics{display:none}
      @container (max-width:420px){.wrap{padding:12px}.header{align-items:flex-start}.header h2{font-size:20px}.summary{font-size:10px}.flow-power{font-size:23px}.flow-name{font-size:20px}.flow-detail{font-size:13px}.sidebar{padding:12px}.header .badge{font-size:9px;padding:5px 7px}}
      @container (min-width:560px){.wrap{padding:22px}.sidebar{max-width:none}}
      @container (min-width:820px){.main-grid{grid-template-columns:minmax(0,1fr) 280px;gap:24px}.sidebar{margin-top:20px}.wrap{padding:24px}}
      @media(prefers-reduced-motion:reduce){.flow-dot{display:none}button{transition:none}}
    `;
    if (!this._hass || this._registryLoading || !this._entityMap) {
      this.shadowRoot.innerHTML = `<style>${style}</style><ha-card><div class="empty">${this._registryError ? this._esc(this._registryError) : "Energiefluss wird geladen …"}</div></ha-card>`;
      return;
    }
    const focusId = this.shadowRoot.activeElement?.dataset?.power;
    const loads = this._loads();
    const live = this._bool("live_control") === true;
    const failSafe = this._bool("fail_safe_active") === true;
    const healthy = this._bool("grid_measurement_healthy") === true;
    const mode = this._state("operating_mode")?.state || "normal";
    const balance = this._state("house_base_power");
    const balanceError = balance?.attributes?.balance_error;
    const modeButtons = ["normal", "surplus"].map(option => `<button data-mode="${option}" class="${option === mode ? "selected" : ""}" ${this._actionBusy ? "disabled" : ""}>${option === "normal" ? "Peakshaving" : "Überschuss"}</button>`).join("");
    this.shadowRoot.innerHTML = `<style>${style}</style><ha-card><div class="wrap ${this._config.compact ? "compact" : ""}">
      <div class="header"><div><h2>${this._esc(this._config.title || "Energiefluss")}</h2><div class="subtitle">ENERGIEMANAGER GSI · ${POWER_MANAGER_CARD_VERSION}</div></div><span class="badge ${failSafe ? "danger" : !live ? "dry" : ""}">${failSafe ? "Fail-Safe" : !healthy ? "Messwerte fehlen" : live ? "Live-Regelung" : "Dry-Run"}</span></div>
      <div class="toolbar">${modeButtons}<button data-live="true" ${this._actionBusy ? "disabled" : ""}>${live ? "Live ausschalten" : "Live aktivieren"}</button><span class="spacer"></span><span class="summary">Netzlimit <b>${this._flowValue(this._num("effective_grid_limit"))}</b></span></div>
      ${this._actionError ? `<div class="error" role="alert">${this._esc(this._actionError)}</div>` : ""}
      <div class="main-grid"><div class="diagram">${this._radialFlow(loads)}<div class="hub-status">Messwerte der Verbraucher · Punkte zeigen die Flussrichtung</div></div>
      <aside class="sidebar"><div class="sidebar-header"><h3>Verbraucher regeln</h3><span>Priorität 1 zuerst</span></div>${loads.length ? loads.map(load => this._consumerControl(load)).join("") : '<div class="empty">Verbraucher unter Geräte & Dienste hinzufügen.</div>'}
        <p class="sidebar-note">EIN nutzt den eingestellten kW-Wert. AUTO übernimmt den konfigurierten Bedarf. Netzlimit, technische Grenzen und das gewählte Überschussbudget bleiben wirksam.${!live ? " Im Dry-Run werden keine Geräte geschaltet." : ""}</p></aside></div>
      <div class="balance-strip"><span>Haus gesamt <strong>${this._flowValue(this._num("house_power"))}</strong></span><span>Grundverbrauch <strong>${this._flowValue(this._num("house_base_power"))}</strong>${balance?.attributes?.estimated ? " (geschätzt)" : ""}</span><span>Grundverbrauch = ${balance?.attributes?.source === "house_meter" ? "Hauszähler" : "Netz + PV + Speicher"} − Verbraucher</span></div>
      ${balanceError ? `<div class="error">${this._esc(balanceError)}</div>` : ""}
      ${this._config.show_diagnostics === false ? "" : `<div class="diagnostics">Regelbudget: ${this._flowValue(this._num("available_budget"))} · Netzwert: ${this._fmt(this._num("grid_measurement_age"), "s", 1)} alt · Ausgangspfad: ${this._bool("output_healthy") === true ? "OK" : "unbekannt / gestört"}${failSafe ? " · " + this._esc(this._state("fail_safe_reason")?.state || "") : ""}</div>`}
    </div></ha-card>`;
    for (const button of this.shadowRoot.querySelectorAll("[data-mode]")) button.addEventListener("click", () => this._setMode(button.dataset.mode));
    this.shadowRoot.querySelector("[data-live]")?.addEventListener("click", () => this._toggleLive());
    for (const input of this.shadowRoot.querySelectorAll("[data-power]")) {
      input.addEventListener("input", () => { this._draftPowers[input.dataset.power] = input.value; });
      input.addEventListener("keydown", event => { if (event.key === "Enter") this._applyManualPower(input.dataset.power); });
      if (focusId === input.dataset.power && !input.disabled) input.focus();
    }
    for (const button of this.shadowRoot.querySelectorAll("[data-manual]")) button.addEventListener("click", () => this._setManualMode(button.dataset.load, button.dataset.manual));
    for (const button of this.shadowRoot.querySelectorAll("[data-apply]")) button.addEventListener("click", () => this._applyManualPower(button.dataset.apply));
  }
}

class PowerManagerCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
  }

  setConfig(config) { this._config = { ...config }; if (!this.shadowRoot.activeElement) this._render(); }
  set hass(hass) {
    this._hass = hass;
    const ids = Object.values(hass?.states || {}).filter(s => s.attributes?.load_name && s.attributes?.load_type).map(s => s.entity_id).join();
    if (ids !== this._loadIds) { this._loadIds = ids; this._render(); }
  }

  _render() {
    const root = this.shadowRoot;
    root.replaceChildren();
    const style = document.createElement("style");
    style.textContent = ":host{display:block;font:14px var(--paper-font-body1_-_font-family,Arial,sans-serif);color:var(--primary-text-color)}label{display:flex;justify-content:space-between;align-items:center;gap:12px;margin:12px 0}input,select{font:inherit;box-sizing:border-box;max-width:65%;padding:8px;border:1px solid var(--divider-color,#aaa);border-radius:6px;background:var(--card-background-color,#fff);color:inherit}h3{margin:22px 0 8px}small{color:var(--secondary-text-color)}fieldset{border:1px solid var(--divider-color,#aaa);border-radius:8px;margin:12px 0;padding:6px 12px}";
    root.append(style);
    const field = (parent, label, key, type, value, options, loadId) => {
      const row = document.createElement("label");
      const text = document.createElement("span");
      text.textContent = label;
      const input = document.createElement(options ? "select" : "input");
      if (options) {
        for (const option of options) {
          const el = document.createElement("option");
          el.value = el.textContent = option;
          input.append(el);
        }
      } else { input.type = type; }
      if (type === "checkbox") input.checked = Boolean(value);
      else input.value = value ?? "";
      input.addEventListener(type === "checkbox" || options ? "change" : "input", () => {
        const next = type === "checkbox" ? input.checked : input.value;
        if (loadId) {
          this._config = { ...this._config, loads: { ...this._config.loads,
            [loadId]: { ...(this._config.loads || {})[loadId], [key]: next } } };
        } else { this._config = { ...this._config, [key]: next }; }
        this.dispatchEvent(new CustomEvent("config-changed", {
          detail: { config: this._config }, bubbles: true, composed: true
        }));
      });
      row.append(text, input);
      parent.append(row);
    };
    field(root, "Titel", "title", "text", this._config.title || "Energiemanager GSI");
    field(root, "Anzeigeeinheit", "power_unit", "text", this._config.power_unit || "auto", ["auto", "kW", "W"]);
    for (const [key, label] of [["show_pv", "PV anzeigen"], ["show_battery", "Batterie anzeigen"], ["show_diagnostics", "Diagnose anzeigen"], ["compact", "Kompakte Darstellung"]]) {
      field(root, label, key, "checkbox", this._config[key] ?? key !== "compact");
    }
    const note = document.createElement("small");
    note.textContent = "Diese Einstellungen ändern die Darstellung. Priorität, Leistung und Gerätebefehle stellst du unter Geräte & Dienste → Energiemanager GSI beim Verbraucher ein.";
    root.append(note);
    const states = Object.values(this._hass?.states || {}).filter(s => s.attributes?.load_name && s.attributes?.load_type);
    for (const state of states) {
      const box = document.createElement("fieldset");
      const legend = document.createElement("legend");
      legend.textContent = state.attributes.load_name;
      box.append(legend);
      const overrides = (this._config.loads || {})[state.entity_id] || {};
      field(box, "Anzeigename", "name", "text", overrides.name || state.attributes.load_name, null, state.entity_id);
      field(box, "Symbol (mdi:…)", "icon", "text", overrides.icon || "mdi:power-plug", null, state.entity_id);
      field(box, "Ausblenden", "hidden", "checkbox", overrides.hidden || false, null, state.entity_id);
      root.append(box);
    }
  }
}

if (!customElements.get("power-manager-card-editor")) {
  customElements.define("power-manager-card-editor", PowerManagerCardEditor);
}

if (!customElements.get("power-manager-card")) {
  customElements.define("power-manager-card", PowerManagerCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "power-manager-card")) {
  window.customCards.push({
    type: "power-manager-card",
    name: "Energiemanager GSI",
    description:
      "Energiefluss, Ist-/Sollwerte, Betriebsart, Live-Regelung und Diagnose für die Energiemanager GSI-Integration.",
    preview: true,
    documentationURL: "https://github.com/luekenlenny0/energiemanager-gsi"
  });
}

console.info(
  "%c POWER-MANAGER-CARD %c v" + POWER_MANAGER_CARD_VERSION,
  "color: white; background: #03a9f4; font-weight: 700; padding: 2px 5px;",
  "color: #03a9f4; font-weight: 700;"
);
