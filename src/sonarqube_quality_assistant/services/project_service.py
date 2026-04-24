import asyncio
from sonarqube_quality_assistant.sonarqube.client import SonarQubeClient
from sonarqube_quality_assistant.sonarqube.endpoints import SONAR_ENDPOINTS
from sonarqube_quality_assistant.sonarqube.mappers import (
    map_branch_list_response,
    map_hotspot_response,
    map_issue_response,
    map_overview_response,
    map_project_list_response,
)

class ProjectService:
    def __init__(self) -> None:
        self.client = SonarQubeClient()

    async def list_projects(self) -> dict:
        """Fetch a list of SonarQube projects along with their quality gate status.
        Returns:
            A dictionary containing a list of projects, each with its key, name, and current quality gate status.
        """

        raw_response = await self.client.get(SONAR_ENDPOINTS["projects"])
        mapped_response = map_project_list_response(raw_response)

        async def fetch_quality_gate(project_key: str) -> str | None:
            try:
                response = await self.get_quality_gate_status(project_key)
                return response.get("projectStatus", {}).get("status")
            except Exception:
                return None

        statuses = await asyncio.gather(
            *(fetch_quality_gate(project["key"]) for project in mapped_response["projects"]),
            return_exceptions=False,
        )

        for project, status in zip(mapped_response["projects"], statuses):
            project["quality_gate_status"] = status

        return mapped_response

    async def get_project_overview(self, project_key: str) -> dict:
        """
        Fetch an overview of a SonarQube project including key quality metrics and quality gate status.
        Args:
            project_key: The key of the SonarQube project to retrieve the overview for.
        Returns:
            A dictionary containing the project's key, name, quality gate status, and key metrics such as bugs, vulnerabilities, code smells, coverage, and duplication density.
        """
        measures_response, quality_gate_response = await asyncio.gather(
            self.client.get(
                SONAR_ENDPOINTS["measures"],
                {
                    "component": project_key,
                    "metricKeys": "bugs,vulnerabilities,code_smells,coverage,duplicated_lines_density",
                },
            ),
            self.get_quality_gate_status(project_key),
        )

        return map_overview_response(measures_response, quality_gate_response)

    async def get_quality_gate_status(self, project_key: str, branch: str | None = None) -> dict:
        """Fetch the quality gate status for a given project and optional branch.
        Args:
            project_key: The key of the SonarQube project to check the quality gate status for.
            branch: Optional branch name to check the quality gate status for. If not provided, the main branch status will be returned.
        Returns:
            A dictionary containing the quality gate status and related information for the specified project and branch.
        """
        return await self.client.get(
            SONAR_ENDPOINTS["quality_gates"],
            {
                "projectKey": project_key,
                "branch": branch,
            },
        )

    async def list_project_branches(self, project_key: str) -> dict:
        """Fetch a list of branches for a given SonarQube project.
        Args:
            project_key: The key of the SonarQube project to list branches for.
        Returns:
            A dictionary containing the project key and a list of branches, each with its name and status   
            (e.g., LONG, SHORT, or PULL_REQUEST).
        """
        response = await self.client.get(
            SONAR_ENDPOINTS["project_branches"],
            {
                "project": project_key,
            },
        )
        mapped = map_branch_list_response(response)
        mapped["project_key"] = project_key
        return mapped

    async def get_branch_overview(self, project_key: str, branch: str) -> dict:
        """Fetch an overview of a specific branch within a SonarQube project, including key quality metrics and quality gate status.
        Args:
            project_key: The key of the SonarQube project to retrieve the branch overview for.
            branch: The name of the branch to retrieve the overview for.
        Returns:
            A dictionary containing the project's key, branch name, quality gate status, and key metrics such as bugs, vulnerabilities, code smells, coverage, and duplication density for the specified branch.
        """
        measures_response, quality_gate_response = await asyncio.gather(
            self.client.get(
                SONAR_ENDPOINTS["measures"],
                {
                    "component": project_key,
                    "branch": branch,
                    "metricKeys": "bugs,vulnerabilities,code_smells,coverage,duplicated_lines_density",
                },
            ),
            self.get_quality_gate_status(project_key, branch),
        )

        mapped = map_overview_response(measures_response, quality_gate_response)
        mapped["branch"] = branch
        return mapped

    async def get_project_issues(self, project_key: str) -> dict:
        """Fetch a list of issues for a given SonarQube project.
        Args:
            project_key: The key of the SonarQube project to retrieve issues for.
        Returns:
            A dictionary containing the project key and a list of issues.
        """
        response = await self.client.get(
            SONAR_ENDPOINTS["issues"],
            {
                "projects": project_key,
                "statuses": "OPEN,CONFIRMED,REOPENED",
            },
        )
        mapped = map_issue_response(response)
        mapped["project_key"] = project_key
        return mapped

    async def get_branch_issues(self, project_key: str, branch: str) -> dict:
        """Fetch a list of issues for a specific branch within a SonarQube project.
        Args:
            project_key: The key of the SonarQube project to retrieve issues for.
            branch: The name of the branch to retrieve issues for.
        Returns:
            A dictionary containing the project key, branch name, and a list of issues.
        """
        response = await self.client.get(
            SONAR_ENDPOINTS["issues"],
            {
                "projects": project_key,
                "branch": branch,
                "statuses": "OPEN,CONFIRMED,REOPENED",
            },
        )
        mapped = map_issue_response(response)
        mapped["project_key"] = project_key
        mapped["branch"] = branch
        return mapped

    async def get_project_hotspots(self, project_key: str) -> dict:
        """Fetch a list of security hotspots for a given SonarQube project.
        Args:
            project_key: The key of the SonarQube project to retrieve hotspots for.
        Returns:
            A dictionary containing the project key and a list of security hotspots.
        """
        response = await self.client.get(
            SONAR_ENDPOINTS["hotspots"],
            {
                "projectKey": project_key,
            },
        )
        mapped = map_hotspot_response(response)
        mapped["project_key"] = project_key
        return mapped
