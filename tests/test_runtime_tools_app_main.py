import asyncio
import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

SRC_PATH = Path(__file__).resolve().parents[1] / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

if "groq" not in sys.modules:
    fake_groq_module = types.ModuleType("groq")
    fake_groq_module.Groq = Mock
    sys.modules["groq"] = fake_groq_module

from sonarqube_quality_assistant.server.notification_runtime import (
    NotificationRuntime,
    ProjectWatchState,
)
from sonarqube_quality_assistant.server.tools import (
    _build_groq_messages,
    _build_readiness_reasons,
    _build_readiness_report,
    _count_issues_by_severity,
    _get_analyzed_at,
    _handle_blocker_issue_notification,
    _handle_quality_gate_notification,
    register_tools,
)

class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator

class ToolHelperTests(unittest.IsolatedAsyncioTestCase):
    async def test_quality_gate_notification_requires_previous_status(self):
        project_service = AsyncMock()

        with self.assertRaisesRegex(ValueError, "previous_status is required"):
            await _handle_quality_gate_notification("app", None, project_service)

    async def test_handle_quality_gate_notification_emits_payload(self):
        project_service = AsyncMock()
        project_service.get_quality_gate_status.return_value = {
            "projectStatus": {"status": "ERROR", "period": {"date": "2026-04-23"}},
        }

        with patch(
            "sonarqube_quality_assistant.server.tools.notification_runtime"
        ) as mock_runtime:
            mock_runtime._emit_notification = AsyncMock()

            result = await _handle_quality_gate_notification("app", "OK", project_service)

        self.assertEqual(
            result["notification"]["payload"]["summary"],
            "Quality gate changed for app: OK -> ERROR.",
        )
        mock_runtime._emit_notification.assert_awaited_once()

    async def test_handle_blocker_issue_notification_raises_when_no_issue_exists(self):
        issue_service = AsyncMock()
        issue_service.get_latest_blocker_issue.return_value = None

        with self.assertRaisesRegex(ValueError, "No open BLOCKER issues found"):
            await _handle_blocker_issue_notification("app", issue_service)

    async def test_handle_blocker_issue_notification_emits_payload(self):
        issue_service = AsyncMock()
        issue_service.get_latest_blocker_issue.return_value = {
            "key": "ISSUE-1",
            "component": "app:file.py",
            "message": "Critical problem",
            "creationDate": "2026-04-23",
        }

        with patch(
            "sonarqube_quality_assistant.server.tools.notification_runtime"
        ) as mock_runtime:
            mock_runtime._emit_notification = AsyncMock()

            result = await _handle_blocker_issue_notification("app", issue_service)

        self.assertEqual(result["notification"]["payload"]["issue_key"], "ISSUE-1")
        mock_runtime._emit_notification.assert_awaited_once()

    def test_readiness_helpers_cover_positive_and_negative_paths(self):
        issues = [
            {"severity": "BLOCKER"},
            {"severity": "CRITICAL"},
            {"severity": "MAJOR"},
        ]

        blocker_count = _count_issues_by_severity(issues, "BLOCKER")
        reasons = _build_readiness_reasons("ERROR", blocker_count, 1, 72.5)
        report = _build_readiness_report(
            "app",
            "feature/test",
            "Not Ready",
            "ERROR",
            72.5,
            3,
            blocker_count,
            1,
            reasons,
        )
        clean_report = _build_readiness_report(
            "app",
            "main",
            "PR Ready",
            "OK",
            95.0,
            0,
            0,
            0,
            [],
        )

        self.assertEqual(blocker_count, 1)
        self.assertEqual(len(reasons), 4)
        self.assertIn("Coverage is 72.5%, which is below the 80% target.", report)
        self.assertIn("No blocker conditions detected", clean_report)

    def test_groq_messages_and_analyzed_at_fallbacks(self):
        payload = {
            "project_key": "app",
            "instruction": "Analyze these issues.",
            "issues": [{"key": "ISSUE-1"}],
        }

        messages = _build_groq_messages(payload)

        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("Project key: app", messages[1]["content"])
        self.assertEqual(
            _get_analyzed_at({"period": {"date": "2026-04-23"}}, {}),
            "2026-04-23",
        )
        self.assertEqual(
            _get_analyzed_at({"analysedAt": "2026-04-22"}, {}),
            "2026-04-22",
        )
        self.assertEqual(
            _get_analyzed_at({}, {"analysedAt": "2026-04-21"}),
            "2026-04-21",
        )

