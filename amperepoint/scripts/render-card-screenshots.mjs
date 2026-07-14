import { spawn } from "node:child_process";
import { once } from "node:events";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(scriptDir, "..", "..");
const fixtureUrl = pathToFileURL(path.join(scriptDir, "card-screenshot-fixture.html")).href;
const outputDir = path.join(rootDir, "amperepoint", "screenshots");
const chromePath =
  process.env.CHROME_PATH || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

const entities = {
  switch: "switch.demo_charging",
  currentLimit: "number.demo_current_limit",
  chargingMode: "select.demo_charging_mode",
  targetEnergy: "number.demo_target_energy",
  scheduleStartTime: "time.demo_schedule_start",
  scheduleEndTime: "time.demo_schedule_end",
  status: "sensor.demo_status",
  cp: "sensor.demo_connection",
  faults: "sensor.demo_faults",
  power: "sensor.demo_power",
  sessionEnergy: "sensor.demo_session_energy",
  totalEnergy: "sensor.demo_total_energy",
  lastSessionDp25: "sensor.demo_last_session",
  temperature: "sensor.demo_temperature",
  rawDp: "sensor.demo_raw_dp",
  planner: "sensor.demo_planner",
  phaseCount: "sensor.demo_phase_count",
  l1Voltage: "sensor.demo_voltage_l1",
  l2Voltage: "sensor.demo_voltage_l2",
  l3Voltage: "sensor.demo_voltage_l3",
  l1Current: "sensor.demo_current_l1",
  l2Current: "sensor.demo_current_l2",
  l3Current: "sensor.demo_current_l3",
  l1Power: "sensor.demo_power_l1",
  l2Power: "sensor.demo_power_l2",
  l3Power: "sensor.demo_power_l3",
};

const scenarios = [
  {
    file: "amperepoint-charge-now.png",
    mode: "charge_now",
    status: "Ładowanie",
    connection: "Auto podłączone / PWM",
    power: "10.84",
    session: "3.42",
    temperature: "37",
    currents: ["15.7", "15.6", "15.8"],
    powers: ["3.61", "3.58", "3.65"],
  },
  {
    file: "amperepoint-charge-energy.png",
    mode: "charge_energy",
    status: "Ładowanie",
    connection: "Auto podłączone / PWM",
    power: "7.36",
    session: "5.80",
    temperature: "35",
    currents: ["10.7", "10.5", "10.6"],
    powers: ["2.47", "2.42", "2.47"],
  },
  {
    file: "amperepoint-charge-schedule.png",
    mode: "charge_schedule",
    status: "Oczekiwanie na harmonogram",
    connection: "Auto podłączone",
    power: "0.00",
    session: "0.00",
    temperature: "29",
    currents: ["0.0", "0.0", "0.0"],
    powers: ["0.00", "0.00", "0.00"],
  },
];

function state(value, attributes = {}) {
  return { state: String(value), attributes };
}

