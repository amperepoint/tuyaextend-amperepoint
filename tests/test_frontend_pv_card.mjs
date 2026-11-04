import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

globalThis.HTMLElement = class {};
globalThis.customElements = {
  elements: new Map(),
  get(name) {
    return this.elements.get(name);
  },
  define(name, element) {
    this.elements.set(name, element);
  },
};
globalThis.window = { customCards: [] };
Object.defineProperty(globalThis, "navigator", {
  configurable: true,
  value: { language: "pl" },
});

const here = dirname(fileURLToPath(import.meta.url));
const cardPath = resolve(
  here,
  "../custom_components/tuyaextend_amperepoint/frontend/amperepoint-q22-card.js",
);
await import(pathToFileURL(cardPath));

const Card = customElements.get("amperepoint-q22-card");

function makeCard(states, entities) {
  const card = new Card();
  card.setConfig({ language: "pl", entities });
  card.render = () => {};
  card._hass = { language: "pl", states, entities: {}, devices: {} };
  return card;
}

const entities = {
  pvMode: "select.charger_pv_mode",
  pvSurplus: "sensor.charger_pv_surplus",
  sessionPvShare: "sensor.charger_session_pv_share",
  pvProduction: "sensor.pv_power",
  planner: "sensor.charger_planner",
};

const states = {
  "select.charger_pv_mode": {
    state: "PV surplus only",
    attributes: { options: ["Off", "PV surplus only", "PV + grid"] },
  },
  "sensor.charger_pv_surplus": {
    state: "2300",
    attributes: { surplus_state: "charging_from_pv" },
  },
  "sensor.charger_session_pv_share": { state: "78", attributes: {} },
  "sensor.pv_power": { state: "5400", attributes: {} },
  "sensor.charger_planner": {
    state: "surplus",
    attributes: { surplus_state: "charging_from_pv" },
  },
};

const card = makeCard(states, entities);
const html = card.pvCard();

assert.ok(html.includes("Ładowanie ze słońca"), "PV section title is rendered");
assert.ok(html.includes("Ładowanie z PV"), "the decision state is translated");
assert.ok(html.includes("2300"), "available surplus is shown");
assert.ok(html.includes("5400"), "PV production is shown");
assert.ok(html.includes("78%"), "solar share of the session is shown");
assert.ok(
  html.includes('<option value="PV surplus only" selected>'),
  "the active mode is pre-selected in the picker",
);

// A charger without any PV entities must not grow an empty section.
const bare = makeCard({}, {});
assert.equal(bare.pvCard(), "", "no PV entities means no PV section");

// Missing measurements must surface as a readable state, not a blank.
const noData = makeCard(
  {
    ...states,
    "sensor.charger_pv_surplus": {
      state: "0",
      attributes: { surplus_state: "no_data" },
    },
    "sensor.charger_planner": {
      state: "surplus",
      attributes: { surplus_state: "no_data" },
    },
  },
  entities,
);
assert.ok(
  noData.pvCard().includes("Brak danych energetycznych"),
  "missing energy data is stated explicitly",
);

console.log("PV card tests passed");
