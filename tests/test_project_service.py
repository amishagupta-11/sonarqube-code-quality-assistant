import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

SRC_PATH = Path(__file__).resolve().parents[1] / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from sonarqube_quality_assistant.services.project_service import ProjectService

class ProjectServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        client_patcher = patch(
            "sonarqube_quality_assistant.services.project_service.SonarQubeClient"
        )
        self.addCleanup(client_patcher.stop)
        self.mock_client_class = client_patcher.start()
        self.mock_client = AsyncMock()
        self.mock_client_class.return_value = self.mock_client
        self.service = ProjectService()

    async def test_list_projects_enriches_each_project_with_quality_gate_status(self):
        self.mock_client.get.return_value = {
            "components": [
                {"key": "app-1", "name": "App 1"},
                {"key": "app-2", "name": "App 2"},
            ]
        }
        self.service.get_quality_gate_status = AsyncMock(
            side_effect=[
                {"projectStatus": {"status": "OK"}},
                {"projectStatus": {"status": "ERROR"}},
            ]
        )

        result = await self.service.list_projects()

        self.assertEqual(
            result["projects"],
            [
                {
                    "key": "app-1",
                    "name": "App 1",
                    "last_analysis_date": None,
                    "visibility": None,
                    "quality_gate_status": "OK",
                },
                {
                    "key": "app-2",
                    "name": "App 2",
                    "last_analysis_date": None,
                    "visibility": None,
                    "quality_gate_status": "ERROR",
                },
            ],
        )

    async def test_list_projects_sets_missing_quality_gate_to_none_when_lookup_fails(self):
        self.mock_client.get.return_value = {"components": [{"key": "app-1", "name": "App 1"}]}
        self.service.get_quality_gate_status = AsyncMock(side_effect=RuntimeError("unavailable"))

        result = await self.service.list_projects()

        self.assertIsNone(result["projects"][0]["quality_gate_status"])

    async def test_get_project_overview_requests_measures_and_quality_gate(self):
        self.mock_client.get.return_value = {
            "component": {
                "key": "app",
                "name": "App",
                "measures": [
                    {"metric": "bugs", "value": "1"},
                    {"metric": "coverage", "value": "91.4"},
                    {"metric": "duplicated_lines_density", "value": "0.8"},
                ],
            }
        }
        self.service.get_quality_gate_status = AsyncMock(
            return_value={"projectStatus": {"status": "OK"}, "analysedAt": "2026-04-20"}
        )

        result = await self.service.get_project_overview("app")

        self.mock_client.get.assert_awaited_once_with(
            "/api/measures/component",
            {
                "component": "app",
                "metricKeys": "bugs,vulnerabilities,code_smells,coverage,duplicated_lines_density",
            },
        )
        self.assertEqual(result["quality_gate_status"], "OK")
        self.assertEqual(result["metrics"]["coverage"], 91.4)

    async def test_list_project_branches_adds_project_key(self):
        self.mock_client.get.return_value = {"branches": [{"name": "main", "isMain": True}]}

        result = await self.service.list_project_branches("app")

        self.assertEqual(result["project_key"], "app")
        self.assertEqual(result["branches"][0]["name"], "main")

    async def test_get_branch_overview_includes_branch_name(self):
        self.mock_client.get.return_value = {
            "component": {
                "key": "app",
                "name": "App",
                "measures": [{"metric": "coverage", "value": "77.0"}],
            }
        }
        self.service.get_quality_gate_status = AsyncMock(
            return_value={"projectStatus": {"status": "WARN"}, "analysedAt": "2026-04-20"}
        )

        result = await self.service.get_branch_overview("app", "feature/login")

        self.assertEqual(result["branch"], "feature/login")
        self.assertEqual(result["quality_gate_status"], "WARN")

    async def test_issue_and_hotspot_queries_tag_project_and_branch(self):
        self.mock_client.get.side_effect = [
            {"issues": [{"key": "ISSUE-1"}]},
            {"issues": [{"key": "ISSUE-2"}]},
            {"hotspots": [{"key": "HOT-1"}]},
        ]

        project_issues = await self.service.get_project_issues("app")
        branch_issues = await self.service.get_branch_issues("app", "dev")
        hotspots = await self.service.get_project_hotspots("app")

        self.assertEqual(project_issues["project_key"], "app")
        self.assertEqual(branch_issues["project_key"], "app")
        self.assertEqual(branch_issues["branch"], "dev")
        self.assertEqual(hotspots["project_key"], "app")
