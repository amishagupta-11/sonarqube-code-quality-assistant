from sonarqube_quality_assistant.sonarqube.client import SonarQubeClient
from sonarqube_quality_assistant.sonarqube.endpoints import SONAR_ENDPOINTS
from sonarqube_quality_assistant.sonarqube.mappers import map_issue_response

class IssueService:
    def __init__(self) -> None:
        self.client = SonarQubeClient()

    async def find_critical_issues(
    self,
        project_key,
        severity=None,
        issue_type=None,
        assigned_to=None
    ):
        """
            Find critical issues for a given project with optional filters for severity, type, and assignee.
            Args:
                project_key: The key of the SonarQube project to search for issues.
                severity: Optional filter for issue severity (e.g., BLOCKER, CRITICAL).
                issue_type: Optional filter for issue type (e.g., BUG, VULNERABILITY, CODE_SMELL).
                assigned_to: Optional filter for assignee username to find issues assigned to a specific user.
            Returns:
                A formatted string listing the critical issues that match the provided filters, including their severity, type"""
        
        params = {
            "projects": project_key,
            "statuses": "OPEN,CONFIRMED,REOPENED"
        }

        if severity:
            params["severities"] = severity

        if issue_type:
            params["types"] = issue_type

        if assigned_to:
            params["assignees"] = assigned_to
        
        response = await self.client.get(
            SONAR_ENDPOINTS["issues"],
            params
        )
        mapped = map_issue_response(response)
        issues = mapped["issues"]

        if not issues:
            return "\n".join(
                [
                    f"Critical Issues for {project_key}",
                    f"Severity filter: {severity}",
                    f"Type filter: {issue_type or 'all'}",
                    f"Assigned to: {assigned_to or 'anyone'}",
                    "",
                    "No matching issues found.",
                ]
            )

        lines = [
            f"Critical Issues for {project_key}",
            f"Severity filter: {severity}",
            f"Type filter: {issue_type or 'all'}",
            f"Assigned to: {assigned_to or 'anyone'}",
            f"Matches: {mapped['total']}",
            "",
        ]

        for issue in issues[:10]:
            lines.extend(
                [
                    f"- [{issue['severity']}] {issue['type']} in {issue['component']}"
                    + (f":{issue['line']}" if issue.get("line") else ""),
                    f"  Message: {issue['message']}",
                    f"  Remediation effort: {issue.get('effort') or 'Not provided by SonarQube'}",
                    f"  Assignee: {issue.get('assignee') or 'Unassigned'}",
                ]
            )

        if mapped["total"] > 10:
            lines.append(f"...and {mapped['total'] - 10} more issues.")

        return "\n".join(lines)

    async def get_latest_blocker_issue(self, project_key: str) -> dict | None:
        """
        Retrieve the most recently created BLOCKER issue for a given project.
        Args:
            project_key: The key of the SonarQube project to search for BLOCKER issues.
        Returns:
            A dictionary containing details of the most recent BLOCKER issue, or None if no such issues are found.
        """
        response = await self.client.get(
            SONAR_ENDPOINTS["issues"],
            {
                "projects": project_key,
                "severities": "BLOCKER",
                "statuses": "OPEN,CONFIRMED,REOPENED",
                "ps": 1,
                "s": "CREATION_DATE",
                "asc": "false",
            },
        )

        issues = response.get("issues", [])
        if not issues:
            return None

        return issues[0]

    async def assign_issue(self, issue_key: str, assignee: str | None) -> dict:
        """
        Assign a SonarQube issue to a specified user or unassign it if no assignee is provided.
        Args:
            issue_key: The unique key of the SonarQube issue to be assigned.
            assignee: The username of the assignee to assign the issue to, or None to unassign.
        Returns:
            A dictionary indicating the success of the operation and the updated issue details.
        """
        await self.client.post(
            SONAR_ENDPOINTS["issues_assign"],
            {
                "issue": issue_key,
                "assignee": assignee or "",
            },
        )

        response = await self.client.get(
            SONAR_ENDPOINTS["issues"],
            {
                "issues": issue_key,
            },
        )
        mapped = map_issue_response(response)
        issues = mapped.get("issues", [])

        return {
            "success": True,
            "issue": issues[0] if issues else {"key": issue_key, "assignee": assignee},
        }