class RegisterToolsTests(unittest.IsolatedAsyncioTestCase):
    async def test_register_tools_exposes_all_handlers_and_routes_calls(self):
        fake_mcp = FakeMCP()

        with patch(
            "sonarqube_quality_assistant.server.tools.QualityReportService"
        ) as mock_quality_report_class, patch(
            "sonarqube_quality_assistant.server.tools.IssueService"
        ) as mock_issue_service_class, patch(
            "sonarqube_quality_assistant.server.tools.ComparisonService"
        ) as mock_comparison_service_class, patch(
            "sonarqube_quality_assistant.server.tools.ProjectService"
        ) as mock_project_service_class, patch(
            "sonarqube_quality_assistant.server.tools.notification_runtime"
        ) as mock_runtime, patch(
            "sonarqube_quality_assistant.server.tools.Groq"
        ) as mock_groq_class:
            quality_report_service = AsyncMock()
            issue_service = AsyncMock()
            comparison_service = AsyncMock()
            project_service = AsyncMock()
            mock_quality_report_class.return_value = quality_report_service
            mock_issue_service_class.return_value = issue_service
            mock_comparison_service_class.return_value = comparison_service
            mock_project_service_class.return_value = project_service

            quality_report_service.get_quality_report.return_value = "report"
            issue_service.find_critical_issues.return_value = "critical issues"
            comparison_service.compare_projects.return_value = "comparison"
            project_service.list_projects.return_value = {"projects": ["app"]}
            project_service.list_project_branches.return_value = {"branches": ["main"]}
            project_service.get_branch_overview.return_value = {
                "quality_gate_status": "OK",
                "metrics": {"coverage": 91.2},
            }
            project_service.get_branch_issues.return_value = {
                "total": 2,
                "issues": [{"severity": "MAJOR"}, {"severity": "INFO"}],
            }
            project_service.get_project_issues.return_value = {
                "issues": [{"key": "ISSUE-1", "severity": "MAJOR", "message": "Fix"}]
            }
            mock_runtime.add_project = AsyncMock(return_value={"watched_projects": ["app"]})
            mock_runtime.remove_project = AsyncMock(return_value={"watched_projects": []})
            mock_runtime.list_notifications = AsyncMock(return_value={"notifications": []})
            mock_runtime._emit_notification = AsyncMock()
            issue_service.assign_issue.return_value = {"success": True}
            issue_service.get_latest_blocker_issue.return_value = {
                "key": "ISSUE-9",
                "component": "app:file.py",
                "message": "Blocker",
                "creationDate": "2026-04-23",
            }
            project_service.get_quality_gate_status.return_value = {
                "projectStatus": {"status": "ERROR", "period": {"date": "2026-04-23"}}
            }

            groq_client = Mock()
            groq_response = Mock()
            groq_response.model = "llama-3.3-70b-versatile"
            groq_response.choices = [
                Mock(
                    finish_reason="stop",
                    message=Mock(content='{"root_cause_groups": []}'),
                )
            ]
            groq_client.chat.completions.create.return_value = groq_response
            mock_groq_class.return_value = groq_client

            register_tools(fake_mcp)

            self.assertEqual(
                set(fake_mcp.tools),
                {
                    "list_projects",
                    "get_quality_report",
                    "find_critical_issues",
                    "compare_quality",
                    "list_project_branches",
                    "check_pr_readiness",
                    "prepare_issue_sampling",
                    "group_issue_patterns_with_sampling",
                    "list_notification_types",
                    "watch_project_notifications",
                    "unwatch_project_notifications",
                    "get_recent_notifications",
                    "preview_notification_event",
                    "assign_issue",
                },
            )

            self.assertEqual(await fake_mcp.tools["list_projects"](), {"projects": ["app"]})
            self.assertEqual(
                await fake_mcp.tools["get_quality_report"]("app", "last_30d"),
                "report",
            )
            self.assertEqual(
                await fake_mcp.tools["find_critical_issues"]("app", "CRITICAL", "BUG", "alice"),
                "critical issues",
            )
            self.assertEqual(
                await fake_mcp.tools["compare_quality"]("app", "other"),
                "comparison",
            )
            self.assertEqual(
                await fake_mcp.tools["list_project_branches"]("app"),
                {"branches": ["main"]},
            )

            readiness = await fake_mcp.tools["check_pr_readiness"]("app", "feature/demo")
            self.assertIn("Verdict: PR Ready", readiness)

            sampling = await fake_mcp.tools["prepare_issue_sampling"]("app")
            self.assertEqual(sampling["sampling_payload"]["project_key"], "app")
            self.assertEqual(len(sampling["sampling_flow"]), 4)

            grouped = await fake_mcp.tools["group_issue_patterns_with_sampling"]("app", None)
            self.assertEqual(grouped["llm_result"]["model"], "llama-3.3-70b-versatile")
            self.assertEqual(grouped["llm_result"]["stop_reason"], "stop")

            self.assertIn("notifications", await fake_mcp.tools["list_notification_types"]())
            self.assertEqual(
                await fake_mcp.tools["watch_project_notifications"]("app"),
                {"watched_projects": ["app"]},
            )
            self.assertEqual(
                await fake_mcp.tools["unwatch_project_notifications"]("app"),
                {"watched_projects": []},
            )
            self.assertEqual(
                await fake_mcp.tools["get_recent_notifications"](),
                {"notifications": []},
            )

            quality_gate_preview = await fake_mcp.tools["preview_notification_event"](
                "sonarqube.quality_gate.changed", "app", "OK"
            )
            blocker_preview = await fake_mcp.tools["preview_notification_event"](
                "sonarqube.issue.blocker_created", "app", "OK"
            )
            self.assertEqual(
                quality_gate_preview["notification"]["type"],
                "sonarqube.quality_gate.changed",
            )
            self.assertEqual(
                blocker_preview["notification"]["type"],
                "sonarqube.issue.blocker_created",
            )
            self.assertEqual(
                await fake_mcp.tools["assign_issue"]("ISSUE-9", "alice"),
                {"success": True},
            )

class NotificationRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        logger_patcher = patch(
            "sonarqube_quality_assistant.server.notification_runtime.get_logger"
        )
        self.addCleanup(logger_patcher.stop)
        self.mock_get_logger = logger_patcher.start()
        self.mock_logger = Mock()
        self.mock_get_logger.return_value = self.mock_logger
        self.runtime = NotificationRuntime()

    async def test_add_remove_and_list_projects_and_notifications(self):
        self.runtime._prime_project_state = AsyncMock()

        add_result = await self.runtime.add_project("app")
        watched = await self.runtime.list_watched_projects()
        self.runtime._notifications.append({"type": "sample"})
        listed = await self.runtime.list_notifications()
        remove_result = await self.runtime.remove_project("app")

        self.assertEqual(add_result, {"success": True, "watched_projects": ["app"]})
        self.assertEqual(watched, {"watched_projects": ["app"]})
        self.assertEqual(listed["notifications"], [{"type": "sample"}])
        self.assertEqual(remove_result, {"success": True, "watched_projects": []})

    async def test_register_listener_and_emit_notification(self):
        listener = AsyncMock()
        self.runtime.register_listener(listener)

        await self.runtime._emit_notification({"type": "event"})

        listener.assert_awaited_once_with({"type": "event"})

    async def test_poll_once_logs_warning_when_project_poll_fails(self):
        self.runtime._watched_projects = {"app"}
        self.runtime._poll_project = AsyncMock(side_effect=RuntimeError("boom"))

        await self.runtime.poll_once()

        self.mock_logger.warning.assert_called_once()
        self.assertIn("Notification polling failed for app", self.mock_logger.warning.call_args.args[0])

    async def test_prime_project_state_builds_blocker_and_severity_indexes(self):
        service = AsyncMock()
        service.get_quality_gate_status.return_value = {
            "projectStatus": {"status": "WARN"}
        }
        service.get_project_issues.return_value = {
            "issues": [
                {"key": "ISSUE-1", "severity": "BLOCKER"},
                {"key": "ISSUE-2", "severity": "CRITICAL"},
                {"key": None, "severity": "MAJOR"},
            ]
        }
        self.runtime._project_service = service

        await self.runtime._prime_project_state("app")

        state = self.runtime._project_states["app"]
        self.assertEqual(state.quality_gate_status, "WARN")
        self.assertEqual(state.blocker_issue_keys, {"ISSUE-1"})
        self.assertEqual(
            state.issue_severities,
            {"ISSUE-1": "BLOCKER", "ISSUE-2": "CRITICAL"},
        )
        self.mock_logger.info.assert_called()

    async def test_poll_project_emits_quality_gate_blocker_and_severity_notifications(self):
        service = AsyncMock()
        service.get_quality_gate_status.return_value = {
            "projectStatus": {"status": "ERROR", "period": {"date": "2026-04-23"}}
        }
        service.get_project_issues.return_value = {
            "issues": [
                {
                    "key": "ISSUE-1",
                    "severity": "BLOCKER",
                    "component": "app:file.py",
                    "message": "New blocker",
                    "creationDate": "2026-04-23",
                },
                {
                    "key": "ISSUE-2",
                    "severity": "BLOCKER",
                    "component": "app:file2.py",
                    "message": "Escalated issue",
                    "creationDate": "2026-04-23",
                },
            ]
        }
        self.runtime._project_service = service
        self.runtime._project_states["app"] = ProjectWatchState(
            quality_gate_status="OK",
            blocker_issue_keys={"ISSUE-1"},
            issue_severities={"ISSUE-1": "BLOCKER", "ISSUE-2": "MAJOR"},
        )
        listener = AsyncMock()
        self.runtime.register_listener(listener)

        await self.runtime._poll_project("app")

        self.assertEqual(len(self.runtime._notifications), 3)
        self.assertEqual(self.runtime._notifications[0]["type"], "sonarqube.issue.severity_changed")
        self.assertEqual(self.runtime._notifications[1]["type"], "sonarqube.issue.blocker_created")
        self.assertEqual(self.runtime._notifications[2]["type"], "sonarqube.quality_gate.changed")
        self.assertEqual(listener.await_count, 3)
        self.assertEqual(self.runtime._project_states["app"].quality_gate_status, "ERROR")
        self.assertEqual(self.runtime._project_states["app"].blocker_issue_keys, {"ISSUE-1", "ISSUE-2"})

    def test_get_project_service_creates_instance_once(self):
        with patch(
            "sonarqube_quality_assistant.server.notification_runtime.ProjectService"
        ) as mock_project_service_class:
            first = self.runtime._get_project_service()
            second = self.runtime._get_project_service()

        self.assertIs(first, second)
        mock_project_service_class.assert_called_once_with()