function buildStates(scenario) {
  const rawDp = {
    forward_energy_total: 92866,
    work_state: scenario.power === "0.00" ? "charger_wait" : "charger_charging",
    charge_cur_set: 16,
    phase_a: "CN8APVAOEA==",
    phase_b: "COoAPGQOBg==",
    phase_c: "CNQAPbgOEQ==",
    power_total: Math.round(Number(scenario.power) * 1000),
    fault: 0,
    connection_state: scenario.power === "0.00" ? "controlpi_9v" : "controlpi_6v_pwm",
    work_mode: scenario.mode,
    energy_charge: 20,
    switch: true,
    local_timer: "Egc=",
    system_version: "V1.8",
    temp_current: Number(scenario.temperature),
    charge_energy_once: 1684,
    mode_set: "",
  };
  const dpIds = [1, 3, 4, 6, 7, 8, 9, 10, 13, 14, 17, 18, 19, 23, 24, 25, 33];
  const writable = new Set([
    "charge_cur_set",
    "work_mode",
    "energy_charge",
    "switch",
    "local_timer",
    "mode_set",
  ]);
  const dpMetadata = Object.fromEntries(
    Object.keys(rawDp).map((code, index) => [
      code,
      {
        dp_id: dpIds[index],
        scale: code === "power_total" ? 3 : code.includes("energy") ? 2 : 0,
        writable: writable.has(code),
      },
    ]),
  );

  return {
    [entities.switch]: state("on"),
    [entities.currentLimit]: state("16", {
      min: 6,
      max: 32,
      step: 1,
      unit_of_measurement: "A",
    }),
    [entities.chargingMode]: state(scenario.mode, {
      options: ["charge_now", "charge_energy", "charge_schedule"],
    }),
    [entities.targetEnergy]: state("20", {
      min: 1,
      max: 200,
      step: 1,
      unit_of_measurement: "kWh",
    }),
    [entities.scheduleStartTime]: state("18:00:00"),
    [entities.scheduleEndTime]: state("07:00:00"),
    [entities.status]: state(scenario.status),
    [entities.cp]: state(scenario.connection),
    [entities.faults]: state("Brak błędów"),
    [entities.power]: state(scenario.power, { unit_of_measurement: "kW" }),
    [entities.sessionEnergy]: state(scenario.session, { unit_of_measurement: "kWh" }),
    [entities.totalEnergy]: state("928.66", { unit_of_measurement: "kWh" }),
    [entities.lastSessionDp25]: state("16.84", { unit_of_measurement: "kWh" }),
    [entities.temperature]: state(scenario.temperature, { unit_of_measurement: "°C" }),
    [entities.rawDp]: state("17", { raw_dp: rawDp, dp_metadata: dpMetadata }),
    [entities.planner]: state(
      scenario.mode === "charge_now"
        ? "override_charging"
        : scenario.mode === "charge_energy"
          ? "override_charging"
          : "waiting",
      {
      config_entry_id: "demo-entry",
      enabled: true,
      windows: [
        {
          id: "weekday-night",
          days: [0, 1, 2, 3, 4],
          start: "22:15",
          end: "06:45",
          current_a: 16,
          priority: 0,
        },
        {
          id: "weekend-day",
          days: [5, 6],
          start: "10:30",
          end: "14:00",
          current_a: 12,
          priority: 0,
        },
      ],
      active_window: scenario.power === "0.00" ? null : { id: "weekday-night" },
      next_action: {
        action: scenario.power === "0.00" ? "start" : "stop",
        at: scenario.power === "0.00" ? "2026-07-15T22:15:00+02:00" : "2026-07-15T06:45:00+02:00",
        window_id: "weekday-night",
      },
      override:
        scenario.mode === "charge_now"
          ? {
              mode: "charge",
              until: "2026-07-14T23:15:00+02:00",
              duration_minutes: 30,
              current_a: 16,
            }
          : scenario.mode === "charge_energy"
            ? {
                mode: "energy",
                target_kwh: 10,
                delivered_kwh: 3.42,
                current_a: 16,
              }
            : null,
      command_status: scenario.mode === "charge_schedule" ? "pending" : "confirmed",
      pending:
        scenario.mode === "charge_schedule"
          ? {
              action: "set_current",
              expected: { current_limit_a: 12 },
              requested_at: "2026-07-14T21:42:00+02:00",
            }
          : null,
      last_confirmation: {
        action: "set_current",
        confirmed_at: "2026-07-14T21:42:00+02:00",
      },
      retry_after: null,
      }
    ),
    [entities.phaseCount]: state("3"),
    [entities.l1Voltage]: state("230", { unit_of_measurement: "V" }),
    [entities.l2Voltage]: state("229", { unit_of_measurement: "V" }),
    [entities.l3Voltage]: state("231", { unit_of_measurement: "V" }),
    [entities.l1Current]: state(scenario.currents[0], { unit_of_measurement: "A" }),
    [entities.l2Current]: state(scenario.currents[1], { unit_of_measurement: "A" }),
    [entities.l3Current]: state(scenario.currents[2], { unit_of_measurement: "A" }),
    [entities.l1Power]: state(scenario.powers[0], { unit_of_measurement: "kW" }),
    [entities.l2Power]: state(scenario.powers[1], { unit_of_measurement: "kW" }),
    [entities.l3Power]: state(scenario.powers[2], { unit_of_measurement: "kW" }),
  };
}

function connect(webSocketUrl) {
  return new Promise((resolve, reject) => {
    const socket = new WebSocket(webSocketUrl);
    socket.addEventListener("open", () => resolve(socket), { once: true });
    socket.addEventListener("error", reject, { once: true });
  });
}

function createCdp(socket) {
  let nextId = 1;
  const pending = new Map();
  socket.addEventListener("message", ({ data }) => {
    const message = JSON.parse(data);
    if (!message.id || !pending.has(message.id)) return;
    const { resolve, reject } = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) reject(new Error(message.error.message));
    else resolve(message.result);
  });
  return (method, params = {}) =>
    new Promise((resolve, reject) => {
      const id = nextId++;
      pending.set(id, { resolve, reject });
      socket.send(JSON.stringify({ id, method, params }));
    });
}

async function waitForDebugEndpoint(child) {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error("Chrome did not expose DevTools")), 10_000);
    const inspect = (chunk) => {
      const match = chunk.toString().match(/DevTools listening on (ws:\/\/\S+)/);
      if (!match) return;
      clearTimeout(timeout);
      resolve(match[1]);
    };
    child.stdout.on("data", inspect);
    child.stderr.on("data", inspect);
    child.once("error", reject);
    child.once("exit", (code) => reject(new Error(`Chrome exited early (${code})`)));
  });
}

await mkdir(outputDir, { recursive: true });
const profileDir = await mkdtemp(path.join(os.tmpdir(), "amperepoint-screenshots-"));
const chrome = spawn(
  chromePath,
  [
    "--headless=new",
    "--disable-gpu",
    "--hide-scrollbars",
    "--no-first-run",
    "--no-default-browser-check",
    "--allow-file-access-from-files",
    "--remote-debugging-port=0",
    `--user-data-dir=${profileDir}`,
    "about:blank",
  ],
  { stdio: ["ignore", "pipe", "pipe"] },
);

