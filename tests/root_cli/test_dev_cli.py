"""Focused unit coverage for migration-era developer CLI helpers."""

from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys
import tempfile
import unittest
from unittest import mock


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

    @staticmethod
    def create_args() -> argparse.Namespace:
        """Create a minimal argument namespace for config construction."""

        return argparse.Namespace()

    def test_is_local_supabase_url_reports_expected_values(self) -> None:
        self.assertTrue(dev.is_local_http_url("http://127.0.0.1:54321"))
        self.assertTrue(dev.is_local_http_url("https://localhost:7277"))
        self.assertFalse(dev.is_local_http_url("https://staging.boardenthusiasts.com"))

    def test_config_from_args_keeps_root_relative_migration_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()

            config = dev.config_from_args(args, repo_root)

            self.assertEqual("apps/spa", config.migration_spa_root)
            self.assertEqual("backend/apps/workers-api", config.migration_workers_root)
            self.assertEqual("backend/supabase", config.supabase_root)

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
            args = self.create_args()
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

    def test_api_test_parser_defaults_to_local_workers_base_url(self) -> None:
        parser = dev.build_parser()

        args = parser.parse_args(["api-test"])

        self.assertEqual("http://127.0.0.1:8787", args.base_url)
        self.assertFalse(args.start_workers)
        self.assertEqual(dev.LOCAL_SEED_DEVELOPER_EMAIL, args.developer_email)
        self.assertEqual(dev.LOCAL_SEED_MODERATOR_EMAIL, args.moderator_email)

    def test_run_api_contract_tests_starts_workers_and_injects_seeded_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            api_root = repo_root / "api"
            collection_path = api_root / "postman" / "collections" / "board-enthusiasts-api.contract-tests.postman_collection.json"
            environment_path = api_root / "postman" / "environments" / "board-enthusiasts_local.postman_environment.json"
            collection_path.parent.mkdir(parents=True, exist_ok=True)
            environment_path.parent.mkdir(parents=True, exist_ok=True)
            collection_path.write_text("{}", encoding="utf-8")
            environment_path.write_text("{}", encoding="utf-8")

            args = self.create_args()
            config = dev.config_from_args(args, repo_root)

            with (
                mock.patch.object(dev, "assert_command_available"),
                mock.patch.object(dev, "run_api_spec_lint"),
                mock.patch.object(dev, "run_supabase_stack_command") as run_supabase_stack_command,
                mock.patch.object(
                    dev,
                    "get_local_supabase_runtime",
                    return_value={
                        "SUPABASE_URL": "http://127.0.0.1:54321",
                        "SUPABASE_ANON_KEY": "anon-key",
                    },
                ),
                mock.patch.object(
                    dev,
                    "start_migration_workers_process",
                    return_value=(mock.Mock(spec=[]), repo_root / ".dev-cli-logs" / "workers-api.log"),
                ) as start_workers_process,
                mock.patch.object(
                    dev,
                    "fetch_supabase_access_token",
                    side_effect=["developer-token", "moderator-token"],
                ) as fetch_token,
                mock.patch.object(dev, "run_command") as run_command,
                mock.patch.object(dev, "stop_background_process") as stop_background_process,
            ):
                dev.run_api_contract_tests(
                    config,
                    environment_path=environment_path,
                    base_url=config.migration_workers_base_url,
                    contract_execution_mode="live",
                    report_path=repo_root / "api" / "postman-cli-reports" / "contract-tests.xml",
                    lint_spec=False,
                    start_workers=True,
                    developer_token=None,
                    moderator_token=None,
                    developer_email=dev.LOCAL_SEED_DEVELOPER_EMAIL,
                    moderator_email=dev.LOCAL_SEED_MODERATOR_EMAIL,
                    seed_user_password=dev.LOCAL_SEED_DEFAULT_PASSWORD,
                )

            self.assertEqual(
                [
                    mock.call(config, action="start"),
                    mock.call(config, action="db-reset"),
                ],
                run_supabase_stack_command.call_args_list,
            )
            start_workers_process.assert_called_once()
            self.assertEqual(2, fetch_token.call_count)
            run_command.assert_called_once()
            invoked_command = run_command.call_args.args[0]
            self.assertIn("developerAccessToken=developer-token", invoked_command)
            self.assertIn("moderatorAccessToken=moderator-token", invoked_command)
            self.assertIn(f"baseUrl={config.migration_workers_base_url}", invoked_command)
            stop_background_process.assert_called_once()

    def test_parity_commands_no_longer_accept_start_stack(self) -> None:
        parser = dev.build_parser()

        with self.assertRaises(SystemExit):
            parser.parse_args(["parity-test", "--start-stack"])

        with self.assertRaises(SystemExit):
            parser.parse_args(["capture-parity-baseline", "--start-stack"])


if __name__ == "__main__":
    unittest.main()
