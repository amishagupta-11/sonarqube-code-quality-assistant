import asyncio
import logging
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

SRC_PATH = Path(__file__).resolve().parents[1] / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from sonarqube_quality_assistant.server.notifications import (
    build_issue_severity_changed_notification,
    build_new_blocker_issue_notification,
    build_quality_gate_changed_notification,
    get_notification_catalog,
)
from sonarqube_quality_assistant.server.prompts import register_prompts
from sonarqube_quality_assistant.server.resources import register_resources
from sonarqube_quality_assistant.server.sampling import (
    build_issue_sampling_payload,
    build_sampling_flow_description,
)
from sonarqube_quality_assistant.server.watcher import _poll_loop, watcher_lifespan
from sonarqube_quality_assistant.utils.logger import get_logger

class FakeMCP:
    def __init__(self):
        self.resources = {}
        self.prompts = []

    def resource(self, uri):
        def decorator(func):
            self.resources[uri] = func
            return func

        return decorator

    def prompt(self):
        def decorator(func):
            self.prompts.append(func)
            return func

        return decorator

class NotificationTests(unittest.TestCase):
    def test_quality_gate_notification_uses_fallbacks(self):
        notification = build_quality_gate_changed_notification(
            "app", "OK", None, None
        )

        self.assertEqual(notification["type"], "sonarqube.quality_gate.changed")
        self.assertEqual(notification["payload"]["current_status"], "UNAVAILABLE")
        self.assertEqual(notification["payload"]["analyzed_at"], "UNAVAILABLE")
        self.assertIn("OK -> UNAVAILABLE", notification["payload"]["summary"])

    def test_new_blocker_notification_uses_fallbacks(self):
        notification = build_new_blocker_issue_notification(
            "app", None, None, None, None
        )

        self.assertEqual(notification["type"], "sonarqube.issue.blocker_created")
        self.assertEqual(notification["payload"]["issue_key"], "UNAVAILABLE")
        self.assertEqual(notification["payload"]["component"], "UNAVAILABLE")
        self.assertEqual(notification["payload"]["message"], "UNAVAILABLE")
        self.assertEqual(notification["payload"]["introduced_at"], "UNAVAILABLE")

    def test_issue_severity_changed_notification_formats_summary(self):
        notification = build_issue_severity_changed_notification(
            "app", "ISSUE-1", "MAJOR", "BLOCKER"
        )

        self.assertEqual(notification["payload"]["previous_severity"], "MAJOR")
        self.assertEqual(notification["payload"]["current_severity"], "BLOCKER")
        self.assertIn("MAJOR -> BLOCKER", notification["payload"]["summary"])

    def test_notification_catalog_lists_supported_events(self):
        catalog = get_notification_catalog()

        events = {item["event"] for item in catalog}

        self.assertEqual(
            events,
            {
                "sonarqube.quality_gate.changed",
                "sonarqube.issue.blocker_created",
                "sonarqube.issue.severity_changed",
            },
        )

class SamplingTests(unittest.TestCase):
    def test_issue_sampling_payload_limits_to_first_thirty_issues(self):
        issues = [
            {
                "key": f"ISSUE-{index}",
                "severity": "MAJOR",
                "type": "CODE_SMELL",
                "component": "app:file.py",
                "line": index,
                "message": f"Message {index}",
                "rule": "python:S1",
                "effort": "5min",
            }
            for index in range(35)
        ]

        payload = build_issue_sampling_payload("app", {"issues": issues})

        self.assertEqual(payload["project_key"], "app")
        self.assertEqual(payload["issue_count"], 30)
        self.assertEqual(len(payload["issues"]), 30)
        self.assertEqual(payload["issues"][0]["key"], "ISSUE-0")
        self.assertEqual(payload["issues"][-1]["key"], "ISSUE-29")
        self.assertIn("Group SonarQube issues by root-cause pattern", payload["sampling_purpose"])

    def test_sampling_flow_description_has_four_steps_in_order(self):
        flow = build_sampling_flow_description()

        self.assertEqual([step["step"] for step in flow], [
            "server_to_client",
            "client_to_llm",
            "llm_to_client",
            "client_to_server",
        ])

