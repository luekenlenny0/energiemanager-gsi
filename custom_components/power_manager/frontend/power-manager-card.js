const POWER_MANAGER_CARD_VERSION = "3.1.0";

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
  }

  static getStubConfig() {
    return {};
  }

  setConfig(config) {
    this._config = config || {};
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._entityMap && !this._registryLoading) {
      this._loadRegistry();
    }
    this._render();
  }

  getCardSize() {
    return 9;
  }

  async _loadRegistry() {
    if (!this._hass) {
      return;
    }

    this._registryLoading = true;
    this._registryError = null;

    try {
      const entries = await this._hass.callWS({ type: "config/entity_registry/list" });
      const powerManagerEntries = entries.filter(
        (entry) => entry.platform === "power_manager"
      );

      const map = {};
      const loadIds = [];

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

        if (uniqueId.endsWith("_target_power")) {
          loadIds.push(entry.entity_id);
          continue;
        }

        for (const key of knownKeys) {
          if (uniqueId.endsWith("_" + key)) {
            map[key] = entry.entity_id;
            break;
          }
        }
      }

      this._entityMap = map;
      this._loadEntityIds = loadIds;
    } catch (err) {
      this._registryError = String(err);
      this._entityMap = {};
      this._loadEntityIds = [];
    } finally {
      this._registryLoading = false;
      this._render();
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
    return Number.isFinite(value) ? value : null;
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
        return {
          entityId,
          name: a.load_name || a.friendly_name || entityId,
          type: a.load_type || "",
          priority: Number.isFinite(Number(a.priority)) ? Number(a.priority) : 999,
          requested: this._nullableNumber(a.requested_kw),
          actual: this._nullableNumber(a.actual_kw),
          target: this._nullableNumber(state.state),
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
        "Live-Regelung aktivieren? Der Power Manager darf danach reale Ausgangswerte schreiben."
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
    } finally {
      this._actionBusy = false;
      this._render();
    }
  }

  _icon(icon) {
    return '<ha-icon icon="' + icon + '"></ha-icon>';
  }

  _metric(label, value, icon, cls = "") {
    return (
      '<div class="metric ' +
      cls +
      '">' +
      '<div class="metric-icon">' +
      this._icon(icon) +
      "</div>" +
      '<div class="metric-text"><span>' +
      label +
      "</span><strong>" +
      value +
      "</strong></div></div>"
    );
  }

  _flowNode(title, value, subtitle, icon, cls = "") {
    return (
      '<div class="flow-node ' +
      cls +
      '">' +
      '<div class="node-icon">' +
      this._icon(icon) +
      "</div>" +
      '<div class="node-content"><span>' +
      title +
      "</span><strong>" +
      value +
      "</strong>" +
      (subtitle ? "<small>" + subtitle + "</small>" : "") +
      "</div></div>"
    );
  }

  _loadCard(load) {
    const status = this._loadStatus(load);
    const actual = this._fmt(load.actual, "kW", 2);
    const target = this._fmt(load.target, "kW", 2);
    const requested = this._fmt(load.requested, "kW", 2);

    return (
      '<div class="load-card">' +
      '<div class="load-card-top"><div><strong>' +
      load.name +
      '</strong><span class="priority">P' +
      (load.priority === 999 ? "—" : load.priority) +
      '</span></div><span class="badge ' +
      status.cls +
      '">' +
      status.text +
      "</span></div>" +
      '<div class="load-values">' +
      '<span><small>Ist</small><b>' +
      actual +
      "</b></span>" +
      '<span><small>Soll</small><b>' +
      target +
      "</b></span>" +
      '<span><small>Anforderung</small><b>' +
      requested +
      "</b></span>" +
      "</div>" +
      '<div class="load-flags">' +
      '<span class="' +
      (load.available ? "ok" : "off") +
      '">' +
      (load.available ? "verfügbar" : "gesperrt") +
      "</span>" +
      '<span class="' +
      (load.peakEnabled ? "ok" : "off") +
      '">Peak</span>' +
      '<span class="' +
      (load.surplusEnabled ? "ok" : "off") +
      '">PV</span>' +
      "</div>" +
      "</div>"
    );
  }

  _render() {
    if (!this.shadowRoot) {
      return;
    }

    const style = [
      ":host{display:block;font-family:var(--paper-font-body1_-_font-family,Roboto,Arial,sans-serif);color:var(--primary-text-color)}",
      "ha-card{overflow:hidden;padding:0;background:var(--ha-card-background,var(--card-background-color,#fff));border-radius:var(--ha-card-border-radius,16px)}",
      ".wrap{padding:20px}",
      ".header{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:16px}",
      ".title{display:flex;align-items:center;gap:12px}.title ha-icon{color:var(--primary-color);--mdc-icon-size:28px}.title h2{margin:0;font-size:24px}.version{font-size:12px;color:var(--secondary-text-color)}",
      ".controls{display:grid;grid-template-columns:1.2fr 1fr 1fr 1fr;gap:10px;margin-bottom:14px}",
      ".control,.metric{border:1px solid var(--divider-color);border-radius:14px;padding:12px;background:color-mix(in srgb,var(--card-background-color,#fff) 94%,var(--primary-color) 6%)}",
      ".mode-buttons{display:flex;gap:6px;margin-top:8px}.mode-buttons button,.live-button{border:0;border-radius:9px;padding:8px 10px;cursor:pointer;font:inherit;background:var(--secondary-background-color);color:var(--primary-text-color)}",
      ".mode-buttons button.active,.live-button.on{background:var(--primary-color);color:var(--text-primary-color,#fff)}.live-button.off{background:var(--secondary-background-color)}",
      "button:disabled{opacity:.55;cursor:wait}.control-label{font-size:12px;color:var(--secondary-text-color);display:block}.control strong{font-size:18px}",
      ".main-grid{display:grid;grid-template-columns:minmax(0,2.2fr) minmax(260px,.8fr);gap:14px}",
      ".panel{border:1px solid var(--divider-color);border-radius:16px;padding:14px;background:var(--card-background-color,#fff)}",
      ".panel-title{font-size:14px;font-weight:700;margin:0 0 12px;display:flex;align-items:center;gap:8px}",
      ".source-row{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}",
      ".flow-node{display:flex;gap:10px;align-items:center;border:1px solid var(--divider-color);border-radius:13px;padding:11px;min-width:0;background:var(--secondary-background-color)}",
      ".flow-node.pv{border-color:#f6b73c;background:color-mix(in srgb,#fff 88%,#f6b73c 12%)}.flow-node.battery{border-color:#53b96b;background:color-mix(in srgb,#fff 88%,#53b96b 12%)}.flow-node.grid{border-color:#9aa5b1}.flow-node.base{border-color:var(--primary-color)}",
      ".node-icon{color:var(--primary-color)}.pv .node-icon{color:#ee9d00}.battery .node-icon{color:#249944}.node-content{display:flex;flex-direction:column;min-width:0}.node-content span{font-size:12px;color:var(--secondary-text-color)}.node-content strong{font-size:18px}.node-content small{font-size:11px;color:var(--secondary-text-color)}",
      ".flow-arrow{text-align:center;color:var(--primary-color);font-size:24px;line-height:1;margin:4px 0}",
      ".manager{width:min(360px,80%);margin:0 auto;border:2px solid var(--primary-color);border-radius:16px;padding:13px;text-align:center;background:color-mix(in srgb,var(--card-background-color,#fff) 88%,var(--primary-color) 12%)}",
      ".manager strong{font-size:20px;display:block}.manager small{color:var(--secondary-text-color)}",
      ".loads-flow{display:grid;grid-template-columns:repeat(2,1fr);gap:9px;margin-top:10px}",
      ".load-card{border:1px solid var(--divider-color);border-radius:13px;padding:11px;background:var(--secondary-background-color)}",
      ".load-card-top{display:flex;justify-content:space-between;gap:8px;align-items:center}.load-card-top strong{font-size:14px}.priority{font-size:11px;margin-left:6px;color:var(--secondary-text-color)}",
      ".badge{border-radius:999px;padding:3px 8px;font-size:11px;font-weight:700}.success{background:#d9f5df;color:#177c31}.warning{background:#fff1cc;color:#8b6200}.danger{background:#fde1df;color:#a92a22}.muted{background:var(--divider-color);color:var(--secondary-text-color)}.info{background:#dfeeff;color:#205d9b}",
      ".load-values{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:9px}.load-values span{display:flex;flex-direction:column}.load-values small{font-size:10px;color:var(--secondary-text-color)}.load-values b{font-size:13px}",
      ".load-flags{display:flex;gap:6px;margin-top:8px}.load-flags span{font-size:10px;border-radius:999px;padding:2px 6px}.load-flags .ok{background:#e1f4e5;color:#197235}.load-flags .off{background:var(--divider-color);color:var(--secondary-text-color)}",
      ".stats{display:grid;gap:8px}.metric{display:flex;align-items:center;gap:10px;padding:10px}.metric-icon{color:var(--primary-color)}.metric-text{display:flex;flex-direction:column}.metric-text span{font-size:11px;color:var(--secondary-text-color)}.metric-text strong{font-size:15px}.metric.danger{border-color:#d9534f}.metric.good{border-color:#50a866}",
      ".footer{margin-top:10px;font-size:11px;color:var(--secondary-text-color);display:flex;justify-content:space-between;gap:10px}",
      ".empty{padding:28px;text-align:center;color:var(--secondary-text-color)}",
      "@media(max-width:900px){.controls{grid-template-columns:repeat(2,1fr)}.main-grid{grid-template-columns:1fr}.source-row{grid-template-columns:repeat(2,1fr)}}",
      "@media(max-width:560px){.wrap{padding:12px}.controls{grid-template-columns:1fr}.source-row,.loads-flow{grid-template-columns:1fr}.load-values{grid-template-columns:1fr 1fr}.header{align-items:flex-start;flex-direction:column}}"
    ].join("");

    if (!this._hass || this._registryLoading || !this._entityMap) {
      this.shadowRoot.innerHTML =
        "<style>" +
        style +
        "</style><ha-card><div class=\"empty\">" +
        (this._registryError
          ? "Power Manager Entities konnten nicht geladen werden: " + this._registryError
          : "Power Manager wird geladen …") +
        "</div></ha-card>";
      return;
    }

    const modeState = this._state("operating_mode");
    const mode = modeState ? modeState.state : "normal";
    const live = this._bool("live_control") === true;
    const failSafe = this._bool("fail_safe_active") === true;
    const outputHealthy = this._bool("output_healthy");
    const gridHealthy = this._bool("grid_measurement_healthy");

    const grid = this._num("grid_power");
    const pv = this._num("pv_power");
    const battery = this._num("battery_power");
    const soc = this._num("battery_soc");
    const base = this._num("base_load");
    const effectiveLimit = this._num("effective_grid_limit");
    const available = this._num("available_budget");
    const surplus = this._num("surplus_budget");
    const headroom = this._num("grid_headroom");
    const requested = this._num("total_requested_power");
    const targetTotal = this._num("total_target_power");
    const activeCount = this._num("active_load_count");
    const limitedCount = this._num("limited_load_count");
    const gridAge = this._num("grid_measurement_age");
    const failReasonState = this._state("fail_safe_reason");
    const failReason =
      failReasonState && !["none", "unknown", "unavailable"].includes(failReasonState.state)
        ? failReasonState.state
        : "—";

    const batterySubtitle =
      battery === null
        ? ""
        : battery > 0.05
          ? "entlädt"
          : battery < -0.05
            ? "lädt"
            : "Ruhe";

    const gridSubtitle =
      grid === null
        ? ""
        : grid > 0.05
          ? "Bezug"
          : grid < -0.05
            ? "Einspeisung"
            : "nahezu ausgeglichen";

    const loads = this._loads();

    const html =
      "<style>" +
      style +
      "</style>" +
      "<ha-card>" +
      '<div class="wrap">' +
      '<div class="header">' +
      '<div class="title">' +
      this._icon("mdi:lightning-bolt-circle") +
      '<div><h2>Power Manager</h2><div class="version">Dashboard Card v' +
      POWER_MANAGER_CARD_VERSION +
      "</div></div></div>" +
      '<div class="badge ' +
      (failSafe ? "danger" : "success") +
      '">' +
      (failSafe ? "Fail-Safe aktiv" : "Regler bereit") +
      "</div></div>" +

      '<div class="controls">' +
      '<div class="control"><span class="control-label">Betriebsart</span><strong>' +
      this._labelMode(mode) +
      '</strong><div class="mode-buttons">' +
      '<button data-action="mode-normal" class="' +
      (mode === "normal" ? "active" : "") +
      '" ' +
      (this._actionBusy ? "disabled" : "") +
      ">Normal</button>" +
      '<button data-action="mode-surplus" class="' +
      (mode === "surplus" ? "active" : "") +
      '" ' +
      (this._actionBusy ? "disabled" : "") +
      ">Überschuss</button></div></div>" +
      '<div class="control"><span class="control-label">Live-Regelung</span><strong>' +
      (live ? "Ein" : "Aus") +
      '</strong><div class="mode-buttons"><button data-action="toggle-live" class="live-button ' +
      (live ? "on" : "off") +
      '" ' +
      (this._actionBusy ? "disabled" : "") +
      ">" +
      (live ? "Live ausschalten" : "Live aktivieren") +
      "</button></div></div>" +
      '<div class="control"><span class="control-label">Effektives PMAX</span><strong>' +
      this._fmt(effectiveLimit, "kW", 1) +
      '</strong><div class="control-label">Headroom: ' +
      this._fmt(headroom, "kW", 1) +
      "</div></div>" +
      '<div class="control"><span class="control-label">Batterie-SOC</span><strong>' +
      this._fmt(soc, "%", 1) +
      '</strong><div class="control-label">' +
      (this._bool("battery_soc_blocking_surplus") ? "Reserve sperrt Überschuss" : "Reserve frei") +
      "</div></div>" +
      "</div>" +

      '<div class="main-grid">' +
      '<div class="panel">' +
      '<div class="panel-title">' +
      this._icon("mdi:transmission-tower") +
      " Energiefluss & Verbraucher</div>" +
      '<div class="source-row">' +
      this._flowNode("PV", this._fmt(pv, "kW", 2), "Erzeugung", "mdi:solar-power", "pv") +
      this._flowNode("Netz", this._fmtSigned(grid, "kW", 2), gridSubtitle, "mdi:transmission-tower", "grid") +
      this._flowNode("Batterie", this._fmtSigned(battery, "kW", 2), batterySubtitle, "mdi:battery", "battery") +
      this._flowNode("Basislast", this._fmt(base, "kW", 2), "nicht regelbar", "mdi:home-lightning-bolt", "base") +
      "</div>" +
      '<div class="flow-arrow">↓</div>' +
      '<div class="manager"><strong>Power Manager</strong><small>' +
      (mode === "surplus"
        ? "PV-Budget " + this._fmt(surplus, "kW", 2)
        : "Peak-Budget " + this._fmt(this._num("peak_budget"), "kW", 2)) +
      " · verfügbar " +
      this._fmt(available, "kW", 2) +
      "</small></div>" +
      '<div class="flow-arrow">↓</div>' +
      '<div class="loads-flow">' +
      (loads.length
        ? loads.map((load) => this._loadCard(load)).join("")
        : '<div class="empty">Noch keine regelbaren Verbraucher gefunden.</div>') +
      "</div></div>" +

      '<div class="panel"><div class="panel-title">' +
      this._icon("mdi:chart-box-outline") +
      " Status & Diagnose</div><div class=\"stats\">" +
      this._metric("Angefordert", this._fmt(requested, "kW", 2), "mdi:gauge") +
      this._metric("Soll gesamt", this._fmt(targetTotal, "kW", 2), "mdi:target") +
      this._metric("Aktive Verbraucher", this._fmt(activeCount, "", 0), "mdi:power-plug") +
      this._metric("Begrenzte Verbraucher", this._fmt(limitedCount, "", 0), "mdi:speedometer-slow") +
      this._metric("Netzmessung", gridHealthy === false ? "gestört" : "OK", "mdi:meter-electric-outline", gridHealthy === false ? "danger" : "good") +
      this._metric("Alter Netzwert", this._fmt(gridAge, "s", 1), "mdi:timer-outline") +
      this._metric("Ausgangspfad", outputHealthy === false ? "Fehler" : "Verbunden", "mdi:connection", outputHealthy === false ? "danger" : "good") +
      this._metric("Fail-Safe", failSafe ? failReason : "Inaktiv", "mdi:shield-alert-outline", failSafe ? "danger" : "good") +
      "</div></div>" +
      "</div>" +

      '<div class="footer"><span>Ist/Soll/Anforderung werden direkt aus der Power-Manager-Integration gelesen.</span><span>Grid: ' +
      this._fmt(grid, "kW", 2) +
      " · PV: " +
      this._fmt(pv, "kW", 2) +
      "</span></div>" +
      "</div></ha-card>";

    this.shadowRoot.innerHTML = html;

    const normalButton = this.shadowRoot.querySelector('[data-action="mode-normal"]');
    const surplusButton = this.shadowRoot.querySelector('[data-action="mode-surplus"]');
    const liveButton = this.shadowRoot.querySelector('[data-action="toggle-live"]');

    if (normalButton) {
      normalButton.addEventListener("click", () => this._setMode("normal"));
    }
    if (surplusButton) {
      surplusButton.addEventListener("click", () => this._setMode("surplus"));
    }
    if (liveButton) {
      liveButton.addEventListener("click", () => this._toggleLive());
    }
  }
}

if (!customElements.get("power-manager-card")) {
  customElements.define("power-manager-card", PowerManagerCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "power-manager-card")) {
  window.customCards.push({
    type: "power-manager-card",
    name: "Power Manager",
    description:
      "Energiefluss, Ist-/Sollwerte, Betriebsart, Live-Regelung und Diagnose für die Power-Manager-Integration.",
    preview: true,
    documentationURL: "https://github.com/ww118-rgb/power-manager"
  });
}

console.info(
  "%c POWER-MANAGER-CARD %c v" + POWER_MANAGER_CARD_VERSION,
  "color: white; background: #03a9f4; font-weight: 700; padding: 2px 5px;",
  "color: #03a9f4; font-weight: 700;"
);
