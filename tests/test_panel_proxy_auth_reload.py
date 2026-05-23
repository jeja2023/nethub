import sys
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


ROOT = Path(__file__).resolve().parents[1]
PANEL_DIR = ROOT / "panel"
if str(PANEL_DIR) not in sys.path:
    sys.path.insert(0, str(PANEL_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from panel import main as panel_main


def config_with_users(users=None):
    inbound = {
        "type": "http",
        "tag": "http-in",
        "listen": "0.0.0.0",
        "listen_port": 2080,
    }
    if users is not None:
        inbound["users"] = users
    return {"inbounds": [inbound], "outbounds": []}


class ProxyAuthReloadTests(unittest.TestCase):
    def test_reload_uses_force_query_and_path_body(self) -> None:
        response = MagicMock()
        response.is_success = True

        with patch.object(panel_main, "_sync_clash_api_request", return_value=response) as req:
            self.assertTrue(panel_main._reload_singbox_config_sync(current_secret="old", next_secret="new"))

        req.assert_called_once()
        args, kwargs = req.call_args
        self.assertEqual(args[:2], ("PUT", "/configs?force=true"))
        self.assertEqual(kwargs["json_body"], {"path": panel_main._SINGBOX_CONFIG_PATH})

    def test_reload_fallback_sends_payload_as_string(self) -> None:
        first = MagicMock()
        first.is_success = False
        first.status_code = 500
        first.text = "bad"
        second = MagicMock()
        second.is_success = True

        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "config.json"
            cfg.write_text('{"outbounds":[]}', encoding="utf-8")
            with (
                patch.object(panel_main, "CONFIG_FILE", cfg),
                patch.object(panel_main, "_sync_clash_api_request", side_effect=[first, second]) as req,
            ):
                self.assertTrue(panel_main._reload_singbox_config_sync(current_secret="old", next_secret="new"))

        second_call = req.call_args_list[1]
        self.assertEqual(second_call.args[:2], ("PUT", "/configs?force=true"))
        payload = second_call.kwargs["json_body"]["payload"]
        self.assertIsInstance(payload, str)
        self.assertIn('"outbounds"', payload)

    def test_clash_headers_uses_runtime_secret_from_environment(self) -> None:
        old = os.environ.get("CLASH_API_SECRET")
        os.environ["CLASH_API_SECRET"] = "runtime-secret"
        try:
            self.assertEqual(panel_main.clash_headers(), {"Authorization": "Bearer runtime-secret"})
        finally:
            if old is None:
                os.environ.pop("CLASH_API_SECRET", None)
            else:
                os.environ["CLASH_API_SECRET"] = old

    def test_no_auth_change_does_not_close_connections(self) -> None:
        old = config_with_users([{"username": "u", "password": "p"}])
        new = config_with_users([{"username": "u", "password": "p"}])

        self.assertFalse(panel_main._proxy_auth_change_requires_connection_close(old, new))

    def test_enabling_proxy_auth_closes_existing_connections(self) -> None:
        old = config_with_users()
        new = config_with_users([{"username": "u", "password": "p"}])

        self.assertTrue(panel_main._proxy_auth_change_requires_connection_close(old, new))

    def test_changing_proxy_credentials_closes_existing_connections(self) -> None:
        old = config_with_users([{"username": "u", "password": "old"}])
        new = config_with_users([{"username": "u", "password": "new"}])

        self.assertTrue(panel_main._proxy_auth_change_requires_connection_close(old, new))

    def test_disabling_proxy_auth_closes_existing_connections(self) -> None:
        old = config_with_users([{"username": "u", "password": "p"}])
        new = config_with_users()

        self.assertTrue(panel_main._proxy_auth_change_requires_connection_close(old, new))


class ProxyAuthStartupCleanupTests(unittest.IsolatedAsyncioTestCase):
    def _mock_api_ready(self):
        """模拟 Clash API 已就绪的响应"""
        mock_resp = unittest.mock.MagicMock()
        mock_resp.status_code = 200
        return mock_resp

    async def test_startup_closes_connections_when_proxy_auth_is_required(self) -> None:
        with (
            patch.object(panel_main, "_ensure_config_auth_matches_env", return_value=False),
            patch.object(panel_main, "_http_proxy_auth_required", return_value=True),
            patch.object(panel_main, "_close_proxy_connections_sync", return_value=True) as close_mock,
            patch.object(panel_main, "_sync_clash_api_request", return_value=self._mock_api_ready()),
            patch.object(panel_main.asyncio, "sleep", new=AsyncMock()),
        ):
            await panel_main._enforce_proxy_auth_connections_on_startup()

        # 多轮清理，应调用多次
        self.assertGreaterEqual(close_mock.call_count, 1)

    async def test_startup_skips_cleanup_when_proxy_auth_is_not_required(self) -> None:
        with (
            patch.object(panel_main, "_ensure_config_auth_matches_env", return_value=False),
            patch.object(panel_main, "_http_proxy_auth_required", return_value=False),
            patch.object(panel_main, "_close_proxy_connections_sync", return_value=True) as close_mock,
            patch.object(panel_main, "_sync_clash_api_request", return_value=self._mock_api_ready()),
            patch.object(panel_main.asyncio, "sleep", new=AsyncMock()),
        ):
            await panel_main._enforce_proxy_auth_connections_on_startup()

        close_mock.assert_not_called()

    async def test_startup_skips_when_api_not_ready(self) -> None:
        with (
            patch.object(panel_main, "_http_proxy_auth_required", return_value=True),
            patch.object(panel_main, "_close_proxy_connections_sync", return_value=True) as close_mock,
            patch.object(panel_main, "_sync_clash_api_request", return_value=None),
            patch.object(panel_main.asyncio, "sleep", new=AsyncMock()),
        ):
            await panel_main._enforce_proxy_auth_connections_on_startup()

        # API 未就绪时不应尝试断开连接
        close_mock.assert_not_called()

    async def test_startup_patches_config_and_reloads_when_auth_missing(self) -> None:
        """环境变量已设置鉴权但 config.json 中缺少 users 时，应补写并重载内核"""
        with (
            patch.object(panel_main, "_ensure_config_auth_matches_env", return_value=True) as patch_mock,
            patch.object(panel_main, "_reload_singbox_config_sync", return_value=True) as reload_mock,
            patch.object(panel_main, "_http_proxy_auth_required", return_value=True),
            patch.object(panel_main, "_close_proxy_connections_sync", return_value=True) as close_mock,
            patch.object(panel_main, "_sync_clash_api_request", return_value=self._mock_api_ready()),
            patch.object(panel_main.asyncio, "sleep", new=AsyncMock()),
        ):
            await panel_main._enforce_proxy_auth_connections_on_startup()

        # 配置被修正后应触发重载
        patch_mock.assert_called_once()
        reload_mock.assert_called_once()
        # 重载后应断开连接
        self.assertGreaterEqual(close_mock.call_count, 1)


if __name__ == "__main__":
    unittest.main()
