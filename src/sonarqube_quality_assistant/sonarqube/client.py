from typing import Any
import httpx
from sonarqube_quality_assistant.utils.env import get_required_env
from sonarqube_quality_assistant.utils.errors import AppError

class SonarQubeClient:
    def __init__(self) -> None:
        self.base_url = get_required_env("SONARQUBE_BASE_URL")
        self.token = get_required_env("SONARQUBE_TOKEN")

    async def get(
        self, path: str, params: dict[str, str | int | None] | None = None
    ) -> Any:
        """
        Make an authenticated GET request to the SonarQube API with optional query parameters.
        Args:
            path: The API endpoint path.
            params: Optional query parameters.
        Returns:
            The JSON response from the API.
        Raises:
            AppError: If the API request fails with a status code of 400 or higher."""
        filtered_params = {k: v for k, v in (params or {}).items() if v is not None}

        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.token}"},
        ) as client:
            response = await client.get(path, params=filtered_params)

        if response.status_code >= 400:
            raise AppError(
                f"SonarQube API request failed: {response.status_code} {response.text}"
            )

        return response.json()

    async def post(
        self, path: str, data: dict[str, str | int | None] | None = None
    ) -> Any:
        """Make an authenticated POST request to the SonarQube API with optional form data.
        Args:
            path: The API endpoint path.
            data: Optional form data to include in the POST request.
        Returns:
            The JSON response from the API, or a success message if the response body is empty.
        Raises:
            AppError: If the API request fails with a status code of 400 or higher."""
        
        filtered_data = {k: v for k, v in (data or {}).items() if v is not None}

        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.token}"},
        ) as client:
            response = await client.post(path, data=filtered_data)

        if response.status_code >= 400:
            raise AppError(
                f"SonarQube API request failed: {response.status_code} {response.text}"
            )

        if not response.text:
            return {"success": True}

        return response.json()