try {
  const browserEndpoint = await waitForDebugEndpoint(chrome);
  const port = new URL(browserEndpoint).port;
  const targets = await fetch(`http://127.0.0.1:${port}/json/list`).then((response) => response.json());
  const pageTarget = targets.find((target) => target.type === "page");
  if (!pageTarget) throw new Error("Chrome page target was not found");

  const socket = await connect(pageTarget.webSocketDebuggerUrl);
  const cdp = createCdp(socket);
  await cdp("Page.enable");
  await cdp("Runtime.enable");
  await cdp("Emulation.setDeviceMetricsOverride", {
    width: 1440,
    height: 1200,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await cdp("Page.navigate", { url: fixtureUrl });
  await new Promise((resolve) => setTimeout(resolve, 500));

  for (const scenario of scenarios) {
    const payload = JSON.stringify({ entities, states: buildStates(scenario) });
    const rendered = await cdp("Runtime.evaluate", {
      expression: `window.renderAmperepointPreview(${payload})`,
      awaitPromise: true,
      returnByValue: true,
    });
    if (rendered.exceptionDetails) {
      throw new Error(rendered.exceptionDetails.exception?.description || "Preview render failed");
    }
    const rect = rendered.result.value;
    const screenshot = await cdp("Page.captureScreenshot", {
      format: "png",
      captureBeyondViewport: true,
      fromSurface: true,
      clip: { x: rect.x, y: rect.y, width: rect.width, height: rect.height, scale: 1 },
    });
    await writeFile(path.join(outputDir, scenario.file), screenshot.data, "base64");
  }

  const auditPayload = JSON.stringify({ entities, states: buildStates(scenarios[0]) });
  await cdp("Runtime.evaluate", {
    expression: `window.renderAmperepointPreview(${auditPayload})`,
    awaitPromise: true,
  });
  const uiAudit = await cdp("Runtime.evaluate", {
    expression: `(() => {
      const card = document.querySelector("amperepoint-q22-card");
      const initialActual = card.querySelector(".planner-state")?.textContent.trim();
      card.querySelector(".planner-enabled")?.click();
      const result = {
        actualStateStayedVisible: card.querySelector(".planner-state")?.textContent.trim() === initialActual,
        draftChanged: card.querySelector(".switch-copy strong")?.textContent.includes("wyłączony"),
        dirtyFeedbackVisible: Boolean(card.querySelector(".planner-savebar.dirty")),
        saveEnabled: card.querySelector(".planner-save")?.disabled === false,
        selectedDayIsPressed: card.querySelector(".day-chip.selected")?.getAttribute("aria-pressed") === "true",
        activeOverrideIsPressed: card.querySelector("[data-planner-override].active")?.getAttribute("aria-pressed") === "true",
      };
      card.querySelector(".planner-discard")?.click();
      result.discardRestoredDraft = card.querySelector(".planner-enabled")?.checked === true;
      for (let index = 0; index < 7; index += 1) {
        const selected = card.querySelector('.planner-window[data-window="0"] .day-chip.selected');
        if (!selected) break;
        selected.click();
      }
      result.invalidDaysExplained = Boolean(card.querySelector('.planner-window[data-window="0"] .planner-row-error'));
      result.invalidDraftCannotSave = card.querySelector(".planner-save")?.disabled === true;
      card.querySelector(".planner-discard")?.click();
      return result;
    })()`,
    returnByValue: true,
  });
  const failedAudit = Object.entries(uiAudit.result.value).filter(([, passed]) => !passed);
  if (failedAudit.length) {
    throw new Error(`Planner UI audit failed: ${failedAudit.map(([name]) => name).join(", ")}`);
  }

  await cdp("Emulation.setDeviceMetricsOverride", {
    width: 420,
    height: 1600,
    deviceScaleFactor: 1,
    mobile: true,
  });
  const mobilePayload = JSON.stringify({ entities, states: buildStates(scenarios[0]) });
  const mobileRendered = await cdp("Runtime.evaluate", {
    expression: `window.renderAmperepointPreview(${mobilePayload})`,
    awaitPromise: true,
    returnByValue: true,
  });
  if (mobileRendered.exceptionDetails) {
    throw new Error(mobileRendered.exceptionDetails.exception?.description || "Mobile preview render failed");
  }
  const mobileRect = mobileRendered.result.value;
  const mobileScreenshot = await cdp("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: true,
    fromSurface: true,
    clip: { x: mobileRect.x, y: mobileRect.y, width: mobileRect.width, height: mobileRect.height, scale: 1 },
  });
  await writeFile(path.join(outputDir, "amperepoint-planner-mobile.png"), mobileScreenshot.data, "base64");

  socket.close();
} finally {
  if (chrome.exitCode === null) {
    chrome.kill();
    await once(chrome, "exit");
  }
  await rm(profileDir, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 });
}

console.log(`Rendered ${scenarios.length + 1} screenshots to ${outputDir}`);
