// Native Home Assistant panel: one persistent card, plus direct point status.
import "./power-manager-card.js?v=3.4.0";

class EnergiemanagerGSIPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `<style>
      :host{display:block;height:100%;overflow:auto;background:var(--primary-background-color);color:var(--primary-text-color)}
      header{display:flex;align-items:center;flex-wrap:wrap;gap:12px;padding:12px 20px;background:var(--app-header-background-color);color:var(--app-header-text-color)}
      h1{font-size:20px;margin:0;flex:1} a{color:inherit} main{max-width:1440px;margin:auto;padding:20px}
      button{font:inherit;background:transparent;color:inherit;border:1px solid currentColor;border-radius:8px;padding:8px;cursor:pointer} #editor{padding:20px;background:var(--card-background-color);border-radius:16px;margin-bottom:20px}
      #points{margin-top:24px;padding:20px;border:1px solid var(--divider-color);border-radius:16px;background:var(--card-background-color)}
      h2{font-size:18px;margin-top:0}.point{display:grid;grid-template-columns:minmax(130px,1fr) 100px minmax(150px,2fr) minmax(90px,1fr);gap:12px;padding:12px 0;border-top:1px solid var(--divider-color)}
      .endpoint{overflow-wrap:anywhere;color:var(--secondary-text-color)}.error{color:var(--error-color)}p{color:var(--secondary-text-color)}
      @media(max-width:700px){main{padding:10px}.point{grid-template-columns:1fr 1fr}.endpoint{grid-column:1/-1}}
    </style><header><ha-menu-button></ha-menu-button><ha-icon icon="mdi:home-lightning-bolt"></ha-icon><h1>Energiemanager GSI</h1><button id="customize">Ansicht anpassen</button><a href="/config/integrations/integration/power_manager">Konfiguration</a></header>
    <main><section id="editor" hidden><power-manager-card-editor></power-manager-card-editor><p id="save-status"></p><button id="done">Fertig</button></section><power-manager-card></power-manager-card><section id="points"><h2>Modbus &amp; MQTT</h2>
    <p>Mess- und Stellpunkte unter Konfiguration → Mess-/Stellpunkt hinzufügen anlegen. Danach Zähler und Verbraucher zuordnen.</p><div id="point-list"></div></section></main>`;
    this._card = this.shadowRoot.querySelector("power-manager-card");
    this._card.setConfig({ title: "Energiefluss", show_diagnostics: true });
    this._editor = this.shadowRoot.querySelector("power-manager-card-editor");
    this.shadowRoot.querySelector("#customize").addEventListener("click", () => {
      this._editor.setConfig(this._card._config);
      this._editor.hass = this._hass;
      this.shadowRoot.querySelector("#editor").hidden = false;
    });
    this.shadowRoot.querySelector("#done").addEventListener("click", () => { this.shadowRoot.querySelector("#editor").hidden = true; });
    this._editor.addEventListener("config-changed", event => {
      this._card.setConfig(event.detail.config);
      const status = this.shadowRoot.querySelector("#save-status");
      try { localStorage.setItem(this._storageKey, JSON.stringify(event.detail.config)); status.textContent = "Ansicht für diesen Benutzer in diesem Browser gespeichert."; }
      catch (_) { status.textContent = "Speichern im Browser nicht möglich. Die Ansicht gilt bis zum Neuladen."; }
    });
  }

  set narrow(value) { this.shadowRoot.querySelector("ha-menu-button").narrow = value; }
  set panel(value) { this._panel = value; }
  set hass(value) {
    this._hass = value;
    const key = `gsi-panel:${this._panel?.config?.entry_id || "default"}:${value.user?.id || "default"}`;
    if (key !== this._storageKey) {
      this._storageKey = key;
      this._card.setConfig({ title: "Energiefluss", show_diagnostics: true });
      try { const config = JSON.parse(localStorage.getItem(key)); if (config) this._card.setConfig(config); } catch (_) { /* Defaults remain usable. */ }
    }
    this._card.hass = value;
    this.shadowRoot.querySelector("ha-menu-button").hass = value;
    const list = this.shadowRoot.querySelector("#point-list");
    const fragment = document.createDocumentFragment();
    const points = Object.values(value.states).filter(state => state.attributes.power_manager_point
      && (!this._panel?.config?.entry_id || state.attributes.power_manager_entry_id === this._panel.config.entry_id));
    for (const state of points.sort((a,b) => (a.attributes.friendly_name || a.entity_id).localeCompare(b.attributes.friendly_name || b.entity_id))) {
      const row = document.createElement("div"); row.className = "point";
      for (const text of [state.attributes.friendly_name || state.entity_id, state.attributes.protocol.toUpperCase(),
        state.attributes.endpoint, state.attributes.point_error || `${state.state} ${state.attributes.unit_of_measurement || ""}`]) {
        const cell = document.createElement("span"); cell.textContent = text; row.appendChild(cell);
      }
      row.children[2].className = "endpoint";
      if (state.attributes.point_error) row.children[3].className = "error";
      fragment.appendChild(row);
    }
    if (!points.length) { const empty = document.createElement("p"); empty.textContent = "Noch keine direkten Anschlüsse angelegt."; fragment.appendChild(empty); }
    list.replaceChildren(fragment);
  }
}

if (!customElements.get("energiemanager-gsi-panel")) customElements.define("energiemanager-gsi-panel", EnergiemanagerGSIPanel);
