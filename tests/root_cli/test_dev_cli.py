"""Focused unit coverage for maintained developer CLI helpers."""

from __future__ import annotations

import argparse
import importlib.util
import pathlib
import subprocess
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
    """Covers the pure helper logic used by the maintained developer CLI."""

    @staticmethod
    def create_args() -> argparse.Namespace:
        """Create a minimal argument namespace for config construction."""

        return argparse.Namespace()

    def test_is_local_supabase_url_reports_expected_values(self) -> None:
        self.assertTrue(dev.is_local_http_url("http://127.0.0.1:55421"))
        self.assertTrue(dev.is_local_http_url("https://localhost:7277"))
        self.assertFalse(dev.is_local_http_url("https://staging.boardenthusiasts.com"))

    def test_config_from_args_keeps_root_relative_migration_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()

            config = dev.config_from_args(args, repo_root)

            self.assertEqual("frontend", config.migration_spa_root)
            self.assertEqual("backend/apps/workers-api", config.migration_workers_root)
            self.assertEqual("backend/supabase", config.supabase_root)
            self.assertEqual("config/.env.local.example", config.local_env_example)
            self.assertEqual("config/.env.staging.example", config.staging_env_example)
            self.assertEqual("config/.env.example", config.production_env_example)
            self.assertEqual("config/.env.local", config.local_env_file)
            self.assertEqual("config/.env.staging", config.staging_env_file)
            self.assertEqual("config/.env", config.production_env_file)

    def test_build_migration_workspace_command_uses_workspace_name(self) -> None:
        command = dev.build_workspace_npm_command(
            script_name="dev",
            workspace_name="@board-enthusiasts/spa",
        )

        self.assertEqual(
            ["npm", "run", "dev", "--workspace", "@board-enthusiasts/spa"],
            command,
        )

    def test_apply_environment_file_preserves_existing_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = pathlib.Path(temp_dir) / ".env.local"
            env_path.write_text("FIRST=from-file\nSECOND=from-file\n", encoding="utf-8")

            with mock.patch.dict(dev.os.environ, {"SECOND": "from-shell"}, clear=False):
                parsed = dev.apply_environment_file(env_path)
                self.assertEqual("from-file", dev.os.environ["FIRST"])
                self.assertEqual("from-shell", dev.os.environ["SECOND"])

            self.assertEqual({"FIRST": "from-file", "SECOND": "from-file"}, parsed)

    def test_build_migration_frontend_environment_can_force_landing_mode(self) -> None:
        args = self.create_args()
        config = dev.config_from_args(args, pathlib.Path.cwd())

        with mock.patch.dict(dev.os.environ, {"VITE_TURNSTILE_SITE_KEY": "site-key"}, clear=False):
            environment = dev.build_migration_frontend_environment(
                config,
                runtime_env={
                    "SUPABASE_URL": "http://127.0.0.1:55421",
                    "SUPABASE_PUBLISHABLE_KEY": "publishable-key",
                },
                landing_mode=True,
            )

        self.assertEqual("http://127.0.0.1:8787", environment["VITE_API_BASE_URL"])
        self.assertEqual("http://127.0.0.1:55421", environment["VITE_SUPABASE_URL"])
        self.assertEqual("publishable-key", environment["VITE_SUPABASE_PUBLISHABLE_KEY"])
        self.assertEqual("site-key", environment["VITE_TURNSTILE_SITE_KEY"])
        self.assertEqual("true", environment["VITE_LANDING_MODE"])

    def test_has_local_required_schema_includes_marketing_contacts(self) -> None:
        runtime_env = {
            "SUPABASE_URL": "http://127.0.0.1:55421",
            "SUPABASE_SECRET_KEY": "secret-key",
        }
        requested_urls: list[str] = []

        class _Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        def fake_urlopen(request, timeout=10):
            requested_urls.append(request.full_url)
            return _Response()

        with mock.patch.object(dev.urllib.request, "urlopen", side_effect=fake_urlopen):
            self.assertTrue(dev.has_local_required_schema(runtime_env))

        self.assertEqual(
            [
                "http://127.0.0.1:55421/rest/v1/titles?select=*&limit=1",
                "http://127.0.0.1:55421/rest/v1/genres?select=*&limit=1",
                "http://127.0.0.1:55421/rest/v1/age_rating_authorities?select=*&limit=1",
                "http://127.0.0.1:55421/rest/v1/marketing_contacts?select=*&limit=1",
            ],
            requested_urls,
        )

    def test_build_supabase_profile_start_command_matches_supported_profiles(self) -> None:
        prefix = ["npx", "supabase"]

        self.assertEqual(
            ["npx", "supabase", "db", "start"],
            dev.build_supabase_profile_start_command(
                prefix=prefix,
                profile=dev.SUPABASE_PROFILE_DATABASE,
            ),
        )
        self.assertEqual(
            [
                "npx",
                "supabase",
                "start",
                "-x",
                "studio",
                "-x",
                "storage-api",
                "-x",
                "imgproxy",
                "-x",
                "postgres-meta",
                "-x",
                "realtime",
                "-x",
                "postgrest",
                "-x",
                "edge-runtime",
                "-x",
                "logflare",
                "-x",
                "vector",
                "-x",
                "supavisor",
            ],
            dev.build_supabase_profile_start_command(
                prefix=prefix,
                profile=dev.SUPABASE_PROFILE_AUTH,
            ),
        )
        self.assertEqual(
            [
                "npx",
                "supabase",
                "start",
                "-x",
                "studio",
                "-x",
                "imgproxy",
                "-x",
                "postgres-meta",
                "-x",
                "realtime",
                "-x",
                "edge-runtime",
                "-x",
                "logflare",
                "-x",
                "vector",
                "-x",
                "supavisor",
            ],
            dev.build_supabase_profile_start_command(
                prefix=prefix,
                profile=dev.SUPABASE_PROFILE_API,
            ),
        )

        self.assertEqual(
            [
                "npx",
                "supabase",
                "start",
                "-x",
                "studio",
                "-x",
                "imgproxy",
                "-x",
                "postgres-meta",
                "-x",
                "realtime",
                "-x",
                "edge-runtime",
                "-x",
                "logflare",
                "-x",
                "vector",
                "-x",
                "supavisor",
            ],
            dev.build_supabase_profile_start_command(
                prefix=prefix,
                profile=dev.SUPABASE_PROFILE_WEB,
            ),
        )

    def test_parse_env_assignments_unquotes_supabase_status_values(self) -> None:
        parsed = dev.parse_env_assignments(
            'API_URL="http://127.0.0.1:55421"\nANON_KEY="anon"\nSERVICE_ROLE_KEY="service"\n'
        )

        self.assertEqual("http://127.0.0.1:55421", parsed["API_URL"])
        self.assertEqual("anon", parsed["ANON_KEY"])
        self.assertEqual("service", parsed["SERVICE_ROLE_KEY"])

    def test_get_supabase_status_env_backfills_current_cli_fields(self) -> None:
        args = self.create_args()
        config = dev.config_from_args(args, pathlib.Path.cwd())

        completed = subprocess.CompletedProcess(
            args=["npx", "supabase", "status", "-o", "env"],
            returncode=0,
            stdout=(
                'ANON_KEY="anon"\n'
                'PUBLISHABLE_KEY="publishable"\n'
                'SERVICE_ROLE_KEY="service"\n'
            ),
            stderr="",
        )

        with mock.patch.object(dev, "resolve_supabase_command_prefix", return_value=["npx", "supabase"]), mock.patch.object(
            dev,
            "run_command",
            return_value=completed,
        ):
            status_env = dev.get_supabase_status_env(config)

        self.assertEqual(dev.LOCAL_SUPABASE_URL, status_env["API_URL"])
        self.assertEqual("anon", status_env["ANON_KEY"])
        self.assertEqual("service", status_env["SERVICE_ROLE_KEY"])

    def test_get_supabase_project_id_reads_config_value(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            supabase_root = repo_root / config.supabase_root
            supabase_root.mkdir(parents=True, exist_ok=True)
            (supabase_root / "config.toml").write_text('project_id = "board-enthusiasts-local"\n', encoding="utf-8")

            self.assertEqual("board-enthusiasts-local", dev.get_supabase_project_id(config))

    def test_build_supabase_bearer_headers_uses_apikey_and_bearer(self) -> None:
        headers = dev.build_supabase_bearer_headers(api_key="secret-key")

        self.assertEqual("secret-key", headers["apikey"])
        self.assertEqual("Bearer secret-key", headers["authorization"])
        self.assertEqual("application/json", headers["accept"])

    def test_ensure_runtime_profile_reuses_matching_runtime_when_supabase_is_healthy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)

            runtime_env = {
                "SUPABASE_URL": "http://127.0.0.1:55421",
                "SUPABASE_SECRET_KEY": "secret-key",
            }

            with (
                mock.patch.object(dev, "load_runtime_profile_state", return_value=dev.SUPABASE_PROFILE_WEB),
                mock.patch.object(dev, "stop_all_managed_application_processes") as stop_processes,
                mock.patch.object(dev, "get_local_supabase_runtime", return_value=runtime_env),
                mock.patch.object(dev, "wait_for_local_supabase_http_ready") as wait_for_ready,
                mock.patch.object(dev, "save_runtime_profile_state") as save_state,
                mock.patch.object(dev, "restart_runtime_profile") as restart_runtime_profile,
            ):
                dev.ensure_runtime_profile(config, profile=dev.SUPABASE_PROFILE_WEB)

            stop_processes.assert_called_once_with(config)
            wait_for_ready.assert_called_once_with(runtime_env=runtime_env)
            save_state.assert_called_once_with(config, profile=dev.SUPABASE_PROFILE_WEB)
            restart_runtime_profile.assert_not_called()

    def test_ensure_runtime_profile_reuses_live_web_runtime_without_state_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)

            runtime_env = {
                "SUPABASE_URL": "http://127.0.0.1:55421",
                "SUPABASE_SECRET_KEY": "secret-key",
            }

            with (
                mock.patch.object(dev, "load_runtime_profile_state", return_value=None),
                mock.patch.object(dev, "stop_all_managed_application_processes") as stop_processes,
                mock.patch.object(dev, "get_local_supabase_runtime", return_value=runtime_env),
                mock.patch.object(dev, "wait_for_local_supabase_http_ready") as wait_for_ready,
                mock.patch.object(dev, "save_runtime_profile_state") as save_state,
                mock.patch.object(dev, "restart_runtime_profile") as restart_runtime_profile,
            ):
                dev.ensure_runtime_profile(config, profile=dev.SUPABASE_PROFILE_WEB)

            stop_processes.assert_called_once_with(config)
            wait_for_ready.assert_called_once_with(runtime_env=runtime_env)
            save_state.assert_called_once_with(config, profile=dev.SUPABASE_PROFILE_WEB)
            restart_runtime_profile.assert_not_called()

    def test_ensure_runtime_profile_restarts_matching_runtime_when_supabase_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)

            with (
                mock.patch.object(dev, "load_runtime_profile_state", return_value=dev.SUPABASE_PROFILE_WEB),
                mock.patch.object(dev, "stop_all_managed_application_processes") as stop_processes,
                mock.patch.object(
                    dev,
                    "get_local_supabase_runtime",
                    side_effect=dev.DevCliError("Local Supabase services are not running."),
                ),
                mock.patch.object(dev, "wait_for_local_supabase_http_ready") as wait_for_ready,
                mock.patch.object(dev, "save_runtime_profile_state") as save_state,
                mock.patch.object(dev, "restart_runtime_profile") as restart_runtime_profile,
            ):
                dev.ensure_runtime_profile(config, profile=dev.SUPABASE_PROFILE_WEB)

            stop_processes.assert_called_once_with(config)
            wait_for_ready.assert_not_called()
            save_state.assert_not_called()
            restart_runtime_profile.assert_called_once_with(config, profile=dev.SUPABASE_PROFILE_WEB)

    def test_ensure_runtime_profile_restarts_when_requested_profile_differs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)

            with (
                mock.patch.object(dev, "load_runtime_profile_state", return_value=dev.SUPABASE_PROFILE_AUTH),
                mock.patch.object(dev, "stop_all_managed_application_processes") as stop_processes,
                mock.patch.object(dev, "get_local_supabase_runtime") as get_local_supabase_runtime,
                mock.patch.object(dev, "wait_for_local_supabase_http_ready") as wait_for_ready,
                mock.patch.object(dev, "save_runtime_profile_state") as save_state,
                mock.patch.object(dev, "restart_runtime_profile") as restart_runtime_profile,
            ):
                dev.ensure_runtime_profile(config, profile=dev.SUPABASE_PROFILE_WEB)

            stop_processes.assert_not_called()
            get_local_supabase_runtime.assert_not_called()
            wait_for_ready.assert_not_called()
            save_state.assert_not_called()
            restart_runtime_profile.assert_called_once_with(config, profile=dev.SUPABASE_PROFILE_WEB)

    def test_run_supabase_stop_retries_transient_docker_prune_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            (repo_root / config.supabase_root).mkdir(parents=True, exist_ok=True)

            transient_failure = subprocess.CompletedProcess(
                args=["npx", "supabase", "stop"],
                returncode=1,
                stdout="",
                stderr="failed to prune containers: Error response from daemon: a prune operation is already running",
            )
            success = subprocess.CompletedProcess(
                args=["npx", "supabase", "stop"],
                returncode=0,
                stdout="",
                stderr="",
            )

            with (
                mock.patch.object(dev, "ensure_migration_workspace_scaffolding"),
                mock.patch.object(dev, "ensure_docker_daemon_available"),
                mock.patch.object(dev, "resolve_supabase_command_prefix", return_value=["npx", "supabase"]),
                mock.patch.object(dev, "run_command", side_effect=[transient_failure, success]) as run_command,
                mock.patch.object(dev.time, "sleep") as sleep,
            ):
                dev.run_supabase_stack_command(config, action="stop")

            self.assertEqual(2, run_command.call_count)
            sleep.assert_called_once_with(2)

    def test_run_supabase_stop_times_out_and_force_removes_project_containers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            (repo_root / config.supabase_root).mkdir(parents=True, exist_ok=True)

            with (
                mock.patch.object(dev, "ensure_migration_workspace_scaffolding"),
                mock.patch.object(dev, "ensure_docker_daemon_available"),
                mock.patch.object(dev, "resolve_supabase_command_prefix", return_value=["npx", "supabase"]),
                mock.patch.object(
                    dev,
                    "run_command",
                    side_effect=subprocess.TimeoutExpired(cmd=["npx", "supabase", "stop"], timeout=dev.SUPABASE_STOP_TIMEOUT_SECONDS),
                ) as run_command,
                mock.patch.object(dev, "force_remove_supabase_project_containers", return_value=True) as force_remove,
            ):
                dev.run_supabase_stack_command(config, action="stop")

            run_command.assert_called_once_with(
                ["npx", "supabase", "stop"],
                cwd=repo_root / config.supabase_root,
                check=False,
                capture_output=True,
                timeout_seconds=dev.SUPABASE_STOP_TIMEOUT_SECONDS,
            )
            force_remove.assert_called_once_with(config)

    def test_run_supabase_stop_treats_unreachable_docker_as_already_stopped(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            (repo_root / config.supabase_root).mkdir(parents=True, exist_ok=True)

            with (
                mock.patch.object(dev, "ensure_migration_workspace_scaffolding"),
                mock.patch.object(dev, "ensure_docker_daemon_available", side_effect=dev.DevCliError("docker unavailable")),
                mock.patch.object(dev, "resolve_supabase_command_prefix", return_value=["npx", "supabase"]),
                mock.patch.object(dev, "run_command") as run_command,
            ):
                dev.run_supabase_stack_command(config, action="stop")

            run_command.assert_not_called()

    def test_run_supabase_start_removes_stale_conflicting_containers_and_retries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            supabase_root = repo_root / config.supabase_root
            supabase_root.mkdir(parents=True, exist_ok=True)
            (supabase_root / "config.toml").write_text('project_id = "board-enthusiasts-local"\n', encoding="utf-8")

            conflict = subprocess.CompletedProcess(
                args=["npx", "supabase", "start"],
                returncode=1,
                stdout="",
                stderr='failed to create docker container: Error response from daemon: Conflict. The container name "/supabase_vector_board-enthusiasts-local" is already in use',
            )
            success = subprocess.CompletedProcess(
                args=["npx", "supabase", "start"],
                returncode=0,
                stdout="Started supabase local development setup.",
                stderr="",
            )

            with (
                mock.patch.object(dev, "ensure_migration_workspace_scaffolding"),
                mock.patch.object(dev, "ensure_docker_daemon_available"),
                mock.patch.object(dev, "resolve_supabase_command_prefix", return_value=["npx", "supabase"]),
                mock.patch.object(dev, "remove_stale_supabase_project_containers") as remove_stale,
                mock.patch.object(dev, "run_command", side_effect=[conflict, success]) as run_command,
                mock.patch.object(
                    dev,
                    "get_local_supabase_runtime",
                    return_value={
                        "SUPABASE_URL": "http://127.0.0.1:55421",
                        "SUPABASE_SECRET_KEY": "secret-key",
                    },
                ),
                mock.patch.object(dev, "wait_for_local_supabase_http_ready"),
            ):
                dev.run_supabase_stack_command(config, action="start")

            self.assertEqual(2, run_command.call_count)
            remove_stale.assert_called_once_with(config)

    def test_run_supabase_start_treats_already_starting_stack_as_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            supabase_root = repo_root / config.supabase_root
            supabase_root.mkdir(parents=True, exist_ok=True)

            already_starting = subprocess.CompletedProcess(
                args=["npx", "supabase", "start"],
                returncode=1,
                stdout="supabase start is already running.",
                stderr="supabase_db_board-enthusiasts-local container is not ready: starting",
            )

            with (
                mock.patch.object(dev, "ensure_migration_workspace_scaffolding"),
                mock.patch.object(dev, "ensure_docker_daemon_available"),
                mock.patch.object(dev, "resolve_supabase_command_prefix", return_value=["npx", "supabase"]),
                mock.patch.object(dev, "run_command", return_value=already_starting) as run_command,
                mock.patch.object(
                    dev,
                    "get_local_supabase_runtime",
                    return_value={
                        "SUPABASE_URL": "http://127.0.0.1:55421",
                        "SUPABASE_SECRET_KEY": "secret-key",
                    },
                ),
                mock.patch.object(dev, "wait_for_local_supabase_http_ready") as wait_for_ready,
            ):
                dev.run_supabase_stack_command(config, action="start")

            run_command.assert_called_once()
            wait_for_ready.assert_called_once()

    def test_run_supabase_start_uses_maintained_web_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            supabase_root = repo_root / config.supabase_root
            supabase_root.mkdir(parents=True, exist_ok=True)

            success = subprocess.CompletedProcess(
                args=["npx", "supabase", "start"],
                returncode=0,
                stdout="Started supabase local development setup.",
                stderr="",
            )

            with (
                mock.patch.object(dev, "ensure_migration_workspace_scaffolding"),
                mock.patch.object(dev, "ensure_docker_daemon_available"),
                mock.patch.object(dev, "resolve_supabase_command_prefix", return_value=["npx", "supabase"]),
                mock.patch.object(dev, "run_command", return_value=success) as run_command,
                mock.patch.object(
                    dev,
                    "get_local_supabase_runtime",
                    return_value={
                        "SUPABASE_URL": "http://127.0.0.1:55421",
                        "SUPABASE_SECRET_KEY": "secret-key",
                    },
                ),
                mock.patch.object(dev, "wait_for_local_supabase_http_ready"),
            ):
                dev.run_supabase_stack_command(config, action="start")

            run_command.assert_called_once_with(
                dev.build_supabase_profile_start_command(
                    prefix=["npx", "supabase"],
                    profile=dev.SUPABASE_PROFILE_WEB,
                ),
                cwd=supabase_root,
                check=False,
                capture_output=True,
            )

    def test_run_supabase_start_retries_when_docker_is_still_reconciling_containers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            supabase_root = repo_root / config.supabase_root
            supabase_root.mkdir(parents=True, exist_ok=True)

            transient_failure = subprocess.CompletedProcess(
                args=["npx", "supabase", "start"],
                returncode=1,
                stdout="",
                stderr=(
                    "Stopping containers...\n"
                    "failed to prune containers: Error response from daemon: a prune operation is already running\n"
                    "failed to start docker container: Error response from daemon: No such container: deadbeef"
                ),
            )
            success = subprocess.CompletedProcess(
                args=["npx", "supabase", "start"],
                returncode=0,
                stdout="Started supabase local development setup.",
                stderr="",
            )

            with (
                mock.patch.object(dev, "ensure_migration_workspace_scaffolding"),
                mock.patch.object(dev, "ensure_docker_daemon_available"),
                mock.patch.object(dev, "resolve_supabase_command_prefix", return_value=["npx", "supabase"]),
                mock.patch.object(dev, "run_command", side_effect=[transient_failure, success]) as run_command,
                mock.patch.object(
                    dev,
                    "get_local_supabase_runtime",
                    return_value={
                        "SUPABASE_URL": "http://127.0.0.1:55421",
                        "SUPABASE_SECRET_KEY": "secret-key",
                    },
                ),
                mock.patch.object(dev, "wait_for_local_supabase_http_ready"),
            ):
                dev.run_supabase_stack_command(config, action="start")

            self.assertEqual(2, run_command.call_count)

    def test_run_supabase_db_reset_retries_when_container_removal_is_still_in_progress(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            supabase_root = repo_root / config.supabase_root
            supabase_root.mkdir(parents=True, exist_ok=True)

            retryable_failure = subprocess.CompletedProcess(
                args=["npx", "supabase", "db", "reset", "--local"],
                returncode=1,
                stdout="",
                stderr=(
                    "Resetting local database...\n"
                    "failed to remove container: Error response from daemon: "
                    "removal of container supabase_db_board-enthusiasts-local is already in progress"
                ),
            )
            success = subprocess.CompletedProcess(
                args=["npx", "supabase", "db", "reset", "--local"],
                returncode=0,
                stdout="Reset complete.",
                stderr="",
            )
            start_success = subprocess.CompletedProcess(
                args=["npx", "supabase", "start"],
                returncode=0,
                stdout="Started supabase local development setup.",
                stderr="",
            )

            with (
                mock.patch.object(dev, "ensure_migration_workspace_scaffolding"),
                mock.patch.object(dev, "ensure_docker_daemon_available"),
                mock.patch.object(dev, "install_migration_workspace_dependencies"),
                mock.patch.object(dev, "resolve_supabase_command_prefix", return_value=["npx", "supabase"]),
                mock.patch.object(dev, "run_command", side_effect=[retryable_failure, start_success, success]) as run_command,
                mock.patch.object(dev, "seed_migration_data") as seed_migration_data,
                mock.patch.object(
                    dev,
                    "get_local_supabase_runtime",
                    return_value={
                        "SUPABASE_URL": "http://127.0.0.1:55421",
                        "SUPABASE_SECRET_KEY": "secret-key",
                    },
                ),
                mock.patch.object(dev, "wait_for_local_supabase_http_ready"),
            ):
                dev.run_supabase_stack_command(config, action="db-reset")

            self.assertEqual(3, run_command.call_count)
            seed_migration_data.assert_called_once_with(config, seed_password=dev.LOCAL_SEED_DEFAULT_PASSWORD)

    def test_run_supabase_db_reset_retries_when_migration_state_is_inconsistent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            supabase_root = repo_root / config.supabase_root
            supabase_root.mkdir(parents=True, exist_ok=True)

            migration_conflict = subprocess.CompletedProcess(
                args=["npx", "supabase", "db", "reset", "--local"],
                returncode=1,
                stdout="",
                stderr=(
                    "ERROR: duplicate key value violates unique constraint \"schema_migrations_pkey\" "
                    "(SQLSTATE 23505)"
                ),
            )
            success = subprocess.CompletedProcess(
                args=["npx", "supabase", "db", "reset", "--local"],
                returncode=0,
                stdout="Reset complete.",
                stderr="",
            )
            stop_success = subprocess.CompletedProcess(
                args=["npx", "supabase", "stop"],
                returncode=0,
                stdout="Stopped local Supabase services.",
                stderr="",
            )
            start_success = subprocess.CompletedProcess(
                args=["npx", "supabase", "start"],
                returncode=0,
                stdout="Started supabase local development setup.",
                stderr="",
            )

            with (
                mock.patch.object(dev, "ensure_migration_workspace_scaffolding"),
                mock.patch.object(dev, "ensure_docker_daemon_available"),
                mock.patch.object(dev, "install_migration_workspace_dependencies"),
                mock.patch.object(dev, "resolve_supabase_command_prefix", return_value=["npx", "supabase"]),
                mock.patch.object(
                    dev,
                    "run_command",
                    side_effect=[migration_conflict, stop_success, start_success, success],
                ) as run_command,
                mock.patch.object(dev, "seed_migration_data") as seed_migration_data,
                mock.patch.object(
                    dev,
                    "get_local_supabase_runtime",
                    return_value={
                        "SUPABASE_URL": "http://127.0.0.1:55421",
                        "SUPABASE_SECRET_KEY": "secret-key",
                    },
                ),
                mock.patch.object(dev, "wait_for_local_supabase_http_ready"),
            ):
                dev.run_supabase_stack_command(config, action="db-reset")

            self.assertEqual(4, run_command.call_count)
            seed_migration_data.assert_called_once_with(config, seed_password=dev.LOCAL_SEED_DEFAULT_PASSWORD)

    def test_run_supabase_db_reset_restarts_stack_when_seed_readiness_is_transient(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            supabase_root = repo_root / config.supabase_root
            supabase_root.mkdir(parents=True, exist_ok=True)

            success = subprocess.CompletedProcess(
                args=["npx", "supabase", "db", "reset", "--local"],
                returncode=0,
                stdout="Reset complete.",
                stderr="",
            )
            stop_success = subprocess.CompletedProcess(
                args=["npx", "supabase", "stop"],
                returncode=0,
                stdout="Stopped local Supabase services.",
                stderr="",
            )
            start_success = subprocess.CompletedProcess(
                args=["npx", "supabase", "start"],
                returncode=0,
                stdout="Started supabase local development setup.",
                stderr="",
            )
            transient_seed_error = dev.DevCliError(
                "Timed out waiting for local Supabase HTTP services to become ready.\n"
                "Last probe failures: Supabase Storage API: HTTP 502 Bad Gateway: "
                '{"message":"An invalid response was received from the upstream server"}'
            )

            with (
                mock.patch.object(dev, "ensure_migration_workspace_scaffolding"),
                mock.patch.object(dev, "ensure_docker_daemon_available"),
                mock.patch.object(dev, "install_migration_workspace_dependencies"),
                mock.patch.object(dev, "resolve_supabase_command_prefix", return_value=["npx", "supabase"]),
                mock.patch.object(
                    dev,
                    "run_command",
                    side_effect=[success, stop_success, start_success, success],
                ) as run_command,
                mock.patch.object(
                    dev,
                    "seed_migration_data",
                    side_effect=[transient_seed_error, None],
                ) as seed_migration_data,
                mock.patch.object(
                    dev,
                    "get_local_supabase_runtime",
                    return_value={
                        "SUPABASE_URL": "http://127.0.0.1:55421",
                        "SUPABASE_SECRET_KEY": "secret-key",
                    },
                ),
                mock.patch.object(dev, "wait_for_local_supabase_http_ready"),
            ):
                dev.run_supabase_stack_command(config, action="db-reset")

            self.assertEqual(4, run_command.call_count)
            self.assertEqual(2, seed_migration_data.call_count)

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

    def test_database_and_web_parsers_default_to_up_actions(self) -> None:
        parser = dev.build_parser()

        database_args = parser.parse_args(["database"])
        web_args = parser.parse_args(["web", "--hot-reload"])

        self.assertEqual("up", database_args.action)
        self.assertEqual("up", web_args.action)
        self.assertTrue(web_args.hot_reload)
        self.assertFalse(web_args.landing_mode)

    def test_web_parser_accepts_landing_mode_flag(self) -> None:
        parser = dev.build_parser()

        web_args = parser.parse_args(["web", "--landing-mode", "--no-browser"])

        self.assertEqual("up", web_args.action)
        self.assertTrue(web_args.landing_mode)
        self.assertTrue(web_args.no_browser)

    def test_status_and_down_parsers_accept_include_dependencies(self) -> None:
        parser = dev.build_parser()

        api_args = parser.parse_args(["api", "down", "--include-dependencies"])
        web_args = parser.parse_args(["web", "status", "--include-dependencies"])

        self.assertTrue(api_args.include_dependencies)
        self.assertTrue(web_args.include_dependencies)

    def test_main_web_down_without_dependencies_stops_only_web_service(self) -> None:
        with (
            mock.patch.object(dev, "stop_frontend_service") as stop_frontend_service,
            mock.patch.object(dev, "stop_backend_service") as stop_backend_service,
            mock.patch.object(dev, "stop_runtime_profile") as stop_runtime_profile,
            mock.patch.object(dev, "is_managed_service_running", return_value=True),
            mock.patch.object(dev, "save_runtime_profile_state") as save_runtime_profile_state,
        ):
            exit_code = dev.main(["web", "down"])

        self.assertEqual(0, exit_code)
        stop_frontend_service.assert_called_once()
        stop_backend_service.assert_not_called()
        stop_runtime_profile.assert_not_called()
        save_runtime_profile_state.assert_called_once_with(
            mock.ANY,
            profile=dev.SUPABASE_PROFILE_API,
        )

    def test_main_web_up_passes_landing_mode_to_full_stack_runner(self) -> None:
        with mock.patch.object(dev, "run_full_local_web_stack") as run_full_local_web_stack:
            exit_code = dev.main(["web", "--landing-mode", "--no-browser"])

        self.assertEqual(0, exit_code)
        run_full_local_web_stack.assert_called_once_with(
            mock.ANY,
            bootstrap=False,
            install_dependencies=True,
            hot_reload=False,
            landing_mode=True,
            open_browser_on_ready=False,
        )

    def test_main_web_down_with_dependencies_stops_full_stack(self) -> None:
        with (
            mock.patch.object(dev, "stop_frontend_service") as stop_frontend_service,
            mock.patch.object(dev, "stop_backend_service") as stop_backend_service,
            mock.patch.object(dev, "stop_runtime_profile") as stop_runtime_profile,
        ):
            exit_code = dev.main(["web", "down", "--include-dependencies"])

        self.assertEqual(0, exit_code)
        stop_frontend_service.assert_called_once()
        stop_backend_service.assert_called_once()
        stop_runtime_profile.assert_called_once()

    def test_main_api_down_without_dependencies_stops_api_and_keeps_auth_database(self) -> None:
        with (
            mock.patch.object(dev, "stop_frontend_service") as stop_frontend_service,
            mock.patch.object(dev, "stop_backend_service") as stop_backend_service,
            mock.patch.object(dev, "restart_runtime_profile") as restart_runtime_profile,
            mock.patch.object(dev, "stop_runtime_profile") as stop_runtime_profile,
        ):
            exit_code = dev.main(["api", "down"])

        self.assertEqual(0, exit_code)
        stop_frontend_service.assert_called_once()
        stop_backend_service.assert_called_once()
        restart_runtime_profile.assert_called_once_with(
            mock.ANY,
            profile=dev.SUPABASE_PROFILE_AUTH,
        )
        stop_runtime_profile.assert_not_called()

    def test_main_seed_data_uses_start_and_db_reset_workflow(self) -> None:
        with mock.patch.object(dev, "run_supabase_stack_command") as run_supabase_stack_command:
            exit_code = dev.main(["seed-data"])

        self.assertEqual(0, exit_code)
        self.assertEqual(
            [
                mock.call(mock.ANY, action="start"),
                mock.call(mock.ANY, action="db-reset"),
            ],
            run_supabase_stack_command.call_args_list,
        )

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
                        "SUPABASE_URL": "http://127.0.0.1:55421",
                        "SUPABASE_PUBLISHABLE_KEY": "publishable-key",
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

    def test_removed_legacy_runtime_commands_are_rejected(self) -> None:
        parser = dev.build_parser()

        for command in (
            ["up"],
            ["down"],
            ["status"],
            ["frontend"],
            ["web-status"],
            ["web-stop"],
            ["spa", "run"],
            ["workers", "run"],
            ["supabase", "start"],
        ):
            with self.assertRaises(SystemExit):
                parser.parse_args(command)

    def test_api_lint_tolerates_known_redocly_windows_shutdown_assertion_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            spec_path = repo_root / config.api_spec
            spec_path.parent.mkdir(parents=True, exist_ok=True)
            spec_path.write_text("openapi: 3.1.0\ninfo:\n  title: Test\n  version: 1.0.0\npaths: {}\n", encoding="utf-8")

            result = subprocess.CompletedProcess(
                args=["npx", "@redocly/cli", "lint", str(spec_path)],
                returncode=1,
                stdout="Woohoo! Your API description is valid. 🎉",
                stderr="Assertion failed: !(handle->flags & UV_HANDLE_CLOSING), file src\\win\\async.c, line 76",
            )

            with (
                mock.patch.object(dev, "assert_command_available"),
                mock.patch.object(dev, "run_command", return_value=result) as run_command,
            ):
                dev.run_api_spec_lint(config)

            self.assertTrue(run_command.called)


if __name__ == "__main__":
    unittest.main()
