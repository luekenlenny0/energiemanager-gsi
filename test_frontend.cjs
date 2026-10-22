const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const registry = new Map();
class Element {
  attachShadow() {
    this.shadowRoot = { innerHTML: "", querySelector: () => null, querySelectorAll: () => [] };
  }
}
const context = {
  HTMLElement: Element,
  customElements: { get: name => registry.get(name), define: (name, value) => registry.set(name, value) },
  window: {}, console: { info() {} },
  document: { createElement: name => ({ tagName: name }) },
};
vm.createContext(context);
vm.runInContext(fs.readFileSync("custom_components/power_manager/frontend/power-manager-card.js", "utf8"), context);

function card() { return new (registry.get("power-manager-card"))(); }

test("registry distinguishes totals and projected power from consumer sensors", async () => {
  const el = card();
  el._hass = { states: {}, callWS: async () => [
    { platform: "power_manager", unique_id: "entry_grid_power", entity_id: "sensor.grid" },
    { platform: "power_manager", unique_id: "entry_projected_grid_power", entity_id: "sensor.projected" },
    { platform: "power_manager", unique_id: "entry_total_target_power", entity_id: "sensor.total" },
    { platform: "power_manager", unique_id: "entry_subentry_target_power", entity_id: "sensor.consumer" },
  ] };
  await el._loadRegistry();
  assert.equal(el._entityMap.grid_power, "sensor.grid");
  assert.equal(el._entityMap.projected_grid_power, "sensor.projected");
  assert.equal(el._entityMap.total_target_power, "sensor.total");
  assert.deepEqual(Array.from(el._loadEntityIds), ["sensor.consumer"]);
});

test("display scaling and missing readings", () => {
  const el = card();
  el.setConfig({ power_unit: "W" });
  assert.match(el._fmt(2.3, "kW"), /2.300 W/);
  assert.equal(el._fmt(null), "—");
  assert.throws(() => el.setConfig({ power_unit: "A" }), /W oder kW/);
});

test("consumer priority, visibility, custom name and escaped content", () => {
  const el = card();
  el._hass = { states: {
    "sensor.b": { state: "1", attributes: { load_name: "B", priority: 2 } },
    "sensor.a": { state: "2", attributes: { load_name: "A", priority: 1 } },
    "sensor.c": { state: "3", attributes: { load_name: "C", priority: 3 } },
  } };
  el._loadEntityIds = ["sensor.b", "sensor.a", "sensor.c"];
  el.setConfig({ loads: { "sensor.a": { name: "<script>" }, "sensor.c": { hidden: true } } });
  const loads = el._loads();
  assert.equal(loads.length, 2);
  assert.equal(loads[0].name, "<script>");
  assert.match(el._consumerControl(loads[0]), /&lt;script&gt;/);
  assert.doesNotMatch(el._consumerControl(loads[0]), /<script>/);
});

test("output labels preserve custom codes, amperes and off values", () => {
  const el = card();
  el._hass = { states: {} };
  assert.equal(el._outputLabel({ type: "switch", outputEntity: "number.mode", target: 2, commandOn: "12" }), "12");
  assert.equal(el._outputLabel({ type: "switch", outputEntity: "number.mode", target: 0, commandOff: "14" }), "14");
  assert.match(el._outputLabel({ type: "evse", outputEntity: "number.current", outputUnit: "A", target: 6.9, phases: 3, voltage: 230 }), /10,00 A/);
  assert.match(el._outputLabel({ type: "evse", outputEntity: "number.current", outputUnit: "A", target: 0, pauseCurrent: 0.01 }), /0,01 A/);
});

test("service errors are visible instead of unhandled", async () => {
  const el = card();
  el._hass = { states: {}, callService: async () => { throw new Error("Gerät nicht erreichbar"); } };
  el._entityMap = { operating_mode: "select.mode" };
  await el._setMode("surplus");
  assert.equal(el._actionBusy, false);
  assert.match(el.shadowRoot.innerHTML, /Gerät nicht erreichbar/);
});

