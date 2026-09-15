"""Real HTTP transport checks; run inside the bundled Home Assistant image."""

import unittest
from unittest.mock import patch

from support import load_integration_module

usage = load_integration_module("usage_reporting")
try:
    from aiohttp import web
except ImportError:
    web = None


@unittest.skipIf(web is None, "aiohttp is supplied by Home Assistant")
class UsageHTTPTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.status = 204
        self.ack = "accepted"
        self.requests = []

        async def receive(request):
            self.requests.append(request)
            headers = {"X-AmperePoint-Usage": self.ack}
            if self.status == 302:
                headers["Location"] = "/redirected"
            return web.Response(status=self.status, headers=headers)

        app = web.Application()
        app.router.add_get("/{path:.*}", receive)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        self.endpoint = patch.object(usage, "ENDPOINT", f"http://127.0.0.1:{port}/activation")
        self.endpoint.start()

    async def asyncTearDown(self):
        self.endpoint.stop()
        await self.runner.cleanup()

    async def test_minimal_payload_and_acknowledgement(self):
        self.assertTrue(await usage._send("a" * 32, "1.0"))
        request = self.requests[0]
        self.assertEqual(dict(request.query), {"installation": "a" * 32, "version": "1.0"})
        self.assertNotIn("Cookie", request.headers)
        self.assertNotIn("Authorization", request.headers)
        self.assertNotIn("Referer", request.headers)
        self.assertEqual(request.headers["Cache-Control"], "no-store")

    async def test_redirect_is_not_followed_or_acknowledged(self):
        self.status = 302
        self.assertFalse(await usage._send("a" * 32, "1.0"))
        self.assertEqual(len(self.requests), 1)

    async def test_error_login_page_or_missing_ack_is_not_success(self):
        for self.status, self.ack in [(500, "accepted"), (503, "accepted"), (200, "accepted"), (204, "")]:
            self.assertFalse(await usage._send("a" * 32, "1.0"))
