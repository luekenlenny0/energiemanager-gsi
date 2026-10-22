const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

function setup() {
  const elements = new Map(), definitions = new Map(), saved = new Map();
  class Element {
    constructor() { this.children = []; this.listeners = {}; this.hidden = false; }
    attachShadow() { this.shadowRoot = { innerHTML: "", querySelector: selector => {
      if (!elements.has(selector)) elements.set(selector, new Element());
      return elements.get(selector);
    } }; }
    setConfig(value) { this._config = value; }
    addEventListener(name, fn) { this.listeners[name] = fn; }
    appendChild(child) { this.children.push(child); }
    replaceChildren(...children) { this.children = children; }
  }
  const context = { HTMLElement: Element, document: {
    createElement: () => new Element(), createDocumentFragment: () => new Element(),
  }, customElements: { get: name => definitions.get(name), define: (name, value) => definitions.set(name,value) },
    localStorage: { getItem: key => saved.get(key) || null, setItem: (key, value) => saved.set(key, value) },
  };
  vm.createContext(context);
  const source = fs.readFileSync("custom_components/power_manager/frontend/energiemanager-gsi-panel.js", "utf8");
  vm.runInContext(source.replace(/^import .*;$/m, ""), context);
  return { panel: new (definitions.get("energiemanager-gsi-panel"))(), elements, saved };
}

test("native panel keeps its card and escapes names, endpoint and error text", () => {
  const {panel,elements} = setup();
  const card = elements.get("power-manager-card");
  panel.panel = {config:{entry_id:"entry"}};
  const state = { entity_id: "sensor.point", state: "1200", attributes: {
    power_manager_point:true, power_manager_entry_id:"entry", protocol:"mqtt", friendly_name:"<img onerror=bad>",
    endpoint:"<script>bad</script>", point_error:"<svg/onload=bad>" }};
  panel.hass = { user:{id:"user"}, states:{ "sensor.point":state, "sensor.foreign":{
    ...state,attributes:{...state.attributes,power_manager_entry_id:"other"}} }};
  panel.hass = { user:{id:"user"}, states:{ "sensor.point":state }};
  assert.equal(card, elements.get("power-manager-card"));
  assert.equal(elements.get("#point-list").children[0].children.length, 1);
  const row = elements.get("#point-list").children[0].children[0];
  assert.equal(row.children[0].textContent, "<img onerror=bad>");
  assert.equal(row.children[2].textContent, "<script>bad</script>");
  assert.equal(row.children[3].textContent, "<svg/onload=bad>");
  assert.equal(row.children[3].className, "error");
});

test("panel edits save per browser user/entry and reload without service writes", () => {
  const {panel,elements,saved} = setup();
  panel.panel = {config:{entry_id:"entry"}};
  panel.hass = {user:{id:"alice"},states:{}};
  elements.get("#customize").listeners.click();
  assert.equal(elements.get("#editor").hidden, false);
  const config = {title:"Mein Haus",power_unit:"W"};
  elements.get("power-manager-card-editor").listeners["config-changed"]({detail:{config}});
  assert.deepEqual(JSON.parse(saved.get("gsi-panel:entry:alice")),config);
  elements.get("#done").listeners.click();
  assert.equal(elements.get("#editor").hidden,true);
  assert.match(elements.get("#save-status").textContent,/gespeichert/);
  panel.hass = {user:{id:"bob"},states:{}};
  assert.equal(elements.get("power-manager-card")._config.title,"Energiefluss");
  panel.hass = {user:{id:"alice"},states:{}};
  assert.equal(elements.get("power-manager-card")._config.title,"Mein Haus");
});