class AppAndMainTests(unittest.IsolatedAsyncioTestCase):
    def _reload_app_module(self):
        sys.modules.pop("sonarqube_quality_assistant.server.app", None)
        return importlib.import_module("sonarqube_quality_assistant.server.app")

    async def test_app_module_wires_server_and_runtime_notifications(self):
        fake_handle = AsyncMock(return_value="handled")
        fake_request_context = Mock()
        fake_request_context.get.return_value = types.SimpleNamespace(session="session-1")
        fake_fast_mcp = Mock()
        fake_fast_mcp._mcp_server = types.SimpleNamespace(
            _handle_request=fake_handle,
            request_context=fake_request_context,
        )

        with patch("mcp.server.fastmcp.FastMCP", return_value=fake_fast_mcp), patch(
            "sonarqube_quality_assistant.server.resources.register_resources"
        ) as mock_register_resources, patch(
            "sonarqube_quality_assistant.server.tools.register_tools"
        ) as mock_register_tools, patch(
            "sonarqube_quality_assistant.server.prompts.register_prompts"
        ) as mock_register_prompts, patch(
            "sonarqube_quality_assistant.server.notifications.get_notification_catalog",
            return_value=[{"event": "x"}],
        ), patch(
            "sonarqube_quality_assistant.server.notification_runtime.notification_runtime"
        ) as mock_runtime, patch(
            "sonarqube_quality_assistant.utils.env.load_env"
        ), patch(
            "logging.getLogger"
        ) as mock_get_logger:
            mock_log = Mock()
            mock_get_logger.return_value = mock_log
            module = self._reload_app_module()

            mock_runtime.register_listener.assert_called_once()
            mock_register_resources.assert_called_once_with(fake_fast_mcp)
            mock_register_tools.assert_called_once_with(fake_fast_mcp)
            mock_register_prompts.assert_called_once_with(fake_fast_mcp)
            self.assertEqual(module.NOTIFICATION_CATALOG, [{"event": "x"}])

            result = await module._patched_handle_request("request")
            self.assertEqual(result, "handled")
            self.assertEqual(module._active_session, "session-1")

    async def test_app_notification_sender_handles_missing_success_and_failure_sessions(self):
        fake_handle = AsyncMock(return_value="handled")
        fake_request_context = Mock()
        fake_request_context.get.return_value = None
        fake_fast_mcp = Mock()
        fake_fast_mcp._mcp_server = types.SimpleNamespace(
            _handle_request=fake_handle,
            request_context=fake_request_context,
        )

        with patch("mcp.server.fastmcp.FastMCP", return_value=fake_fast_mcp), patch(
            "sonarqube_quality_assistant.server.resources.register_resources"
        ), patch(
            "sonarqube_quality_assistant.server.tools.register_tools"
        ), patch(
            "sonarqube_quality_assistant.server.prompts.register_prompts"
        ), patch(
            "sonarqube_quality_assistant.server.notifications.get_notification_catalog",
            return_value=[],
        ), patch(
            "sonarqube_quality_assistant.server.notification_runtime.notification_runtime"
        ), patch(
            "sonarqube_quality_assistant.utils.env.load_env"
        ), patch(
            "logging.getLogger"
        ) as mock_get_logger:
            mock_log = Mock()
            mock_get_logger.return_value = mock_log
            module = self._reload_app_module()

            module._active_session = None
            await module.send_runtime_notification({"type": "first"})
            mock_log.warning.assert_called_with("No active session yet, notification dropped")

            session = AsyncMock()
            module._active_session = session
            await module.send_runtime_notification({"type": "second"})
            session.send_log_message.assert_awaited_once_with(
                level="info",
                data={"type": "second"},
                logger="sonarqube-quality-assistant",
            )

            failing_session = AsyncMock()
            failing_session.send_log_message.side_effect = RuntimeError("send failed")
            module._active_session = failing_session
            await module.send_runtime_notification({"type": "third"})
            self.assertIsNone(module._active_session)
            mock_log.error.assert_called()

    def test_main_runs_mcp_and_re_raises_failures(self):
        sys.modules.pop("sonarqube_quality_assistant.server.app", None)
        fake_mcp = Mock()
        fake_module = types.ModuleType("sonarqube_quality_assistant.server.app")
        fake_module.mcp = fake_mcp

        with patch.dict(
            sys.modules,
            {"sonarqube_quality_assistant.server.app": fake_module},
        ), patch(
            "sonarqube_quality_assistant.main.load_env"
        ) as mock_load_env, patch(
            "sonarqube_quality_assistant.main.get_logger"
        ) as mock_get_logger, patch(
            "sys.stderr"
        ):
            module = importlib.import_module("sonarqube_quality_assistant.main")
            logger = Mock()
            mock_get_logger.return_value = logger

            module.main()

            mock_load_env.assert_called_once_with()
            logger.info.assert_called_once_with("Starting sonarqube-quality-assistant")
            fake_mcp.run.assert_called_once_with(transport="stdio")

        fake_mcp = Mock()
        fake_mcp.run.side_effect = RuntimeError("boom")
        fake_module = types.ModuleType("sonarqube_quality_assistant.server.app")
        fake_module.mcp = fake_mcp
        sys.modules.pop("sonarqube_quality_assistant.main", None)

        with patch.dict(
            sys.modules,
            {"sonarqube_quality_assistant.server.app": fake_module},
        ), patch(
            "sonarqube_quality_assistant.main.load_env"
        ), patch(
            "sonarqube_quality_assistant.main.get_logger",
            return_value=Mock(),
        ), patch(
            "sys.stderr"
        ):
            module = importlib.import_module("sonarqube_quality_assistant.main")
            with self.assertRaisesRegex(RuntimeError, "boom"):
                module.main()