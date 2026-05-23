import unittest
from unittest.mock import patch

import httpx
from fastapi import HTTPException

from panel import main as panel_main


class PanelUrlValidationTests(unittest.IsolatedAsyncioTestCase):
    def test_rejects_localhost_subscription_url(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            panel_main._validate_subscription_url("http://localhost/sub")

        self.assertEqual(ctx.exception.status_code, 400)

    def test_rejects_private_dns_resolution(self) -> None:
        with patch.object(
            panel_main.socket,
            "getaddrinfo",
            return_value=[(None, None, None, None, ("10.0.0.5", 443))],
        ):
            with self.assertRaises(HTTPException) as ctx:
                panel_main._validate_subscription_url("https://example.com/sub")

        self.assertEqual(ctx.exception.status_code, 400)

    async def test_revalidates_redirect_target(self) -> None:
        request = httpx.Request("GET", "https://example.com/sub")
        response = httpx.Response(
            302,
            headers={"location": "http://127.0.0.1/private"},
            request=request,
        )

        async def fake_get(*args, **kwargs):
            return response

        with patch.object(httpx.AsyncClient, "get", new=fake_get):
            with self.assertRaises(HTTPException) as ctx:
                await panel_main._fetch_subscription_content("https://example.com/sub")

        self.assertEqual(ctx.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
