from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "tuyaextend_amperepoint"
NAME = "TuyaExtend AmperePoint"
VERSION = "0.2.0"

PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
]

DEFAULT_SCAN_INTERVAL = timedelta(seconds=15)
DEFAULT_TARIFF_VALUE = 1.20
DEFAULT_CURRENCY = "PLN"
DEFAULT_COMPLETE_POWER_THRESHOLD_KW = 0.25
DEFAULT_COMPLETE_IDLE_MINUTES = 3
DEFAULT_CREATE_DASHBOARD = True

CONF_MODEL = "model"
CONF_SOURCE_DEVICE_ID = "source_device_id"
CONF_SOURCE_INTEGRATION = "source_integration"
CONF_SOURCE_NAME = "source_name"
CONF_AUTO_DISCOVERED = "auto_discovered"
CONF_SOURCE_RAW_DP = "source_raw_dp"
CONF_SOURCE_STATUS = "source_status"
CONF_SOURCE_CONNECTED = "source_connected"
CONF_SOURCE_POWER = "source_power"
CONF_SOURCE_SESSION_ENERGY = "source_session_energy"
CONF_SOURCE_TOTAL_ENERGY = "source_total_energy"
CONF_SOURCE_LAST_SESSION_ENERGY = "source_last_session_energy"
CONF_SESSION_ENERGY_MODE = "session_energy_mode"
CONF_SOURCE_CURRENT_LIMIT = "source_current_limit"
CONF_SOURCE_CHARGE_SWITCH = "source_charge_switch"
CONF_SOURCE_ERROR = "source_error"
CONF_SOURCE_TEMPERATURE = "source_temperature"
CONF_TARIFF_VALUE = "tariff_value"
CONF_TARIFF_ENTITY = "tariff_entity"
CONF_CURRENCY = "currency"
CONF_COMPLETE_POWER_THRESHOLD = "complete_power_threshold_kw"
CONF_COMPLETE_IDLE_MINUTES = "complete_idle_minutes"
CONF_CREATE_DASHBOARD = "create_dashboard"

CONF_SOURCE_VOLTAGE_L1 = "source_voltage_l1"
CONF_SOURCE_VOLTAGE_L2 = "source_voltage_l2"
CONF_SOURCE_VOLTAGE_L3 = "source_voltage_l3"
CONF_SOURCE_CURRENT_L1 = "source_current_l1"
CONF_SOURCE_CURRENT_L2 = "source_current_l2"
CONF_SOURCE_CURRENT_L3 = "source_current_l3"
CONF_SOURCE_POWER_L1 = "source_power_l1"
CONF_SOURCE_POWER_L2 = "source_power_l2"
CONF_SOURCE_POWER_L3 = "source_power_l3"
CONF_SOURCE_PHASE_A = "source_phase_a"
CONF_SOURCE_PHASE_B = "source_phase_b"
CONF_SOURCE_PHASE_C = "source_phase_c"

SESSION_ENERGY_MODE_AUTO = "auto"
SESSION_ENERGY_MODE_SESSION_ENTITY = "session_entity"
SESSION_ENERGY_MODE_TOTAL_DELTA = "total_delta"
SESSION_ENERGY_MODE_POWER_INTEGRATION = "power_integration"

SESSION_ENERGY_MODES = {
    SESSION_ENERGY_MODE_AUTO: "Auto",
    SESSION_ENERGY_MODE_SESSION_ENTITY: "Session energy entity",
    SESSION_ENERGY_MODE_TOTAL_DELTA: "Total energy delta",
    SESSION_ENERGY_MODE_POWER_INTEGRATION: "Power integration",
}

PHASE_VOLTAGE_KEYS = (
    CONF_SOURCE_VOLTAGE_L1,
    CONF_SOURCE_VOLTAGE_L2,
    CONF_SOURCE_VOLTAGE_L3,
)
PHASE_CURRENT_KEYS = (
    CONF_SOURCE_CURRENT_L1,
    CONF_SOURCE_CURRENT_L2,
    CONF_SOURCE_CURRENT_L3,
)
PHASE_POWER_KEYS = (
    CONF_SOURCE_POWER_L1,
    CONF_SOURCE_POWER_L2,
    CONF_SOURCE_POWER_L3,
)
PHASE_RAW_KEYS = (
    CONF_SOURCE_PHASE_A,
    CONF_SOURCE_PHASE_B,
    CONF_SOURCE_PHASE_C,
)

FRONTEND_URL = "/tuyaextend_amperepoint/frontend"
FRONTEND_MODULE = f"{FRONTEND_URL}/amperepoint-q22-card.js"
