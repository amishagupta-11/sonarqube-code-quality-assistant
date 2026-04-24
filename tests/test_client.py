import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

SRC_PATH = Path(__file__).resolve().parents[1] / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from sonarqube_quality_assistant.sonarqube.client import SonarQubeClient
from sonarqube_quality_assistant.utils.errors import AppError

class FakeResponse:
    def __init__(self, status_code=200, json_data=None, text="ok"):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}
        self.text = text

    def json(self):
        return self._json_data

class SonarQubeClientTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        env_patcher = patch(
            "sonarqube_quality_assistant.sonarqube.client.get_required_env",
            side_effect=["https://sonarqube.example", "token-123"],
        )
        self.addCleanup(env_patcher.stop)
        env_patcher.start()
        self.client = SonarQubeClient()

    @patch("sonarqube_quality_assistant.sonarqube.client.httpx.AsyncClient")
    async def test_get_filters_none_params_and_returns_json(self, mock_async_client):
        response = FakeResponse(json_data={"ok": True})
        context_client = AsyncMock()
        context_client.get.return_value = response
        mock_async_client.return_value.__aenter__.return_value = context_client

        result = await self.client.get("/api/projects/search", {"project": "app", "branch": None})

        self.assertEqual(result, {"ok": True})
        mock_async_client.assert_called_once_with(
            base_url="https://sonarqube.example",
            headers={"Authorization": "Bearer token-123"},
        )
        context_client.get.assert_awaited_once_with(
            "/api/projects/search",
            params={"project": "app"},
        )

    @patch("sonarqube_quality_assistant.sonarqube.client.httpx.AsyncClient")
    async def test_get_raises_app_error_on_http_failure(self, mock_async_client):
        response = FakeResponse(status_code=500, text="boom")
        context_client = AsyncMock()
        context_client.get.return_value = response
        mock_async_client.return_value.__aenter__.return_value = context_client

        with self.assertRaisesRegex(AppError, "SonarQube API request failed: 500 boom"):
            await self.client.get("/api/projects/search")

    @patch("sonarqube_quality_assistant.sonarqube.client.httpx.AsyncClient")
    async def test_post_filters_none_values_and_handles_empty_body(self, mock_async_client):
        response = FakeResponse(text="")
        context_client = AsyncMock()
        context_client.post.return_value = response
        mock_async_client.return_value.__aenter__.return_value = context_client

        result = await self.client.post("/api/issues/assign", {"issue": "ISSUE-1", "assignee": None})

        self.assertEqual(result, {"success": True})
        context_client.post.assert_awaited_once_with(
            "/api/issues/assign",
            data={"issue": "ISSUE-1"},
        )

    @patch("sonarqube_quality_assistant.sonarqube.client.httpx.AsyncClient")
    async def test_post_returns_json_payload_when_present(self, mock_async_client):
        response = FakeResponse(text='{"success":true}', json_data={"success": True})
        context_client = AsyncMock()
        context_client.post.return_value = response
        mock_async_client.return_value.__aenter__.return_value = context_client

        result = await self.client.post("/api/issues/assign", {"issue": "ISSUE-1"})

        self.assertEqual(result, {"success": True})
