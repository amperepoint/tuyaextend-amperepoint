import assert from "node:assert/strict";
import test from "node:test";
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

// Optimistic command state belongs to the charger that received the command.
// It must not be rendered on another charger after a device switch.
card._pendingCharging = true;
card._pendingCurrentLimit = 16;
card.selectDevice("garage");
assert.equal(card._pendingCharging, null);
assert.equal(card._pendingCurrentLimit, null);
assert.equal(card.apSelectedDeviceId(), "garage");

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


// Render scheduling and DOM-state regression coverage for issue #30.
const chargerEntity = {
  platform: "tuyaextend_amperepoint",
  device_id: "charger",
  translation_key: "power",
};

function state(entityId, value, attributes = {}) {
  return {
    entity_id: entityId,
    state: String(value),
    attributes,
    last_changed: "2026-08-13T10:00:00+00:00",
    last_updated: "2026-08-13T10:00:00+00:00",
  };
}

test("the HA state may arrive before Lovelace calls setConfig", () => {
  const card = new Card();
  let renders = 0;
  card.render = () => {
    renders += 1;
  };

  assert.doesNotThrow(() => {
    card.hass = {
      entities: {},
      devices: {},
      states: { "sensor.unrelated": state("sensor.unrelated", 1) },
    };
  });
  assert.equal(renders, 1);

  assert.doesNotThrow(() => {
    card.setConfig({ entities: { power: "sensor.charger_power" } });
  });
  assert.equal(renders, 2);
});

test("unrelated Home Assistant updates neither render nor repeat device discovery", () => {
  const card = new Card();
  card.setConfig({ entities: { power: "sensor.charger_power" } });

  let detections = 0;
  let renders = 0;
  card.detectEntities = () => {
    detections += 1;
    return { entities: {}, title: null };
  };
  card.render = () => {
    renders += 1;
  };

  const entities = { "sensor.charger_power": chargerEntity };
  const devices = { charger: { name: "Garage charger" } };
  const power = state("sensor.charger_power", "3.7", { unit_of_measurement: "kW" });

  card.hass = {
    entities,
    devices,
    states: {
      "sensor.charger_power": power,
      "sensor.weather_temperature": state("sensor.weather_temperature", 20),
    },
  };
  assert.equal(renders, 1);
  assert.equal(detections, 1);

  card.hass = {
    entities,
    devices,
    states: {
      "sensor.charger_power": power,
      "sensor.weather_temperature": state("sensor.weather_temperature", 21),
    },
  };
  assert.equal(renders, 1, "an unrelated state update must not replace the card DOM");
  assert.equal(detections, 1, "stable registries must reuse charger discovery");

  card.hass = {
    entities,
    devices,
    states: {
      "sensor.charger_power": {
        ...power,
        last_updated: "2026-08-13T10:00:01+00:00",
      },
      "sensor.weather_temperature": state("sensor.weather_temperature", 21),
    },
  };
  assert.equal(renders, 1, "timestamps that are not displayed must not trigger a render");
  assert.equal(detections, 1);

  card.hass = {
    entities: { ...entities },
    devices: { ...devices },
    states: {
      "sensor.charger_power": power,
      "sensor.weather_temperature": state("sensor.weather_temperature", 21),
    },
  };
  assert.equal(renders, 1, "equivalent registry snapshots must reuse the discovery key");
  assert.equal(detections, 1);

  card.hass = {
    entities,
    devices,
    states: {
      "sensor.charger_power": state("sensor.charger_power", "4.1", {
        unit_of_measurement: "kW",
      }),
      "sensor.weather_temperature": state("sensor.weather_temperature", 21),
    },
  };
  assert.equal(renders, 2, "a charger state update must still refresh the UI");
  assert.equal(detections, 1);
});