class ResourceAndPromptTests(unittest.IsolatedAsyncioTestCase):
    async def test_register_resources_binds_all_expected_handlers(self):
        fake_mcp = FakeMCP()

        with patch(
            "sonarqube_quality_assistant.server.resources.ProjectService"
        ) as mock_project_service_class, patch(
            "sonarqube_quality_assistant.server.resources.notification_runtime"
        ) as mock_notification_runtime:
            project_service = AsyncMock()
            mock_project_service_class.return_value = project_service
            project_service.list_projects.return_value = {"projects": []}
            project_service.get_project_overview.return_value = {"project_key": "app"}
            project_service.list_project_branches.return_value = {"branches": []}
            project_service.get_branch_overview.return_value = {"branch": "main"}
            project_service.get_project_issues.return_value = {"issues": []}
            project_service.get_branch_issues.return_value = {"issues": []}
            project_service.get_project_hotspots.return_value = {"hotspots": []}
            mock_notification_runtime.list_notifications = AsyncMock(
                return_value={"notifications": []}
            )

            register_resources(fake_mcp)

            self.assertEqual(
                set(fake_mcp.resources),
                {
                    "sonar://projects",
                    "sonar://project/{project_key}/overview",
                    "sonar://project/{project_key}/branches",
                    "sonar://project/{project_key}/branch/{branch}/overview",
                    "sonar://project/{project_key}/issues",
                    "sonar://project/{project_key}/branch/{branch}/issues",
                    "sonar://project/{project_key}/hotspots",
                    "sonar://notifications",
                },
            )

            self.assertEqual(await fake_mcp.resources["sonar://projects"](), {"projects": []})
            self.assertEqual(
                await fake_mcp.resources["sonar://project/{project_key}/overview"]("app"),
                {"project_key": "app"},
            )
            self.assertEqual(
                await fake_mcp.resources["sonar://project/{project_key}/branches"]("app"),
                {"branches": []},
            )
            self.assertEqual(
                await fake_mcp.resources["sonar://project/{project_key}/branch/{branch}/overview"](
                    "app", "main"
                ),
                {"branch": "main"},
            )
            self.assertEqual(
                await fake_mcp.resources["sonar://project/{project_key}/issues"]("app"),
                {"issues": []},
            )
            self.assertEqual(
                await fake_mcp.resources["sonar://project/{project_key}/branch/{branch}/issues"](
                    "app", "main"
                ),
                {"issues": []},
            )
            self.assertEqual(
                await fake_mcp.resources["sonar://project/{project_key}/hotspots"]("app"),
                {"hotspots": []},
            )
            self.assertEqual(
                await fake_mcp.resources["sonar://notifications"](),
                {"notifications": []},
            )

    def test_register_prompts_adds_pr_readiness_prompt(self):
        fake_mcp = FakeMCP()

        register_prompts(fake_mcp)

        self.assertEqual(len(fake_mcp.prompts), 1)
        prompt_text = fake_mcp.prompts[0]("app", "feature/login")
        self.assertIn("System role: SonarQube PR readiness analyst.", prompt_text)
        self.assertIn("Project key: app", prompt_text)
        self.assertIn("Branch: feature/login", prompt_text)
        self.assertIn("4. Decide whether the PR is Ready or Not Ready.", prompt_text)

class LoggerTests(unittest.TestCase):
    @patch("sonarqube_quality_assistant.utils.logger.logging.getLogger")
    @patch("sonarqube_quality_assistant.utils.logger.logging.basicConfig")
    def test_get_logger_configures_logging_and_returns_named_logger(
        self, mock_basic_config, mock_get_logger
    ):
        logger = Mock(spec=logging.Logger)
        mock_get_logger.return_value = logger

        result = get_logger("quality")

        mock_basic_config.assert_called_once_with(
            level=logging.INFO,
            format="[%(levelname)s] [%(name)s] %(message)s",
        )
        mock_get_logger.assert_called_once_with("quality")
        self.assertIs(result, logger)

class WatcherTests(unittest.IsolatedAsyncioTestCase):
    async def test_poll_loop_polls_once_and_stops_after_timeout_then_event(self):
        stop_event = asyncio.Event()

        with patch(
            "sonarqube_quality_assistant.server.watcher.notification_runtime"
        ) as mock_runtime, patch(
            "sonarqube_quality_assistant.server.watcher.logger"
        ) as mock_logger:
            def poll_once_side_effect():
                stop_event.set()

            mock_runtime.poll_once = AsyncMock(side_effect=poll_once_side_effect)

            await _poll_loop(0, stop_event)

            mock_runtime.poll_once.assert_awaited_once_with()
            mock_logger.info.assert_called_with("Polling all watched projects...")

    async def test_watcher_lifespan_bootstraps_projects_and_exposes_runtime(self):
        with patch(
            "sonarqube_quality_assistant.server.watcher.get_optional_env",
            side_effect=["5", "app-1, app-2"],
        ), patch(
            "sonarqube_quality_assistant.server.watcher.notification_runtime"
        ) as mock_runtime:
            mock_runtime.add_project = AsyncMock()
            mock_runtime.poll_once = AsyncMock()

            with self.assertRaises(asyncio.CancelledError):
                async with watcher_lifespan(object()) as state:
                    self.assertEqual(state["notification_runtime"], mock_runtime)
                    self.assertEqual(
                        [call.args[0] for call in mock_runtime.add_project.await_args_list],
                        ["app-1", "app-2"],
                    )

    async def test_watcher_lifespan_logs_bootstrap_failures(self):
        with patch(
            "sonarqube_quality_assistant.server.watcher.get_optional_env",
            side_effect=["5", "app-1"],
        ), patch(
            "sonarqube_quality_assistant.server.watcher.notification_runtime"
        ) as mock_runtime, patch(
            "sonarqube_quality_assistant.server.watcher.logger"
        ) as mock_logger:
            mock_runtime.add_project = AsyncMock(side_effect=RuntimeError("boom"))
            mock_runtime.poll_once = AsyncMock()

            with self.assertRaises(asyncio.CancelledError):
                async with watcher_lifespan(object()) as state:
                    self.assertIs(state["notification_runtime"], mock_runtime)

            mock_logger.warning.assert_called_once()
            self.assertIn(
                "Failed to bootstrap notification watch for app-1",
                mock_logger.warning.call_args.args[0],
        )