test("visual editor is registered", () => {
  assert.ok(registry.has("power-manager-card-editor"));
  assert.equal(registry.get("power-manager-card").getConfigElement().tagName, "power-manager-card-editor");
});

test("manual entities are linked by immutable registry identity", async () => {
  const el = card();
  el._hass = { states: {}, callWS: async () => [
    { platform: "power_manager", unique_id: "entry_load_target_power", entity_id: "sensor.renamed" },
    { platform: "power_manager", unique_id: "entry_load_manual_power", entity_id: "number.renamed" },
    { platform: "power_manager", unique_id: "entry_load_manual_mode", entity_id: "select.renamed" },
  ] };
  await el._loadRegistry();
  assert.equal(el._loadControls["sensor.renamed"].manual_power, "number.renamed");
  assert.equal(el._loadControls["sensor.renamed"].manual_mode, "select.renamed");
});

function manualCard() {
  const el = card();
  const calls = [];
  el._hass = { states: { "sensor.load": { state: "2", attributes: { load_name: "Heizung", load_type: "modulating", min_kw: 1, max_kw: 5 } } },
    callService: async (domain, service, data) => calls.push({ domain, service, data }) };
  el._entityMap = {};
  el._loadEntityIds = ["sensor.load"];
  el._loadControls = { "sensor.load": { manual_power: "number.demand", manual_mode: "select.control" } };
  return { el, calls };
}

test("EIN writes pending kW value before manual enable", async () => {
  const { el, calls } = manualCard();
  el._draftPowers["sensor.load"] = "3.5";
  await el._setManualMode("sensor.load", "manual");
  assert.equal(calls.length, 2);
  assert.equal(calls[0].domain, "number");
  assert.equal(calls[0].data.value, 3.5);
  assert.equal(calls[1].data.option, "manual");
});

test("AUS ignores invalid draft and always requests off", async () => {
  const { el, calls } = manualCard();
  el._draftPowers["sensor.load"] = "bad";
  await el._setManualMode("sensor.load", "off");
  assert.equal(calls.length, 1);
  assert.equal(calls[0].data.option, "off");
});

test("invalid manual power neither writes nor enables", async () => {
  const { el, calls } = manualCard();
  for (const value of ["", "NaN", "7", "0.5", "-1"]) {
    el._draftPowers["sensor.load"] = value;
    await el._setManualMode("sensor.load", "manual");
    assert.equal(calls.length, 0);
    assert.ok(el._actionError);
  }
});

test("radial graph contains all consumers and separate base demand", () => {
  const { el } = manualCard();
  el._hass.states["sensor.base"] = { state: "0.542", attributes: { source: "grid_pv_battery" } };
  el._entityMap.house_base_power = "sensor.base";
  const graph = el._radialFlow(el._loads());
  assert.match(graph, /Grundverbrauch/);
  assert.match(graph, /542 W/);
  assert.match(graph, /Heizung/);
  assert.match(graph, /animateMotion/);
  assert.doesNotMatch(graph, /NaN/);
});

test("registry changes refresh controls and subscription is released", async () => {
  const el = card();
  let eventCallback, eventType, released = 0, refreshed = 0;
  el.isConnected = true;
  el._hass = { connection: { subscribeEvents: async (callback, type) => {
    eventCallback = callback; eventType = type; return () => released++;
  } } };
  el._loadRegistry = async () => refreshed++;
  await el._subscribeRegistry();
  assert.equal(eventType, "entity_registry_updated");
  await eventCallback();
  assert.equal(refreshed, 1);
  el.disconnectedCallback();
  assert.equal(released, 1);
});

test("disconnect during pending subscription does not leak event listener", async () => {
  const el = card();
  let resolve, released = 0;
  el.isConnected = true;
  el._hass = { connection: { subscribeEvents: () => new Promise(done => { resolve = done; }) } };
  const pending = el._subscribeRegistry();
  el.isConnected = false;
  el.disconnectedCallback();
  resolve(() => released++);
  await pending;
  assert.equal(released, 1);
  assert.equal(el._registryUnsubscribe, null);
});
