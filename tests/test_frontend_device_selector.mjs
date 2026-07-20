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
  value: { language: "en" },
});

const here = dirname(fileURLToPath(import.meta.url));
const cardPath = resolve(
  here,
  "../custom_components/tuyaextend_amperepoint/frontend/amperepoint-q22-card.js",
);
await import(pathToFileURL(cardPath));

const Card = customElements.get("amperepoint-q22-card");
const card = new Card();
card.setConfig({
  entities: { power: "sensor.garage_power" },
});
card.render = () => {};
card._hass = {
  devices: {
    garage: { name: "Garage" },
    driveway: { name: "Driveway" },
  },
  entities: {
    "sensor.garage_power": {
      platform: "tuyaextend_amperepoint",
      device_id: "garage",
      translation_key: "power",
    },
    "time.garage_schedule_start": {
      platform: "tuyaextend_amperepoint",
      device_id: "garage",
      translation_key: "schedule_start_time",
    },
    "sensor.driveway_power": {
      platform: "tuyaextend_amperepoint",
      device_id: "driveway",
      translation_key: "power",
    },
  },
  states: {
    "sensor.garage_power": { state: "3.7", attributes: {} },
    "time.garage_schedule_start": { state: "18:00:00", attributes: {} },
    "sensor.driveway_power": { state: "0", attributes: {} },
  },
};

assert.equal(
  card.apRegistryEntities("garage").scheduleStartTime,
  "time.garage_schedule_start",
  "schedule_start_time should use the exact translation-key mapping",
);

card._plannerDirty = true;
card.selectDevice("driveway");
assert.equal(card.apSelectedDeviceId(), "garage");
assert.equal(card.config.entities.power, "sensor.garage_power");

card._plannerDirty = false;
card._plannerDraft = { enabled: true, windows: [{ start: "18:00" }] };
card._plannerError = "old charger error";
card.selectDevice("driveway");
assert.equal(card.apSelectedDeviceId(), "driveway");
assert.equal(card.config.entities.power, "sensor.driveway_power");
assert.equal(card.config.title, "Driveway");
assert.equal(card._plannerDraft, null);
assert.equal(card._plannerError, null);

console.log("frontend device selector tests passed");
