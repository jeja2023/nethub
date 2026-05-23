import tempfile
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from panel import main as panel_main
from core.vault_store import decrypt_vault_file, encrypt_vault_file


class VaultImportMergeTests(unittest.TestCase):
    def test_rebuild_persists_new_clash_secret_after_successful_reload(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td)
            vaults_dir = data_dir / "vaults"
            vault_name = "default"
            vault_path = vaults_dir / f"{vault_name}.enc"
            password = "secret"
            encrypt_vault_file(
                ["vless://00000000-0000-0000-0000-000000000000@example.com:443?type=tcp#node"],
                password,
                vault_path,
            )

            old_secret = os.environ.get("CLASH_API_SECRET")
            os.environ["CLASH_API_SECRET"] = "old-secret"
            try:
                with (
                    patch.object(panel_main, "DATA_DIR", data_dir),
                    patch.object(panel_main, "VAULTS_DIR", vaults_dir),
                    patch.object(panel_main, "VAULTS_INDEX", vaults_dir / "index.json"),
                    patch.object(panel_main, "_LEGACY_VAULT_FILE", data_dir / "vault.enc"),
                    patch.object(panel_main, "CONFIG_FILE", data_dir / "config.json"),
                    patch.object(panel_main, "_reload_singbox_config_sync", return_value=True),
                ):
                    panel_main._ensure_vault_record(vault_name)
                    panel_main._rebuild_config_from_vaults(password, clash_secret="new-secret")

                self.assertEqual(os.environ.get("CLASH_API_SECRET"), "new-secret")
            finally:
                if old_secret is None:
                    os.environ.pop("CLASH_API_SECRET", None)
                else:
                    os.environ["CLASH_API_SECRET"] = old_secret

    def test_manual_import_appends_existing_vault_nodes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td)
            vaults_dir = data_dir / "vaults"
            vault_name = "default"
            vault_path = vaults_dir / f"{vault_name}.enc"
            existing = [f"vless://00000000-0000-0000-0000-000000000000@example{i}.com:443?type=tcp#old-{i}" for i in range(47)]
            incoming = ["vless://00000000-0000-0000-0000-000000000000@new.example.com:443?type=tcp#new"]
            password = "secret"
            encrypt_vault_file(existing, password, vault_path)

            with (
                patch.object(panel_main, "DATA_DIR", data_dir),
                patch.object(panel_main, "VAULTS_DIR", vaults_dir),
                patch.object(panel_main, "VAULTS_INDEX", vaults_dir / "index.json"),
                patch.object(panel_main, "_LEGACY_VAULT_FILE", data_dir / "vault.enc"),
                patch.object(panel_main, "_rebuild_config_from_vaults", return_value=48),
            ):
                node_count, duplicate_count, total = panel_main._import_vault_urls(vault_name, password, incoming)

                urls = decrypt_vault_file(vault_path, password)
                vaults = panel_main._list_vaults()

        self.assertEqual(node_count, 48)
        self.assertEqual(duplicate_count, 0)
        self.assertEqual(total, 48)
        self.assertEqual(len(urls), 48)
        self.assertEqual(urls[-1], incoming[0])
        self.assertEqual(vaults[0]["name"], vault_name)
        self.assertTrue(vaults[0]["enabled"])
        self.assertEqual(vaults[0]["node_count"], 48)

    def test_replace_mode_keeps_delete_and_edit_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td)
            vaults_dir = data_dir / "vaults"
            vault_name = "default"
            vault_path = vaults_dir / f"{vault_name}.enc"
            password = "secret"
            encrypt_vault_file(["vless://old@example.com:443?type=tcp#old"], password, vault_path)

            with (
                patch.object(panel_main, "DATA_DIR", data_dir),
                patch.object(panel_main, "VAULTS_DIR", vaults_dir),
                patch.object(panel_main, "VAULTS_INDEX", vaults_dir / "index.json"),
                patch.object(panel_main, "_LEGACY_VAULT_FILE", data_dir / "vault.enc"),
                patch.object(panel_main, "_rebuild_config_from_vaults", return_value=1),
            ):
                panel_main._import_vault_urls(
                    vault_name,
                    password,
                    ["vless://new@example.com:443?type=tcp#new"],
                    replace=True,
                )
                urls = decrypt_vault_file(vault_path, password)

        self.assertEqual(urls, ["vless://new@example.com:443?type=tcp#new"])


if __name__ == "__main__":
    unittest.main()
