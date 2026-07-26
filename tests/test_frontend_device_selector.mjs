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
    "sensor.garage_session_duration": {
      platform: "tuyaextend_amperepoint",
      device_id: "garage",
      translation_key: "session_duration",
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

assert.equal(
  card.apRegistryEntities("garage").sessionDuration,
  "sensor.garage_session_duration",
  "session_duration must resolve through the registry map (Prime telemetry)",
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

// A charger applies a new current limit before its entity reports it, so the
// card holds the requested value instead of snapping the slider back.
const limitCard = new Card();
limitCard.setConfig({ entities: { currentLimit: "number.limit" } });
limitCard.render = () => {};
const limitStates = { "number.limit": { state: "6", attributes: { min: 6, max: 16 } } };
limitCard._hass = { states: limitStates, callService: async () => {} };

await limitCard.setCurrentLimit(16);
assert.equal(limitCard._pendingCurrentLimit, 16);

limitCard.hass = { states: limitStates, callService: async () => {} };
assert.equal(limitCard._pendingCurrentLimit, 16, "a stale reading must not clear it");

limitStates["number.limit"] = { state: "16", attributes: { min: 6, max: 16 } };
limitCard.hass = { states: limitStates, callService: async () => {} };
assert.equal(limitCard._pendingCurrentLimit, null, "confirmation releases it");
clearTimeout(limitCard._pendingCurrentLimitTimer);

console.log("current limit tests passed");

// The charger's switch permits charging; it is on with no vehicle attached,
// so the button must follow the session instead of the switch.
const btnCard = new Card();
btnCard.setConfig({
  entities: { switch: "switch.charging", status: "sensor.status", power: "sensor.power" },
});
btnCard.render = () => {};
const calls = [];
const btnStates = {
  "switch.charging": { state: "on", attributes: {} },
  "sensor.status": { state: "Gotowy", attributes: {} },
  "sensor.power": { state: "0", attributes: {} },
};
btnCard._hass = {
  states: btnStates,
  callService: async (domain, service, data) => calls.push(`${domain}.${service}`),
};

assert.equal(btnCard.isCharging(), false, "an enabled switch is not a session");

// Pressing start keeps the switch on rather than toggling it off.
await btnCard.toggleCharging();
assert.deepEqual(calls, ["switch.turn_on"]);
assert.equal(btnCard._pendingCharging, true, "the requested state is held");

// Once the charger reports the session, the requested state is released.
btnStates["sensor.status"] = { state: "Ladowanie", attributes: {} };
btnCard.hass = btnCard._hass;
assert.equal(btnCard._pendingCharging, null);

// Stopping now turns the switch off.
await btnCard.toggleCharging();
assert.deepEqual(calls, ["switch.turn_on", "switch.turn_off"]);
clearTimeout(btnCard._pendingChargingTimer);

console.log("charging button tests passed");
