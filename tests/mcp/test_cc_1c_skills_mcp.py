from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mcp_bridge import cc_1c_skills_server as bridge


def write_project(root: Path) -> Path:
    project = root / ".v8-project.json"
    project.write_text(
        json.dumps(
            {
                "v8path": "C:/Program Files/BAF/8.3/bin",
                "default": "bas",
                "databases": [
                    {
                        "id": "bas",
                        "name": "Secret Shop BAS",
                        "type": "server",
                        "server": "SD-218-215-XRB",
                        "ref": "Secret Shop BAS",
                        "user": "Администратор",
                        "passwordEnv": "BAF_BAS_PASSWORD",
                        "password": "do-not-leak",
                        "aliases": ["main", "shop"],
                        "configSrc": "src/baf-config-dump",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return project


class TestCc1cSkillsMcpBridge(unittest.TestCase):
    def test_project_info_redacts_secrets(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_project(root)

            result = bridge.cc1c_project_info(workspace=str(root))

            self.assertTrue(result["ok"])
            self.assertEqual(result["default_db_id"], "bas")
            self.assertTrue(result["databases"][0]["password_present"])
            self.assertTrue(result["databases"][0]["default"])
            self.assertNotIn("password", result["databases"][0])
            self.assertEqual(result["raw_redacted"]["databases"][0]["password"], "<redacted>")
            self.assertEqual(result["raw_redacted"]["databases"][0]["passwordEnv"], "<redacted>")

    def test_db_dump_xml_preview_uses_registry_and_password_env(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_project(root)

            result = bridge.cc1c_db_dump_xml(workspace=str(root), db="shop")

            cmd = result["command"]
            self.assertTrue(result["ok"])
            self.assertFalse(result["execute"])
            self.assertIn("-InfoBaseServer", cmd)
            self.assertIn("SD-218-215-XRB", cmd)
            self.assertIn("-InfoBaseRef", cmd)
            self.assertIn("Secret Shop BAS", cmd)
            self.assertIn("-PasswordEnv", cmd)
            self.assertIn("BAF_BAS_PASSWORD", cmd)
            self.assertNotIn("do-not-leak", json.dumps(result, ensure_ascii=False))
            self.assertTrue(result["config_dir"].endswith("src/baf-config-dump"))

    def test_db_backup_sql_preview_defaults_sql_database_to_ref(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_project(root)

            result = bridge.cc1c_db_backup(
                workspace=str(root),
                db="bas",
                mode="sql",
                output_file="D:/backups/SecretShopBAS.bak",
            )

            cmd = result["command"]
            self.assertTrue(result["ok"])
            self.assertIn("-Mode", cmd)
            self.assertIn("sql", cmd)
            self.assertIn("-SqlDatabase", cmd)
            self.assertIn("Secret Shop BAS", cmd)
            self.assertNotIn("do-not-leak", json.dumps(result, ensure_ascii=False))

    def test_srv_sessions_terminate_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_project(root)

            result = bridge.cc1c_srv_sessions(
                workspace=str(root),
                db="bas",
                action="terminate",
                all_sessions=True,
                execute=False,
            )

            self.assertFalse(result["ok"])
            self.assertIn("confirmation_token", result["error"])

    def test_redact_command_hides_plain_password(self):
        cmd = ["powershell.exe", "-File", "x.ps1", "-Password", "secret", "-ClusterPwd", "secret2"]

        self.assertEqual(
            bridge._redact_command(cmd),
            [
                "powershell.exe",
                "-File",
                "x.ps1",
                "-Password",
                "<redacted>",
                "-ClusterPwd",
                "<redacted>",
            ],
        )


if __name__ == "__main__":
    unittest.main()
