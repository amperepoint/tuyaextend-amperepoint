param(
    [Parameter(Mandatory = $true)]
    [string] $DeviceId
)

$ErrorActionPreference = "Stop"

@"
import json
from pathlib import Path

from homeassistant.components.tuya.const import TUYA_CLIENT_ID
from tuya_sharing import Manager

device_id = "$DeviceId"
entries = json.loads(Path("/config/.storage/core.config_entries").read_text()).get("data", {}).get("entries", [])
entry = next(
    item
    for item in entries
    if item.get("domain") == "tuya" and not item.get("disabled_by")
)

manager = Manager(
    TUYA_CLIENT_ID,
    entry["data"]["user_code"],
    entry["data"]["terminal_id"],
    entry["data"]["endpoint"],
    entry["data"]["token_info"],
)
manager.update_device_cache()
device = manager.device_map.get(device_id)
if device is None:
    print(f"Device not found: {device_id}")
    print("Available device IDs:")
    for available_id, available_device in manager.device_map.items():
        print(f"- {available_id}: {available_device.name} ({available_device.product_name})")
    raise SystemExit(1)

print(json.dumps(
    {
        "id": device.id,
        "name": device.name,
        "category": device.category,
        "product_id": device.product_id,
        "product_name": device.product_name,
        "online": device.online,
        "status": device.status,
        "status_range": {
            code: {
                "type": getattr(item, "type", None),
                "values": getattr(item, "values", None),
            }
            for code, item in (device.status_range or {}).items()
        },
        "function": {
            code: {
                "type": getattr(item, "type", None),
                "values": getattr(item, "values", None),
            }
            for code, item in (device.function or {}).items()
        },
        "local_strategy": {
            dp_id: item.get("status_code")
            for dp_id, item in (device.local_strategy or {}).items()
        },
    },
    ensure_ascii=False,
    indent=2,
    default=str,
))
"@ | docker exec -i homeassistant python3 -
