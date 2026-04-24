from mcp.server.fastmcp import FastMCP
from sonarqube_quality_assistant.server.notification_runtime import notification_runtime
from sonarqube_quality_assistant.services.project_service import ProjectService

def register_resources(mcp: FastMCP) -> None:
    project_service = ProjectService()

    @mcp.resource("sonar://projects")
    async def sonar_projects() -> dict:
        """List SonarQube projects visible to the server."""
        return await project_service.list_projects()

    @mcp.resource("sonar://project/{project_key}/overview")
    async def sonar_project_overview(project_key: str) -> dict:
        """Return dashboard metrics for a SonarQube project."""
        return await project_service.get_project_overview(project_key)

    @mcp.resource("sonar://project/{project_key}/branches")
    async def sonar_project_branches(project_key: str) -> dict:
        """Return branches known to SonarQube for a project."""
        return await project_service.list_project_branches(project_key)

    @mcp.resource("sonar://project/{project_key}/branch/{branch}/overview")
    async def sonar_project_branch_overview(project_key: str, branch: str) -> dict:
        """Return dashboard metrics for a specific SonarQube branch."""
        return await project_service.get_branch_overview(project_key, branch)

    @mcp.resource("sonar://project/{project_key}/issues")
    async def sonar_project_issues(project_key: str) -> dict:
        """Return open issues for a SonarQube project."""
        return await project_service.get_project_issues(project_key)

    @mcp.resource("sonar://project/{project_key}/branch/{branch}/issues")
    async def sonar_project_branch_issues(project_key: str, branch: str) -> dict:
        """Return open issues for a specific SonarQube branch."""
        return await project_service.get_branch_issues(project_key, branch)

    @mcp.resource("sonar://project/{project_key}/hotspots")
    async def sonar_project_hotspots(project_key: str) -> dict:
        """Return security hotspots for a SonarQube project."""
        return await project_service.get_project_hotspots(project_key)

    @mcp.resource("sonar://notifications")
    async def sonar_notifications() -> dict:
        """Return the latest detected notification events from the background watcher."""
        return await notification_runtime.list_notifications()
