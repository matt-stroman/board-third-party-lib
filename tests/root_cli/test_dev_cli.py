"""Focused unit coverage for maintained developer CLI helpers."""

from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
import urllib.parse
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

    def test_apply_runtime_base_url_overrides_respects_local_port_env(self) -> None:
        args = self.create_args()
        config = dev.config_from_args(args, pathlib.Path.cwd())

        with mock.patch.dict(
            dev.os.environ,
            {
                "BOARD_ENTHUSIASTS_LOCAL_WORKERS_PORT": "58877",
                "BOARD_ENTHUSIASTS_LOCAL_FRONTEND_PORT": "54173",
            },
            clear=False,
        ):
            overridden = dev.apply_runtime_base_url_overrides(config)

        self.assertEqual("http://127.0.0.1:58877", overridden.backend_base_url)
        self.assertEqual("http://127.0.0.1:58877", overridden.migration_workers_base_url)
        self.assertEqual("http://127.0.0.1:54173", overridden.frontend_base_url)
        self.assertEqual("http://127.0.0.1:54173", overridden.migration_spa_base_url)

    def test_build_migration_workspace_command_uses_workspace_name(self) -> None:
        command = dev.build_workspace_npm_command(
            script_name="dev",
            workspace_name="@board-enthusiasts/spa",
        )

        self.assertEqual(
            ["npm", "run", "dev", "--workspace", "@board-enthusiasts/spa"],
            command,
        )

    def test_resolve_supabase_command_prefix_prefers_standalone_cli(self) -> None:
        with mock.patch.object(dev.shutil, "which", side_effect=lambda name: "C:/tools/supabase.exe" if name == "supabase" else None):
            self.assertEqual(["supabase"], dev.resolve_supabase_command_prefix())

    def test_resolve_supabase_command_prefix_uses_non_interactive_npx_fallback(self) -> None:
        def fake_which(name: str) -> str | None:
            if name == "supabase":
                return None
            if name == "npx":
                return "C:/Program Files/nodejs/npx.cmd"
            return None

        with mock.patch.object(dev.shutil, "which", side_effect=fake_which):
            self.assertEqual(["npx", "--yes", "supabase"], dev.resolve_supabase_command_prefix())

    def test_apply_environment_file_preserves_existing_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = pathlib.Path(temp_dir) / ".env.local"
            env_path.write_text("FIRST=from-file\nSECOND=from-file\n", encoding="utf-8")

            with mock.patch.dict(dev.os.environ, {"SECOND": "from-shell"}, clear=False):
                parsed = dev.apply_environment_file(env_path)
                self.assertEqual("from-file", dev.os.environ["FIRST"])
                self.assertEqual("from-shell", dev.os.environ["SECOND"])

            self.assertEqual({"FIRST": "from-file", "SECOND": "from-file"}, parsed)

    def test_require_environment_values_treats_placeholders_as_missing(self) -> None:
        with mock.patch.dict(
            dev.os.environ,
            {
                "PRESENT": "value",
                "PLACEHOLDER": "replace-me",
                "OPTIONAL_STYLE": "optional-for-staging",
            },
            clear=True,
        ):
            with self.assertRaises(dev.DevCliError) as raised:
                dev.require_environment_values("PRESENT", "PLACEHOLDER", "OPTIONAL_STYLE", context="Deploy test")

        self.assertIn("PLACEHOLDER", str(raised.exception))
        self.assertIn("OPTIONAL_STYLE", str(raised.exception))

    def test_is_github_environment_secret_matches_expected_split(self) -> None:
        self.assertTrue(dev.is_github_environment_secret("SUPABASE_SECRET_KEY"))
        self.assertTrue(dev.is_github_environment_secret("DEPLOY_SMOKE_SECRET"))
        self.assertFalse(dev.is_github_environment_secret("SUPABASE_PUBLISHABLE_KEY"))
        self.assertFalse(dev.is_github_environment_secret("BREVO_SIGNUPS_LIST_ID"))

    def test_infer_supabase_url_from_project_ref_for_hosted_env(self) -> None:
        with mock.patch.dict(
            dev.os.environ,
            {
                "BOARD_ENTHUSIASTS_APP_ENV": "staging",
                "SUPABASE_PROJECT_REF": "project-ref-123",
            },
            clear=True,
        ):
            self.assertEqual(
                "https://project-ref-123.supabase.co",
                dev.infer_supabase_url_from_environment(),
            )

    def test_infer_supabase_url_respects_explicit_override_for_custom_domains(self) -> None:
        with mock.patch.dict(
            dev.os.environ,
            {
                "BOARD_ENTHUSIASTS_APP_ENV": "production",
                "SUPABASE_PROJECT_REF": "project-ref-123",
                "SUPABASE_URL": "https://supabase.boardenthusiasts.com",
            },
            clear=True,
        ):
            self.assertEqual(
                "https://supabase.boardenthusiasts.com",
                dev.infer_supabase_url_from_environment(),
            )

    def test_infer_supabase_url_does_not_override_local_environment(self) -> None:
        with mock.patch.dict(
            dev.os.environ,
            {
                "BOARD_ENTHUSIASTS_APP_ENV": "local",
                "SUPABASE_PROJECT_REF": "local-dev",
            },
            clear=True,
        ):
            self.assertIsNone(dev.infer_supabase_url_from_environment())

    def test_resolve_deploy_source_branch_prefers_explicit_argument(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())

        with mock.patch.dict(dev.os.environ, {"GITHUB_REF_NAME": "staging"}, clear=False):
            self.assertEqual(
                "release/1.2.3",
                dev.resolve_deploy_source_branch(config, explicit_source_branch="release/1.2.3"),
            )

    def test_resolve_deploy_source_branch_uses_github_ref_name_when_present(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())

        with mock.patch.dict(dev.os.environ, {"GITHUB_REF_NAME": "staging"}, clear=True):
            self.assertEqual("staging", dev.resolve_deploy_source_branch(config))

    def test_resolve_deploy_source_branch_falls_back_to_git_branch(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())

        git_branch_result = subprocess.CompletedProcess(
            args=["git", "branch", "--show-current"],
            returncode=0,
            stdout="release/v1.0.0\n",
            stderr="",
        )
        with mock.patch.dict(dev.os.environ, {}, clear=True):
            with mock.patch.object(dev, "run_command", return_value=git_branch_result) as run_command_mock:
                self.assertEqual("release/v1.0.0", dev.resolve_deploy_source_branch(config))

        run_command_mock.assert_called_once()

    def test_resolve_deploy_source_branch_requires_explicit_branch_when_detached(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())

        git_branch_result = subprocess.CompletedProcess(
            args=["git", "branch", "--show-current"],
            returncode=0,
            stdout="\n",
            stderr="",
        )
        with mock.patch.dict(dev.os.environ, {}, clear=True):
            with mock.patch.object(dev, "run_command", return_value=git_branch_result):
                with self.assertRaises(dev.DevCliError) as raised:
                    dev.resolve_deploy_source_branch(config)

        self.assertIn("--source-branch", str(raised.exception))

    def test_auto_load_command_environment_normalizes_inferred_supabase_url(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            staging_env_path = repo_root / config.staging_env_file
            staging_env_path.parent.mkdir(parents=True, exist_ok=True)
            staging_env_path.write_text(
                "BOARD_ENTHUSIASTS_APP_ENV=staging\nSUPABASE_PROJECT_REF=project-ref-123\n",
                encoding="utf-8",
            )

            with mock.patch.dict(dev.os.environ, {}, clear=True):
                loaded_path = dev.auto_load_command_environment(
                    config,
                    command_name="deploy",
                    deploy_target="staging",
                )
                self.assertEqual("https://project-ref-123.supabase.co", dev.os.environ["SUPABASE_URL"])

            self.assertEqual(staging_env_path, loaded_path)

    def test_normalize_deploy_stage_state_requires_upgrade_for_new_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            config = dev.config_from_args(self.create_args(), repo_root)
            dev.save_deploy_state(
                config,
                target="staging",
                state={
                    "target": "staging",
                    "fingerprint": "old-fingerprint",
                    "completed_stages": ["supabase_schema"],
                },
            )

            with self.assertRaises(dev.DevCliError) as raised:
                dev.normalize_deploy_stage_state(
                    config,
                    target="staging",
                    fingerprint="new-fingerprint",
                    force=False,
                    upgrade=False,
                )

        self.assertIn("--upgrade", str(raised.exception))

    def test_normalize_deploy_stage_state_resets_completed_stages_for_upgrade(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            config = dev.config_from_args(self.create_args(), repo_root)
            dev.save_deploy_state(
                config,
                target="staging",
                state={
                    "target": "staging",
                    "fingerprint": "old-fingerprint",
                    "completed_stages": ["supabase_schema", "pages_project"],
                },
            )

            completed_stages, state = dev.normalize_deploy_stage_state(
                config,
                target="staging",
                fingerprint="new-fingerprint",
                force=False,
                upgrade=True,
            )

        self.assertEqual(set(), completed_stages)
        self.assertEqual("new-fingerprint", state["fingerprint"])

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

    def test_get_deploy_worker_config_path_rewrites_main_relative_to_generated_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            template_path = repo_root / config.cloudflare_workers_template
            template_path.parent.mkdir(parents=True, exist_ok=True)
            template_path.write_text(
                "\n".join(
                    [
                        '{',
                        '  "name": "board-enthusiasts-api-staging",',
                        '  "main": "../../apps/workers-api/src/worker.ts",',
                        '  "workers_dev": true,',
                        '  "preview_urls": false,',
                        '  "routes": [],',
                        '  "vars": {',
                        '    "APP_ENV": "staging",',
                        '    "SUPABASE_URL": "env(SUPABASE_URL)"',
                        "  }",
                        "}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            rendered_path = dev.get_deploy_worker_config_path(
                config,
                target="staging",
                env_values={
                    "BOARD_ENTHUSIASTS_WORKERS_BASE_URL": "https://api.staging.boardenthusiasts.com",
                    "SUPABASE_URL": "https://example.supabase.co",
                },
            )
            rendered = rendered_path.read_text(encoding="utf-8")

        self.assertIn('"main": "../backend/apps/workers-api/src/worker.ts"', rendered)
        self.assertIn('"routes": [{"pattern": "api.staging.boardenthusiasts.com", "custom_domain": true}]', rendered)
        self.assertIn('"SUPABASE_URL": "https://example.supabase.co"', rendered)

    def test_get_deploy_worker_config_path_keeps_empty_routes_for_workers_dev_urls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            template_path = repo_root / config.cloudflare_workers_template
            template_path.parent.mkdir(parents=True, exist_ok=True)
            template_path.write_text(
                "\n".join(
                    [
                        '{',
                        '  "name": "board-enthusiasts-api-staging",',
                        '  "main": "../../apps/workers-api/src/worker.ts",',
                        '  "workers_dev": true,',
                        '  "preview_urls": false,',
                        '  "routes": [],',
                        '  "vars": {',
                        '    "APP_ENV": "staging",',
                        '    "SUPABASE_URL": "env(SUPABASE_URL)"',
                        "  }",
                        "}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            rendered_path = dev.get_deploy_worker_config_path(
                config,
                target="staging",
                env_values={
                    "BOARD_ENTHUSIASTS_WORKERS_BASE_URL": "https://board-enthusiasts-api-staging.example.workers.dev",
                    "SUPABASE_URL": "https://example.supabase.co",
                },
            )
            rendered = rendered_path.read_text(encoding="utf-8")

        self.assertIn('"routes": []', rendered)

    def test_get_deploy_worker_config_path_requires_values_for_env_placeholders(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            template_path = repo_root / config.cloudflare_workers_template
            template_path.parent.mkdir(parents=True, exist_ok=True)
            template_path.write_text(
                "\n".join(
                    [
                        "{",
                        '  "vars": {',
                        '    "SUPABASE_URL": "env(SUPABASE_URL)"',
                        "  }",
                        "}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(dev.DevCliError) as raised:
                dev.get_deploy_worker_config_path(
                    config,
                    target="staging",
                    env_values={"BOARD_ENTHUSIASTS_WORKERS_BASE_URL": "https://api.staging.boardenthusiasts.com"},
                )

        self.assertIn("SUPABASE_URL", str(raised.exception))

    def test_build_worker_custom_domain_routes_supports_production_hostnames(self) -> None:
        routes = dev.build_worker_custom_domain_routes(worker_base_url="https://api.boardenthusiasts.com")

        self.assertEqual(routes, [{"pattern": "api.boardenthusiasts.com", "custom_domain": True}])

    def test_build_cloudflare_pages_branch_alias_hostname_normalizes_release_branch(self) -> None:
        alias = dev.build_cloudflare_pages_branch_alias_hostname(
            project_name="board-enthusiasts-staging",
            source_branch="staging/1.0.0-landing-page.0",
        )

        self.assertEqual(alias, "staging-1-0-0-landing-page-0.board-enthusiasts-staging.pages.dev")

    def test_parse_cloudflare_pages_alias_hostname_uses_wranger_reported_alias(self) -> None:
        output = (
            "✨ Deployment complete! Take a peek over at https://0b1901b2.board-enthusiasts.pages.dev\n"
            "✨ Deployment alias URL: https://production-1-0-0-landing-pag.board-enthusiasts.pages.dev\n"
        )

        alias = dev.parse_cloudflare_pages_alias_hostname(output)

        self.assertEqual(alias, "production-1-0-0-landing-pag.board-enthusiasts.pages.dev")

    def test_ensure_cloudflare_pages_custom_domain_attaches_missing_hostname(self) -> None:
        env_values = {
            "BOARD_ENTHUSIASTS_SPA_BASE_URL": "https://staging.boardenthusiasts.com",
            "CLOUDFLARE_ACCOUNT_ID": "account-id",
            "CLOUDFLARE_API_TOKEN": "token",
        }

        with mock.patch.object(dev, "get_cloudflare_pages_project_domains", return_value=[]), mock.patch.object(
            dev,
            "request_json",
            return_value={"success": True},
        ) as request_json:
            dev.ensure_cloudflare_pages_custom_domain(env_values, target="staging")

        request_json.assert_called_once_with(
            url="https://api.cloudflare.com/client/v4/accounts/account-id/pages/projects/board-enthusiasts-staging/domains",
            method="POST",
            headers={
                "Authorization": "Bearer token",
                "Content-Type": "application/json",
            },
            payload={"name": "staging.boardenthusiasts.com"},
        )

    def test_ensure_cloudflare_pages_project_skips_creation_when_project_exists(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())
        env_values = {
            "CLOUDFLARE_ACCOUNT_ID": "account-id",
            "CLOUDFLARE_API_TOKEN": "token",
        }

        with mock.patch.object(
            dev,
            "get_cloudflare_pages_project",
            return_value={"name": "board-enthusiasts-staging"},
        ) as get_project, mock.patch.object(dev, "request_json") as request_json:
            dev.ensure_cloudflare_pages_project(config, target="staging", env=env_values)

        get_project.assert_called_once_with(env_values, project_name="board-enthusiasts-staging")
        request_json.assert_not_called()

    def test_ensure_cloudflare_pages_project_treats_already_exists_as_success(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())
        env_values = {
            "CLOUDFLARE_ACCOUNT_ID": "account-id",
            "CLOUDFLARE_API_TOKEN": "token",
        }

        with mock.patch.object(
            dev,
            "get_cloudflare_pages_project",
            return_value=None,
        ), mock.patch.object(
            dev,
            "request_json",
            side_effect=dev.DevCliError(
                "HTTP 409 Conflict for https://api.cloudflare.com/client/v4/accounts/account-id/pages/projects: "
                "{\"success\":false,\"errors\":[{\"code\":8000002,\"message\":\"A project with this name already exists. Choose a different project name.\"}]}"
            ),
        ):
            dev.ensure_cloudflare_pages_project(config, target="staging", env=env_values)

    def test_sync_cloudflare_pages_domain_dns_updates_existing_record_target(self) -> None:
        env_values = {
            "BOARD_ENTHUSIASTS_SPA_BASE_URL": "https://staging.boardenthusiasts.com",
            "CLOUDFLARE_ACCOUNT_ID": "account-id",
            "CLOUDFLARE_API_TOKEN": "token",
        }

        with mock.patch.object(
            dev,
            "get_cloudflare_zone_for_hostname",
            return_value={"id": "zone-id", "name": "staging.boardenthusiasts.com"},
        ), mock.patch.object(
            dev,
            "get_cloudflare_dns_records",
            return_value=[
                {
                    "id": "dns-id",
                    "type": "CNAME",
                    "name": "staging.boardenthusiasts.com",
                    "content": "staging.boardenthusiasts.pages.dev",
                    "proxied": True,
                }
            ],
        ), mock.patch.object(dev, "request_json", return_value={"success": True}) as request_json:
            dev.sync_cloudflare_pages_domain_dns(
                env_values,
                target="staging",
                alias_target="staging-1-0-0-landing-pag.board-enthusiasts-staging.pages.dev",
            )

        request_json.assert_called_once_with(
            url="https://api.cloudflare.com/client/v4/zones/zone-id/dns_records/dns-id",
            method="PUT",
            headers={
                "Authorization": "Bearer token",
                "Content-Type": "application/json",
            },
            payload={
                "type": "CNAME",
                "name": "staging.boardenthusiasts.com",
                "content": "staging-1-0-0-landing-pag.board-enthusiasts-staging.pages.dev",
                "proxied": True,
                "ttl": 1,
            },
        )

    def test_assert_pages_custom_domain_prerequisites_rejects_non_cname_records(self) -> None:
        env_values = {
            "BOARD_ENTHUSIASTS_SPA_BASE_URL": "https://boardenthusiasts.com",
            "CLOUDFLARE_ACCOUNT_ID": "account-id",
            "CLOUDFLARE_API_TOKEN": "token",
        }

        with mock.patch.object(
            dev,
            "get_cloudflare_zone_for_hostname",
            return_value={"id": "zone-id", "name": "boardenthusiasts.com"},
        ), mock.patch.object(
            dev,
            "get_cloudflare_dns_records",
            return_value=[{"id": "dns-id", "type": "A", "name": "boardenthusiasts.com"}],
        ):
            with self.assertRaises(dev.DevCliError) as raised:
                dev.assert_pages_custom_domain_prerequisites(env_values)

        self.assertIn("proxied CNAME target", str(raised.exception))

    def test_assert_pages_custom_domain_prerequisites_allows_manageable_apex_routing_records(self) -> None:
        env_values = {
            "BOARD_ENTHUSIASTS_SPA_BASE_URL": "https://boardenthusiasts.com",
            "CLOUDFLARE_ACCOUNT_ID": "account-id",
            "CLOUDFLARE_API_TOKEN": "token",
        }

        with mock.patch.object(
            dev,
            "get_cloudflare_zone_for_hostname",
            return_value={"id": "zone-id", "name": "boardenthusiasts.com"},
        ), mock.patch.object(
            dev,
            "get_cloudflare_dns_records",
            return_value=[
                {"id": "a1", "type": "A", "name": "boardenthusiasts.com", "proxied": True},
                {"id": "a2", "type": "A", "name": "boardenthusiasts.com", "proxied": True},
                {"id": "mx1", "type": "MX", "name": "boardenthusiasts.com"},
                {"id": "txt1", "type": "TXT", "name": "boardenthusiasts.com"},
            ],
        ):
            dev.assert_pages_custom_domain_prerequisites(env_values)

    def test_sync_cloudflare_pages_domain_dns_replaces_manageable_apex_routing_records(self) -> None:
        env_values = {
            "BOARD_ENTHUSIASTS_SPA_BASE_URL": "https://boardenthusiasts.com",
            "CLOUDFLARE_ACCOUNT_ID": "account-id",
            "CLOUDFLARE_API_TOKEN": "token",
        }

        with mock.patch.object(
            dev,
            "get_cloudflare_zone_for_hostname",
            return_value={"id": "zone-id", "name": "boardenthusiasts.com"},
        ), mock.patch.object(
            dev,
            "get_cloudflare_dns_records",
            return_value=[
                {"id": "a1", "type": "A", "name": "boardenthusiasts.com", "proxied": True, "content": "15.197.148.33"},
                {"id": "a2", "type": "A", "name": "boardenthusiasts.com", "proxied": True, "content": "3.33.130.190"},
                {"id": "mx1", "type": "MX", "name": "boardenthusiasts.com"},
            ],
        ), mock.patch.object(dev, "request_json") as request_json:
            dev.sync_cloudflare_pages_domain_dns(
                env_values,
                target="production",
                alias_target="production-1-0-0-landing-pag.board-enthusiasts.pages.dev",
            )

        self.assertEqual(3, request_json.call_count)
        request_json.assert_any_call(
            url="https://api.cloudflare.com/client/v4/zones/zone-id/dns_records/a1",
            method="DELETE",
            headers={
                "Authorization": "Bearer token",
                "Content-Type": "application/json",
            },
        )
        request_json.assert_any_call(
            url="https://api.cloudflare.com/client/v4/zones/zone-id/dns_records/a2",
            method="DELETE",
            headers={
                "Authorization": "Bearer token",
                "Content-Type": "application/json",
            },
        )
        request_json.assert_any_call(
            url="https://api.cloudflare.com/client/v4/zones/zone-id/dns_records",
            method="POST",
            headers={
                "Authorization": "Bearer token",
                "Content-Type": "application/json",
            },
            payload={
                "type": "CNAME",
                "name": "boardenthusiasts.com",
                "content": "production-1-0-0-landing-pag.board-enthusiasts.pages.dev",
                "proxied": True,
                "ttl": 1,
            },
        )

    def test_assert_worker_custom_domain_dns_prerequisites_skips_existing_live_custom_domain(self) -> None:
        env_values = {
            "BOARD_ENTHUSIASTS_WORKERS_BASE_URL": "https://api.staging.boardenthusiasts.com",
            "CLOUDFLARE_API_TOKEN": "token",
            "CLOUDFLARE_ACCOUNT_ID": "account-id",
        }

        with mock.patch.object(dev, "probe_http_endpoint", return_value=(True, None)) as probe_http_endpoint, mock.patch.object(
            dev, "request_json"
        ) as request_json:
            dev.assert_worker_custom_domain_dns_prerequisites(env_values)

        probe_http_endpoint.assert_called_once()
        request_json.assert_not_called()

    def test_assert_worker_custom_domain_dns_prerequisites_reports_conflicting_dns_records(self) -> None:
        env_values = {
            "BOARD_ENTHUSIASTS_WORKERS_BASE_URL": "https://api.staging.boardenthusiasts.com",
            "CLOUDFLARE_API_TOKEN": "token",
            "CLOUDFLARE_ACCOUNT_ID": "account-id",
        }

        def request_json_side_effect(*, url: str, headers: dict[str, str] | None = None, **_: object) -> object:
            self.assertIsNotNone(headers)
            if "client/v4/zones?" in url:
                zone_name = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("name", [""])[0]
                if zone_name == "boardenthusiasts.com":
                    return {
                        "result": [
                            {
                                "id": "zone-id",
                                "name": "boardenthusiasts.com",
                                "account": {"id": "account-id"},
                            }
                        ]
                    }
                return {"result": []}
            if "client/v4/zones/zone-id/dns_records" in url:
                return {"result": [{"id": "dns-id", "type": "CNAME", "name": "api.staging.boardenthusiasts.com"}]}
            self.fail(f"Unexpected Cloudflare API URL: {url}")

        with mock.patch.object(dev, "probe_http_endpoint", return_value=(False, "tls handshake failed")), mock.patch.object(
            dev,
            "request_json",
            side_effect=request_json_side_effect,
        ):
            with self.assertRaises(dev.DevCliError) as raised:
                dev.assert_worker_custom_domain_dns_prerequisites(env_values)

        self.assertIn("Delete the existing DNS record", str(raised.exception))

    def test_assert_worker_custom_domain_dns_prerequisites_allows_cloudflare_managed_worker_records(self) -> None:
        env_values = {
            "BOARD_ENTHUSIASTS_WORKERS_BASE_URL": "https://api.staging.boardenthusiasts.com",
            "CLOUDFLARE_API_TOKEN": "token",
            "CLOUDFLARE_ACCOUNT_ID": "account-id",
        }

        def request_json_side_effect(*, url: str, headers: dict[str, str] | None = None, **_: object) -> object:
            self.assertIsNotNone(headers)
            if "client/v4/zones?" in url:
                zone_name = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("name", [""])[0]
                if zone_name == "boardenthusiasts.com":
                    return {
                        "result": [
                            {
                                "id": "zone-id",
                                "name": "boardenthusiasts.com",
                                "account": {"id": "account-id"},
                            }
                        ]
                    }
                return {"result": []}
            if "client/v4/zones/zone-id/dns_records" in url:
                return {
                    "result": [
                        {
                            "id": "dns-id",
                            "type": "AAAA",
                            "name": "api.staging.boardenthusiasts.com",
                            "meta": {"origin_worker_id": "worker-id", "read_only": True},
                        }
                    ]
                }
            self.fail(f"Unexpected Cloudflare API URL: {url}")

        with mock.patch.object(dev, "probe_http_endpoint", return_value=(False, "tls handshake failed")), mock.patch.object(
            dev,
            "request_json",
            side_effect=request_json_side_effect,
        ):
            dev.assert_worker_custom_domain_dns_prerequisites(env_values)

    def test_run_deploy_preflight_does_not_require_custom_domains_to_resolve_before_deploy(self) -> None:
        args = self.create_args()
        config = dev.config_from_args(args, pathlib.Path.cwd())
        env_values = {
            "BOARD_ENTHUSIASTS_SPA_BASE_URL": "https://boardenthusiasts.com",
            "BOARD_ENTHUSIASTS_WORKERS_BASE_URL": "https://api.boardenthusiasts.com",
        }
        subprocess_env = {"CLOUDFLARE_API_TOKEN": "token"}

        with mock.patch.object(dev, "assert_github_environment_sync") as assert_github_environment_sync, mock.patch.object(
            dev, "get_cloudflare_pages_projects"
        ) as get_cloudflare_pages_projects, mock.patch.object(
            dev, "assert_pages_custom_domain_prerequisites"
        ) as assert_pages_custom_domain_prerequisites, mock.patch.object(
            dev, "assert_worker_custom_domain_dns_prerequisites"
        ) as assert_worker_custom_domain_dns_prerequisites, mock.patch.object(
            dev, "assert_supabase_publishable_access"
        ) as assert_supabase_publishable_access, mock.patch.object(
            dev, "assert_supabase_secret_access"
        ) as assert_supabase_secret_access, mock.patch.object(
            dev, "assert_turnstile_secret_access"
        ) as assert_turnstile_secret_access, mock.patch.object(
            dev, "assert_brevo_configuration"
        ) as assert_brevo_configuration, mock.patch.object(dev, "run_supabase_link") as run_supabase_link:
            dev.run_deploy_preflight(
                config,
                target="production",
                env_values=env_values,
                subprocess_env=subprocess_env,
            )

        assert_github_environment_sync.assert_called_once_with(config, target="production")
        get_cloudflare_pages_projects.assert_called_once_with(config, env=subprocess_env)
        assert_pages_custom_domain_prerequisites.assert_called_once_with(env_values)
        assert_worker_custom_domain_dns_prerequisites.assert_called_once_with(env_values)
        assert_supabase_publishable_access.assert_called_once_with(env_values)
        assert_supabase_secret_access.assert_called_once_with(env_values)
        assert_turnstile_secret_access.assert_called_once_with(env_values)
        assert_brevo_configuration.assert_called_once_with(env_values)
        run_supabase_link.assert_called_once_with(config, env_values=env_values, subprocess_env=subprocess_env)

    def test_run_workers_deploy_smoke_preserves_smoke_secret_for_support_issue_probe(self) -> None:
        env_values = {
            "BOARD_ENTHUSIASTS_WORKERS_BASE_URL": "https://api.staging.boardenthusiasts.com",
            "BOARD_ENTHUSIASTS_SPA_BASE_URL": "https://staging.boardenthusiasts.com",
            "DEPLOY_SMOKE_SECRET": "smoke-secret",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_PUBLISHABLE_KEY": "publishable-key",
            "SUPABASE_SECRET_KEY": "secret-key",
            "BREVO_API_KEY": "brevo-api-key",
            "VITE_LANDING_MODE": "true",
        }
        contact = {"id": "contact-1", "lifecycle_status": "waitlisted"}

        with mock.patch.object(dev, "wait_for_workers_deploy_smoke_base_url"), mock.patch.object(
            dev,
            "request_json",
            side_effect=[
                {"status": "ready"},
                {"accepted": True},
                {"accepted": True},
            ],
        ) as request_json, mock.patch.object(
            dev,
            "get_supabase_marketing_contact",
            side_effect=[contact, contact],
        ), mock.patch.object(
            dev,
            "get_supabase_marketing_contact_role_interests",
            return_value=["player"],
        ), mock.patch.object(
            dev,
            "get_brevo_contact",
            return_value={"id": 42},
        ), mock.patch.object(
            dev,
            "delete_supabase_marketing_contact",
        ), mock.patch.object(
            dev,
            "delete_brevo_contact",
        ), mock.patch.object(
            dev.time,
            "time",
            return_value=1773474581,
        ):
            dev.run_workers_deploy_smoke(
                dev.config_from_args(self.create_args(), pathlib.Path.cwd()),
                target="staging",
                env_values=env_values,
            )

        support_call = request_json.call_args_list[2]
        self.assertEqual("https://api.staging.boardenthusiasts.com/support/issues", support_call.kwargs["url"])
        self.assertEqual("smoke-secret", support_call.kwargs["headers"]["x-board-enthusiasts-deploy-smoke-secret"])

    def test_run_workers_deploy_smoke_requires_full_mvp_credentials_when_landing_disabled(self) -> None:
        env_values = {
            "BOARD_ENTHUSIASTS_WORKERS_BASE_URL": "https://api.staging.boardenthusiasts.com",
            "BOARD_ENTHUSIASTS_SPA_BASE_URL": "https://staging.boardenthusiasts.com",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_PUBLISHABLE_KEY": "publishable-key",
            "VITE_LANDING_MODE": "false",
        }

        with self.assertRaises(dev.DevCliError) as raised:
            dev.run_workers_deploy_smoke(
                dev.config_from_args(self.create_args(), pathlib.Path.cwd()),
                target="staging",
                env_values=env_values,
            )

        self.assertIn("Full-MVP deploy smoke requires smoke-account credentials", str(raised.exception))

    def test_run_pages_deploy_smoke_checks_full_mvp_routes_when_landing_disabled(self) -> None:
        env_values = {
            "BOARD_ENTHUSIASTS_SPA_BASE_URL": "https://staging.boardenthusiasts.com",
            "VITE_LANDING_MODE": "false",
        }

        with mock.patch.object(dev, "wait_for_pages_shell") as wait_for_pages_shell:
            dev.run_pages_deploy_smoke(env_values)

        self.assertEqual(
            [
                mock.call("https://staging.boardenthusiasts.com"),
                mock.call("https://staging.boardenthusiasts.com/browse"),
                mock.call("https://staging.boardenthusiasts.com/studios/blue-harbor-games"),
                mock.call("https://staging.boardenthusiasts.com/browse/blue-harbor-games/lantern-drift"),
                mock.call("https://staging.boardenthusiasts.com/player"),
                mock.call("https://staging.boardenthusiasts.com/develop"),
                mock.call("https://staging.boardenthusiasts.com/moderate"),
            ],
            wait_for_pages_shell.call_args_list,
        )

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

    def test_request_json_does_not_force_browser_user_agent(self) -> None:
        captured_user_agent: str | None = None

        class _Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self) -> bytes:
                return b'{"ok": true}'

        def fake_urlopen(request, timeout=15, context=None):
            nonlocal captured_user_agent
            captured_user_agent = request.headers.get("User-agent")
            return _Response()

        with mock.patch.object(dev.urllib.request, "urlopen", side_effect=fake_urlopen):
            payload = dev.request_json(url="https://example.com/api")

        self.assertEqual({"ok": True}, payload)
        self.assertIsNone(captured_user_agent)

    def test_is_expected_pages_shell_html_accepts_vite_spa_shell(self) -> None:
        html = """
<!doctype html>
<html lang="en">
  <head>
    <title>Board Enthusiasts | Community Hub for Board Players and Builders</title>
    <script type="module" crossorigin src="/assets/index-abc123.js"></script>
    <link rel="stylesheet" crossorigin href="/assets/index-def456.css">
  </head>
  <body>
    <div id="root"></div>
  </body>
</html>
"""

        self.assertTrue(dev.is_expected_pages_shell_html(html))

    def test_is_expected_pages_shell_html_rejects_unrelated_shell_without_brand_marker(self) -> None:
        html = """
<!doctype html>
<html lang="en">
  <head>
    <title>Example App</title>
    <script type="module" crossorigin src="/assets/index-abc123.js"></script>
    <link rel="stylesheet" crossorigin href="/assets/index-def456.css">
  </head>
  <body>
    <div id="root"></div>
  </body>
</html>
"""

        self.assertFalse(dev.is_expected_pages_shell_html(html))

    def test_is_expected_pages_shell_html_rejects_cloudflare_placeholder(self) -> None:
        html = """
<html>
  <head><title>Nothing is here yet</title></head>
  <body>Nothing is here yet</body>
</html>
"""

        self.assertFalse(dev.is_expected_pages_shell_html(html))

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

    def test_get_supabase_status_env_times_out_with_recovery_guidance(self) -> None:
        args = self.create_args()
        config = dev.config_from_args(args, pathlib.Path.cwd())

        with mock.patch.object(dev, "resolve_supabase_command_prefix", return_value=["npx", "supabase"]), mock.patch.object(
            dev,
            "run_command",
            side_effect=subprocess.TimeoutExpired(
                cmd=["npx", "supabase", "status", "-o", "env"],
                timeout=dev.SUPABASE_STATUS_TIMEOUT_SECONDS,
            ),
        ):
            with self.assertRaises(dev.DevCliError) as raised:
                dev.get_supabase_status_env(config)

        self.assertIn("timed out", str(raised.exception).lower())
        self.assertIn("database down", str(raised.exception))

    def test_get_local_supabase_urls_and_mailpit_respect_port_overrides(self) -> None:
        with mock.patch.dict(
            dev.os.environ,
            {
                "BOARD_ENTHUSIASTS_LOCAL_SUPABASE_API_PORT": "56421",
                "BOARD_ENTHUSIASTS_LOCAL_SUPABASE_DB_PORT": "56432",
                "BOARD_ENTHUSIASTS_LOCAL_MAILPIT_PORT": "56424",
            },
            clear=False,
        ):
            self.assertEqual("http://127.0.0.1:56421", dev.get_local_supabase_url())
            self.assertEqual("http://127.0.0.1:56421/auth/v1/health", dev.get_local_supabase_auth_url())
            self.assertEqual(56432, dev.get_local_supabase_db_port())
            self.assertEqual("http://127.0.0.1:56424", dev.get_local_mailpit_url())

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
                mock.patch.object(dev, "ensure_tcp_port_bindable"),
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
                mock.patch.object(dev, "ensure_tcp_port_bindable"),
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
                mock.patch.object(dev, "ensure_tcp_port_bindable"),
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
                mock.patch.object(dev, "ensure_tcp_port_bindable"),
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

    def test_run_supabase_start_validates_db_port_bindability_before_starting(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            supabase_root = repo_root / config.supabase_root
            supabase_root.mkdir(parents=True, exist_ok=True)

            with (
                mock.patch.object(dev, "ensure_migration_workspace_scaffolding"),
                mock.patch.object(dev, "ensure_docker_daemon_available"),
                mock.patch.object(
                    dev,
                    "ensure_tcp_port_bindable",
                    side_effect=dev.DevCliError("port is excluded"),
                ) as ensure_tcp_port_bindable,
                mock.patch.object(dev, "resolve_supabase_command_prefix", return_value=["npx", "supabase"]),
                mock.patch.object(dev, "run_command") as run_command,
            ):
                with self.assertRaises(dev.DevCliError) as raised:
                    dev.run_supabase_stack_command(config, action="start")

            ensure_tcp_port_bindable.assert_called_once_with(
                host="0.0.0.0",
                port=dev.LOCAL_SUPABASE_DB_PORT,
                description="local Supabase database",
            )
            run_command.assert_not_called()
            self.assertIn("port is excluded", str(raised.exception))

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

    def test_deploy_parser_defaults_to_production(self) -> None:
        parser = dev.build_parser()

        deploy_args = parser.parse_args(["deploy"])

        self.assertFalse(deploy_args.staging)
        self.assertFalse(deploy_args.force)
        self.assertFalse(deploy_args.upgrade)
        self.assertFalse(deploy_args.preflight_only)
        self.assertFalse(deploy_args.dry_run_only)

    def test_deploy_parser_accepts_staging_and_resume_flags(self) -> None:
        parser = dev.build_parser()

        deploy_args = parser.parse_args(["deploy", "--staging", "--upgrade", "--preflight-only"])
        legacy_args = parser.parse_args(["deploy-staging", "--force", "--dry-run-only"])
        legacy_pages_args = parser.parse_args(["deploy-staging", "--dry-run", "--pages-only"])
        legacy_workers_args = parser.parse_args(["deploy-staging", "--dry-run", "--workers-only"])

        self.assertTrue(deploy_args.staging)
        self.assertTrue(deploy_args.upgrade)
        self.assertTrue(deploy_args.preflight_only)
        self.assertTrue(legacy_args.force)
        self.assertTrue(legacy_args.dry_run_only)
        self.assertTrue(legacy_pages_args.dry_run_only)
        self.assertTrue(legacy_pages_args.pages_only)
        self.assertTrue(legacy_workers_args.dry_run_only)
        self.assertTrue(legacy_workers_args.workers_only)

    def test_run_legacy_staging_dry_run_pages_only_builds_spa(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())
        env_values = {
            "BOARD_ENTHUSIASTS_WORKERS_BASE_URL": "https://api.staging.boardenthusiasts.com",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_PUBLISHABLE_KEY": "publishable",
            "VITE_TURNSTILE_SITE_KEY": "turnstile-site-key",
            "VITE_LANDING_MODE": "true",
        }

        with mock.patch.object(
            dev,
            "require_environment_values",
            return_value=env_values,
        ), mock.patch.object(
            dev,
            "build_workspace_npm_command",
            return_value=["npm", "run", "build", "--workspace", "@board-enthusiasts/spa"],
        ) as build_workspace_npm_command, mock.patch.object(
            dev,
            "build_deploy_frontend_environment",
            return_value={"VITE_API_BASE_URL": "https://api.staging.boardenthusiasts.com"},
        ) as build_deploy_frontend_environment, mock.patch.object(dev, "run_command") as run_command:
            dev.run_legacy_staging_dry_run(config, pages_only=True, workers_only=False)

        build_workspace_npm_command.assert_called_once_with(
            script_name="build",
            workspace_name=config.migration_spa_workspace_name,
        )
        build_deploy_frontend_environment.assert_called_once_with(env_values)
        run_command.assert_called_once_with(
            ["npm", "run", "build", "--workspace", "@board-enthusiasts/spa"],
            cwd=config.repo_root,
            env={"VITE_API_BASE_URL": "https://api.staging.boardenthusiasts.com"},
        )

    def test_run_legacy_staging_dry_run_workers_only_dry_runs_worker(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())
        env_values = {
            "BOARD_ENTHUSIASTS_WORKERS_BASE_URL": "https://api.staging.boardenthusiasts.com",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_PUBLISHABLE_KEY": "publishable",
            "SUPABASE_AVATARS_BUCKET": "avatars",
            "SUPABASE_CARD_IMAGES_BUCKET": "card-images",
            "SUPABASE_HERO_IMAGES_BUCKET": "hero-images",
            "SUPABASE_LOGO_IMAGES_BUCKET": "logo-images",
            "CLOUDFLARE_ACCOUNT_ID": "account-id",
            "CLOUDFLARE_API_TOKEN": "token",
            "BREVO_SIGNUPS_LIST_ID": "3",
            "ALLOWED_WEB_ORIGINS": "https://staging.boardenthusiasts.com",
            "SUPPORT_REPORT_RECIPIENT": "support@boardenthusiasts.com",
            "SUPPORT_REPORT_SENDER_EMAIL": "noreply@boardenthusiasts.com",
            "SUPPORT_REPORT_SENDER_NAME": "Board Enthusiasts",
        }

        with mock.patch.object(
            dev,
            "require_environment_values",
            return_value=env_values,
        ), mock.patch.object(
            dev,
            "build_subprocess_env",
            return_value={"CLOUDFLARE_API_TOKEN": "token", "CLOUDFLARE_ACCOUNT_ID": "account-id"},
        ) as build_subprocess_env, mock.patch.object(
            dev,
            "get_deploy_worker_config_path",
            return_value=pathlib.Path("generated-wrangler.jsonc"),
        ) as get_deploy_worker_config_path, mock.patch.object(dev, "run_command") as run_command:
            dev.run_legacy_staging_dry_run(config, pages_only=False, workers_only=True)

        build_subprocess_env.assert_called_once()
        get_deploy_worker_config_path.assert_called_once_with(config, target="staging", env_values=env_values)
        run_command.assert_called_once_with(
            ["npx", "wrangler", "deploy", "--dry-run", "--config", "generated-wrangler.jsonc"],
            cwd=config.repo_root,
            env={"CLOUDFLARE_API_TOKEN": "token", "CLOUDFLARE_ACCOUNT_ID": "account-id"},
        )

    def test_env_parser_accepts_github_environment_sync_flags(self) -> None:
        parser = dev.build_parser()

        env_args = parser.parse_args(
            [
                "env",
                "staging",
                "--sync-github-environment",
                "--github-environment",
                "staging-release",
                "--repo",
                "matt-stroman/board-enthusiasts",
            ]
        )

        self.assertEqual("staging", env_args.target)
        self.assertTrue(env_args.sync_github_environment)
        self.assertEqual("staging-release", env_args.github_environment)
        self.assertEqual("matt-stroman/board-enthusiasts", env_args.repo)

    def test_sync_root_environment_file_to_github_environment_sets_vars_and_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            config = dev.config_from_args(self.create_args(), repo_root)
            env_path = repo_root / config.staging_env_file
            env_path.parent.mkdir(parents=True, exist_ok=True)
            env_path.write_text(
                "\n".join(
                    [
                        "BOARD_ENTHUSIASTS_APP_ENV=staging",
                        "SUPABASE_PUBLISHABLE_KEY=publishable",
                        "SUPABASE_SECRET_KEY=secret",
                        "SUPABASE_URL=",
                        "BREVO_SIGNUPS_LIST_ID=3",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            run_calls: list[list[str]] = []

            def fake_run_command(cmd, **kwargs):
                run_calls.append(list(cmd))
                if cmd[:3] == ["gh", "auth", "status"]:
                    return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            with (
                mock.patch.object(dev, "assert_command_available"),
                mock.patch.object(dev, "resolve_github_cli_executable", return_value="gh"),
                mock.patch.object(dev, "run_command", side_effect=fake_run_command),
            ):
                dev.sync_root_environment_file_to_github_environment(
                    config,
                    target="staging",
                    github_environment=None,
                    github_repo="matt-stroman/board-enthusiasts",
                )

        self.assertEqual(["gh", "auth", "status"], run_calls[0][:3])
        self.assertIn(
            [
                "gh",
                "variable",
                "set",
                "BOARD_ENTHUSIASTS_APP_ENV",
                "--env",
                "staging",
                "--body",
                "staging",
                "--repo",
                "matt-stroman/board-enthusiasts",
            ],
            run_calls,
        )
        self.assertIn(
            [
                "gh",
                "variable",
                "set",
                "SUPABASE_PUBLISHABLE_KEY",
                "--env",
                "staging",
                "--body",
                "publishable",
                "--repo",
                "matt-stroman/board-enthusiasts",
            ],
            run_calls,
        )
        self.assertIn(
            [
                "gh",
                "secret",
                "set",
                "SUPABASE_SECRET_KEY",
                "--env",
                "staging",
                "--repo",
                "matt-stroman/board-enthusiasts",
            ],
            run_calls,
        )
        flattened = [" ".join(call) for call in run_calls]
        self.assertFalse(any("SUPABASE_URL" in call for call in flattened))

    def test_sync_root_environment_file_to_github_environment_rejects_local_target(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())

        with self.assertRaises(dev.DevCliError) as raised:
            dev.sync_root_environment_file_to_github_environment(
                config,
                target="local",
                github_environment=None,
                github_repo=None,
            )

        self.assertIn("staging or production", str(raised.exception))

    def test_infer_github_repo_from_origin_supports_https_remote(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())

        with mock.patch.object(
            dev,
            "run_command",
            return_value=subprocess.CompletedProcess(
                ["git", "config", "--get", "remote.origin.url"],
                0,
                stdout="https://github.com/matt-stroman/board-enthusiasts.git\n",
                stderr="",
            ),
        ):
            self.assertEqual("matt-stroman/board-enthusiasts", dev.infer_github_repo_from_origin(config))

    def test_assert_github_environment_sync_detects_var_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            config = dev.config_from_args(self.create_args(), repo_root)
            env_path = repo_root / config.staging_env_file
            env_path.parent.mkdir(parents=True, exist_ok=True)
            env_path.write_text(
                "\n".join(
                    [
                        "BOARD_ENTHUSIASTS_APP_ENV=staging",
                        "SUPABASE_PUBLISHABLE_KEY=publishable",
                        "SUPABASE_SECRET_KEY=secret",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            def fake_run_command(cmd, **kwargs):
                normalized = list(cmd)
                if normalized[:3] == ["gh", "auth", "status"]:
                    return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")
                if normalized[:2] == ["git", "config"]:
                    return subprocess.CompletedProcess(cmd, 0, stdout="https://github.com/matt-stroman/board-enthusiasts.git\n", stderr="")
                if normalized[:2] == ["gh", "api"]:
                    path = normalized[2]
                    if path.endswith("/environments/staging"):
                        return subprocess.CompletedProcess(cmd, 0, stdout='{"name":"staging"}', stderr="")
                    if path.endswith("/variables?per_page=100"):
                        return subprocess.CompletedProcess(
                            cmd,
                            0,
                            stdout=json.dumps({"variables": [{"name": "BOARD_ENTHUSIASTS_APP_ENV", "value": "staging"}]}),
                            stderr="",
                        )
                    if path.endswith("/secrets?per_page=100"):
                        return subprocess.CompletedProcess(
                            cmd,
                            0,
                            stdout=json.dumps({"secrets": [{"name": "SUPABASE_SECRET_KEY"}]}),
                            stderr="",
                        )
                raise AssertionError(f"Unexpected command: {normalized}")

            with (
                mock.patch.object(dev, "assert_command_available"),
                mock.patch.object(dev, "resolve_github_cli_executable", return_value="gh"),
                mock.patch.object(dev, "run_command", side_effect=fake_run_command),
                mock.patch.dict(dev.os.environ, {}, clear=True),
            ):
                with self.assertRaises(dev.DevCliError) as raised:
                    dev.assert_github_environment_sync(config, target="staging")

        self.assertIn("mismatched vars", str(raised.exception))

    def test_assert_github_environment_sync_skips_inside_github_actions(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())

        with (
            mock.patch.object(dev, "assert_command_available") as assert_command_available,
            mock.patch.object(dev, "run_command") as run_command,
            mock.patch.dict(dev.os.environ, {"GITHUB_ACTIONS": "true"}, clear=False),
        ):
            dev.assert_github_environment_sync(config, target="staging")

        assert_command_available.assert_not_called()
        run_command.assert_not_called()

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