test("fallback discovery notices a same-count replacement of state IDs", () => {
  const card = new Card();
  card.setConfig({});
  let detections = 0;
  card.detectEntities = () => {
    detections += 1;
    return { entities: {}, title: null };
  };
  card.render = () => {};

  card.hass = {
    states: { "sensor.old_charger_power": state("sensor.old_charger_power", 0) },
  };
  card.hass = {
    states: { "sensor.new_charger_power": state("sensor.new_charger_power", 0) },
  };

  assert.equal(detections, 2, "changed entity IDs must invalidate fallback discovery");
});

test("rapid relevant updates are coalesced into one animation-frame render", () => {
  const originalRequest = globalThis.requestAnimationFrame;
  const frames = [];
  globalThis.requestAnimationFrame = (callback) => {
    frames.push(callback);
    return frames.length;
  };

  try {
    const card = new Card();
    card.setConfig({ entities: { power: "sensor.charger_power" } });
    card.detectEntities = () => ({ entities: {}, title: null });
    let renders = 0;
    card.render = () => {
      renders += 1;
    };
    const entities = { "sensor.charger_power": chargerEntity };
    const devices = { charger: { name: "Garage charger" } };

    card.hass = {
      entities,
      devices,
      states: { "sensor.charger_power": state("sensor.charger_power", "1.0") },
    };
    card.hass = {
      entities,
      devices,
      states: { "sensor.charger_power": state("sensor.charger_power", "2.0") },
    };
    card.hass = {
      entities,
      devices,
      states: { "sensor.charger_power": state("sensor.charger_power", "3.0") },
    };

    assert.equal(renders, 0);
    assert.equal(frames.length, 1, "only one browser frame should be scheduled");
    frames.shift()();
    assert.equal(renders, 1);
    assert.equal(card._renderQueued, false);
    assert.equal(card._renderFrame, null);
  } finally {
    if (originalRequest === undefined) delete globalThis.requestAnimationFrame;
    else globalThis.requestAnimationFrame = originalRequest;
  }
});

test("a late HACS update entity invalidates the negative lookup cache", () => {
  const card = new Card();
  card.setConfig({ entities: { power: "sensor.charger_power" } });
  card.detectEntities = () => ({ entities: {}, title: null });
  card.render = () => {};
  const entities = { "sensor.charger_power": chargerEntity };
  const devices = { charger: { name: "Garage charger" } };

  card.hass = {
    entities,
    devices,
    states: { "sensor.charger_power": state("sensor.charger_power", "0") },
  };
  assert.equal(card.hacsUpdateEntity(), null);

  const update = state("update.tuyaextend_amperepoint_update", "off", {
    installed_version: "0.5.35",
    latest_version: "0.5.35",
  });
  card.hass = {
    entities,
    devices,
    states: {
      "sensor.charger_power": state("sensor.charger_power", "0"),
      "update.tuyaextend_amperepoint_update": update,
    },
  };
  assert.equal(card.hacsUpdateEntity(), update);
});

