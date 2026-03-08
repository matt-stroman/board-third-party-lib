"""Focused unit coverage for migration-era developer CLI helpers."""

from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys
import tempfile
import unittest


def load_dev_cli_module():
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    module_path = repo_root / "scripts" / "dev.py"
    spec = importlib.util.spec_from_file_location("board_enthusiasts_dev_cli", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load scripts/dev.py for testing.")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


dev = load_dev_cli_module()


class DevCliMigrationHelperTests(unittest.TestCase):
    """Covers the pure helper logic added for Wave 1 migration scaffolding."""

    def test_is_local_supabase_url_reports_expected_values(self) -> None:
        self.assertTrue(dev.is_local_http_url("http://127.0.0.1:54321"))
        self.assertTrue(dev.is_local_http_url("https://localhost:7277"))
        self.assertFalse(dev.is_local_http_url("https://staging.boardenthusiasts.com"))

    def test_config_from_args_keeps_root_relative_migration_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = argparse.Namespace(
                compose_file="backend/docker-compose.yml",
                postgres_container_name="board_tpl_postgres",
                postgres_user="board_tpl_user",
                postgres_database="board_tpl",
                keycloak_container_name="board_tpl_keycloak",
                keycloak_ready_url="https://localhost:8443/realms/board/protocol/openid-connect/auth",
                backend_project="backend/src/Board.ThirdPartyLibrary.Api/Board.ThirdPartyLibrary.Api.csproj",
                backend_solution="backend/Board.ThirdPartyLibrary.Backend.sln",
            )

            config = dev.config_from_args(args, repo_root)

            self.assertEqual("apps/spa", config.migration_spa_root)
            self.assertEqual("apps/workers-api", config.migration_workers_root)
            self.assertEqual("supabase", config.supabase_root)

    def test_build_migration_workspace_command_uses_workspace_name(self) -> None:
        command = dev.build_workspace_npm_command(
            script_name="dev",
            workspace_name="@board-enthusiasts/spa",
        )

        self.assertEqual(
            ["npm", "run", "dev", "--workspace", "@board-enthusiasts/spa"],
            command,
        )

    def test_parse_env_assignments_unquotes_supabase_status_values(self) -> None:
        parsed = dev.parse_env_assignments(
            'API_URL="http://127.0.0.1:54321"\nANON_KEY="anon"\nSERVICE_ROLE_KEY="service"\n'
        )

        self.assertEqual("http://127.0.0.1:54321", parsed["API_URL"])
        self.assertEqual("anon", parsed["ANON_KEY"])
        self.assertEqual("service", parsed["SERVICE_ROLE_KEY"])

    def test_build_supabase_bearer_headers_uses_apikey_and_bearer(self) -> None:
        headers = dev.build_supabase_bearer_headers(api_key="service-role-key")

        self.assertEqual("service-role-key", headers["apikey"])
        self.assertEqual("Bearer service-role-key", headers["authorization"])
        self.assertEqual("application/json", headers["accept"])

    def test_has_current_migration_workspace_dependencies_tracks_lockfile_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = argparse.Namespace(
                compose_file="backend/docker-compose.yml",
                postgres_container_name="board_tpl_postgres",
                postgres_user="board_tpl_user",
                postgres_database="board_tpl",
                keycloak_container_name="board_tpl_keycloak",
                keycloak_ready_url="https://localhost:8443/realms/board/protocol/openid-connect/auth",
                backend_project="backend/src/Board.ThirdPartyLibrary.Api/Board.ThirdPartyLibrary.Api.csproj",
                backend_solution="backend/Board.ThirdPartyLibrary.Backend.sln",
            )
            config = dev.config_from_args(args, repo_root)

            (repo_root / "package.json").write_text('{"name":"board-enthusiasts"}', encoding="utf-8")
            (repo_root / "package-lock.json").write_text('{"lockfileVersion":3}', encoding="utf-8")
            (repo_root / "node_modules").mkdir()
            (repo_root / "node_modules" / "tsx").mkdir(parents=True)
            (repo_root / "node_modules" / "tsx" / "package.json").write_text("{}", encoding="utf-8")
            (repo_root / "node_modules" / "@supabase" / "supabase-js").mkdir(parents=True)
            (repo_root / "node_modules" / "@supabase" / "supabase-js" / "package.json").write_text("{}", encoding="utf-8")
            (repo_root / "node_modules" / "@playwright" / "test").mkdir(parents=True)
            (repo_root / "node_modules" / "@playwright" / "test" / "package.json").write_text("{}", encoding="utf-8")
            (repo_root / "node_modules" / ".bin").mkdir(parents=True)
            (repo_root / "node_modules" / ".bin" / "tsx.cmd").write_text("", encoding="utf-8")
            (repo_root / "node_modules" / ".bin" / "playwright.cmd").write_text("", encoding="utf-8")

            self.assertFalse(dev.has_current_migration_workspace_dependencies(config))

            dev.record_migration_workspace_dependencies(config)

            self.assertTrue(dev.has_current_migration_workspace_dependencies(config))

            (repo_root / "package-lock.json").write_text('{"lockfileVersion":4}', encoding="utf-8")

            self.assertFalse(dev.has_current_migration_workspace_dependencies(config))


if __name__ == "__main__":
    unittest.main()
