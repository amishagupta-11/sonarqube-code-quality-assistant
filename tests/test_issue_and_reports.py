import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

SRC_PATH = Path(__file__).resolve().parents[1] / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from sonarqube_quality_assistant.services.comparison_service import ComparisonService
from sonarqube_quality_assistant.services.issue_service import IssueService
from sonarqube_quality_assistant.services.quality_report_service import QualityReportService

class IssueServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        client_patcher = patch(
            "sonarqube_quality_assistant.services.issue_service.SonarQubeClient"
        )
        self.addCleanup(client_patcher.stop)
        self.mock_client_class = client_patcher.start()
        self.mock_client = AsyncMock()
        self.mock_client_class.return_value = self.mock_client
        self.service = IssueService()

    async def test_find_critical_issues_formats_empty_result(self):
        self.mock_client.get.return_value = {"issues": [], "total": 0}

        result = await self.service.find_critical_issues("app", severity="CRITICAL")

        self.assertIn("No matching issues found.", result)
        self.assertIn("Severity filter: CRITICAL", result)
        self.assertIn("Type filter: all", result)

    async def test_find_critical_issues_formats_issue_list_and_remaining_count(self):
        issues = [
            {
                "key": f"ISSUE-{index}",
                "severity": "CRITICAL",
                "type": "BUG",
                "component": "app:src/main.py",
                "line": index,
                "message": f"Problem {index}",
                "assignee": None if index % 2 else "alice",
                "effort": None if index % 2 else "15min",
            }
            for index in range(1, 12)
        ]
        self.mock_client.get.return_value = {"issues": issues, "total": 11}

        result = await self.service.find_critical_issues(
            "app", severity="CRITICAL", issue_type="BUG", assigned_to="alice"
        )

        self.assertIn("Matches: 11", result)
        self.assertIn("- [CRITICAL] BUG in app:src/main.py:1", result)
        self.assertIn("Remediation effort: Not provided by SonarQube", result)
        self.assertIn("Assignee: Unassigned", result)
        self.assertIn("...and 1 more issues.", result)
        self.assertEqual(
            self.mock_client.get.await_args.args[1],
            {
                "projects": "app",
                "statuses": "OPEN,CONFIRMED,REOPENED",
                "severities": "CRITICAL",
                "types": "BUG",
                "assignees": "alice",
            },
        )

    async def test_get_latest_blocker_issue_returns_none_when_absent(self):
        self.mock_client.get.return_value = {"issues": []}

        result = await self.service.get_latest_blocker_issue("app")

        self.assertIsNone(result)

    async def test_assign_issue_posts_then_fetches_updated_issue(self):
        self.mock_client.post.return_value = {"success": True}
        self.mock_client.get.return_value = {
            "issues": [{"key": "ISSUE-1", "assignee": "alice", "severity": "MAJOR"}]
        }

        result = await self.service.assign_issue("ISSUE-1", "alice")

        self.mock_client.post.assert_awaited_once_with(
            "/api/issues/assign",
            {"issue": "ISSUE-1", "assignee": "alice"},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["issue"]["assignee"], "alice")


class ReportServicesTests(unittest.IsolatedAsyncioTestCase):
    async def test_quality_report_counts_issue_categories_and_fallbacks(self):
        with patch(
            "sonarqube_quality_assistant.services.quality_report_service.ProjectService"
        ) as mock_project_service_class:
            mock_project_service = AsyncMock()
            mock_project_service_class.return_value = mock_project_service
            mock_project_service.get_project_overview.return_value = {
                "quality_gate_status": None,
                "metrics": {
                    "bugs": 2,
                    "vulnerabilities": 1,
                    "code_smells": 5,
                    "coverage": 88.8,
                    "duplications": 2.1,
                },
            }
            mock_project_service.get_project_issues.return_value = {
                "total": 3,
                "issues": [
                    {"severity": "BLOCKER", "type": "BUG"},
                    {"severity": "CRITICAL", "type": "VULNERABILITY"},
                    {"severity": "MAJOR", "type": "CODE_SMELL"},
                ],
            }

            service = QualityReportService()
            result = await service.get_quality_report("app", "last-7-days")

        self.assertIn("Quality gate: Unavailable", result)
        self.assertIn("Open BLOCKER issues: 1", result)
        self.assertIn("Open CRITICAL issues: 1", result)
        self.assertIn("Open vulnerability issues: 1", result)
        self.assertIn("period label 'last-7-days'", result)

    async def test_comparison_service_formats_both_project_summaries(self):
        with patch(
            "sonarqube_quality_assistant.services.comparison_service.ProjectService"
        ) as mock_project_service_class:
            mock_project_service = AsyncMock()
            mock_project_service_class.return_value = mock_project_service
            mock_project_service.get_project_overview.side_effect = [
                {
                    "quality_gate_status": "OK",
                    "metrics": {
                        "bugs": 1,
                        "vulnerabilities": 0,
                        "code_smells": 3,
                        "coverage": 92.4,
                        "duplications": 0.5,
                    },
                },
                {
                    "quality_gate_status": "ERROR",
                    "metrics": {
                        "bugs": 4,
                        "vulnerabilities": 2,
                        "code_smells": 11,
                        "coverage": 61.0,
                        "duplications": 4.3,
                    },
                },
            ]

            service = ComparisonService()
            result = await service.compare_projects("app-a", "app-b")

        self.assertIn("Quality Comparison", result)
        self.assertIn("app-a quality gate: OK", result)
        self.assertIn("app-b quality gate: ERROR", result)
        self.assertIn("app-a coverage: 92.4%", result)
        self.assertIn("app-b duplications: 4.3%", result)