test("a necessary DOM replacement preserves scroll, details and an edited field", () => {
  const originalDocument = globalThis.document;
  const originalRequest = globalThis.requestAnimationFrame;
  const frames = [];
  globalThis.requestAnimationFrame = (callback) => {
    frames.push(callback);
    return frames.length;
  };

  const page = { scrollTop: 640, scrollLeft: 3 };
  const scroller = { scrollTop: 420, scrollLeft: 7, parentNode: null };
  const oldDetails = {
    dataset: { renderKey: "planner-editor" },
    open: true,
  };
  const oldInput = {
    dataset: { renderKey: "planner-0-start" },
    value: "18:37",
    selectionStart: 2,
    selectionEnd: 5,
    selectionDirection: "forward",
  };
  const oldTable = {
    dataset: { renderKey: "raw-table-scroll" },
    scrollTop: 12,
    scrollLeft: 180,
  };
  globalThis.document = { activeElement: oldInput, scrollingElement: page };

  try {
    const card = new Card();
    card.parentNode = scroller;
    card.style = { minHeight: "12px" };
    card.offsetHeight = 900;
    let renderedElements = [oldDetails, oldInput, oldTable];
    card.contains = (element) => renderedElements.includes(element);
    card.querySelectorAll = (selector) => {
      if (selector === "details[data-render-key]") {
        return renderedElements.filter((element) => "open" in element);
      }
      if (selector === "[data-render-key]") return renderedElements;
      return [];
    };

    const snapshot = card.beginDomReplacement();
    assert.equal(card.style.minHeight, "900px", "the old card height prevents layout collapse");

    page.scrollTop = 0;
    page.scrollLeft = 0;
    scroller.scrollTop = 0;
    scroller.scrollLeft = 0;
    let focused = false;
    let selection = null;
    const newDetails = {
      dataset: { renderKey: "planner-editor" },
      open: false,
    };
    const newInput = {
      dataset: { renderKey: "planner-0-start" },
      value: "18:00",
      focus: () => {
        focused = true;
      },
      setSelectionRange: (...args) => {
        selection = args;
      },
    };
    const newTable = {
      dataset: { renderKey: "raw-table-scroll" },
      scrollTop: 0,
      scrollLeft: 0,
    };
    renderedElements = [newDetails, newInput, newTable];

    card.completeDomReplacement(snapshot);
    assert.equal(page.scrollTop, 640);
    assert.equal(page.scrollLeft, 3);
    assert.equal(scroller.scrollTop, 420);
    assert.equal(scroller.scrollLeft, 7);
    assert.equal(newDetails.open, true, "expanded diagnostics/planner state must survive");
    assert.equal(newInput.value, "18:37", "an unsaved planner edit must not be erased");
    assert.equal(newTable.scrollTop, 12);
    assert.equal(newTable.scrollLeft, 180, "raw DP horizontal scroll must survive");
    assert.equal(focused, true);
    assert.deepEqual(selection, [2, 5, "forward"]);
    assert.equal(frames.length, 1);

    // Browsers can clamp scroll once more when the new layout is committed.
    // The next-frame restoration is the final guard against the reported jump.
    page.scrollTop = 0;
    scroller.scrollTop = 0;
    newTable.scrollLeft = 0;
    frames.shift()();
    assert.equal(page.scrollTop, 640);
    assert.equal(scroller.scrollTop, 420);
    assert.equal(newTable.scrollLeft, 180);
    assert.equal(card.style.minHeight, "12px");
  } finally {
    if (originalDocument === undefined) delete globalThis.document;
    else globalThis.document = originalDocument;
    if (originalRequest === undefined) delete globalThis.requestAnimationFrame;
    else globalThis.requestAnimationFrame = originalRequest;
  }
});

test("disconnect cancels queued rendering and delayed restoration", () => {
  const originalRequest = globalThis.requestAnimationFrame;
  const originalCancel = globalThis.cancelAnimationFrame;
  let nextFrame = 0;
  const cancelled = [];
  globalThis.requestAnimationFrame = () => {
    nextFrame += 1;
    return nextFrame;
  };
  globalThis.cancelAnimationFrame = (frame) => cancelled.push(frame);

  try {
    const card = new Card();
    card.style = { minHeight: "640px" };
    card._renderPreviousMinHeight = "";
    card._pendingCharging = true;
    card._pendingCurrentLimit = 16;
    card._pendingChargingMode = "charge_now";
    card.requestRender();
    card._renderRestoreFrame = 2;

    card.disconnectedCallback();
    assert.deepEqual(cancelled, [1, 2]);
    assert.equal(card._renderQueued, false);
    assert.equal(card._renderFrame, null);
    assert.equal(card._renderRestoreFrame, null);
    assert.equal(card.style.minHeight, "");
    assert.equal(card._pendingCharging, null);
    assert.equal(card._pendingCurrentLimit, null);
    assert.equal(card._pendingChargingMode, null);
  } finally {
    if (originalRequest === undefined) delete globalThis.requestAnimationFrame;
    else globalThis.requestAnimationFrame = originalRequest;
    if (originalCancel === undefined) delete globalThis.cancelAnimationFrame;
    else globalThis.cancelAnimationFrame = originalCancel;
  }
});
