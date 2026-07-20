from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "tuyaextend_amperepoint"


class ReleaseMetadataTests(unittest.TestCase):
    def test_local_brand_icons_are_bundled(self) -> None:
        for filename in ("icon.png", "icon@2x.png"):
            icon = COMPONENT / "brand" / filename
            self.assertTrue(icon.is_file())
            self.assertEqual(icon.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

    def test_integration_is_listed_as_a_device(self) -> None:
        manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["integration_type"], "device")

    def test_backend_and_dashboard_versions_match_manifest(self) -> None:
        manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
        const_source = (COMPONENT / "const.py").read_text(encoding="utf-8")
        card_source = (COMPONENT / "frontend" / "amperepoint-q22-card.js").read_text(
            encoding="utf-8"
        )

        backend_version = re.search(
            r'^VERSION = "([^"]+)"$', const_source, re.MULTILINE
        )
        dashboard_version = re.search(
            r'^const AP_Q22_DASHBOARD_VERSION = "([^"]+)";',
            card_source,
            re.MULTILINE,
        )

        self.assertIsNotNone(backend_version)
        self.assertIsNotNone(dashboard_version)
        self.assertEqual(backend_version.group(1), manifest["version"])
        self.assertEqual(dashboard_version.group(1), manifest["version"])


if __name__ == "__main__":
    unittest.main()
