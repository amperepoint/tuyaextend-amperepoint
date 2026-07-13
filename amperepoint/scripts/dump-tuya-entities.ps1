$ErrorActionPreference = "Stop"

@'
import json
from pathlib import Path

entity_registry = Path("/config/.storage/core.entity_registry")
device_registry = Path("/config/.storage/core.device_registry")

if not entity_registry.exists():
    print("Entity registry not found")
    raise SystemExit(0)

entities = json.loads(entity_registry.read_text()).get("data", {}).get("entities", [])
devices = {}
if device_registry.exists():
    devices = {
        item.get("id"): item
        for item in json.loads(device_registry.read_text()).get("data", {}).get("devices", [])
    }

for entity in entities:
    if entity.get("platform") != "tuya":
        continue
    device = devices.get(entity.get("device_id"), {})
    print(json.dumps({
        "entity_id": entity.get("entity_id"),
        "name": entity.get("name"),
        "original_name": entity.get("original_name"),
        "device_name": device.get("name_by_user") or device.get("name"),
        "device_model": device.get("model"),
        "disabled_by": entity.get("disabled_by"),
    }, ensure_ascii=False))
'@ | docker exec -i homeassistant python3 -
