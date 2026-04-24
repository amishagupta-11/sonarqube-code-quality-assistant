from typing import Literal
from mcp.server.fastmcp import Context, FastMCP
from groq import Groq
from sonarqube_quality_assistant.server.notifications import (
    build_new_blocker_issue_notification,
    build_quality_gate_changed_notification,
    get_notification_catalog,
)
from sonarqube_quality_assistant.server.notification_runtime import notification_runtime
from sonarqube_quality_assistant.server.sampling import (
    build_issue_sampling_payload,
    build_sampling_flow_description,
)
from sonarqube_quality_assistant.services.comparison_service import ComparisonService
from sonarqube_quality_assistant.services.issue_service import IssueService
from sonarqube_quality_assistant.services.project_service import ProjectService
from sonarqube_quality_assistant.services.quality_report_service import QualityReportService

def _count_issues_by_severity(issues: list[dict], severity: str) -> int:
    """
    Count issues matching a given severity.
    Args:
    - issues: A list of issue dictionaries, each containing a 'severity' key.
    - severity: The severity level to count (e.g., "BLOCKER", "CRITICAL").
    Returns:
    The count of issues that have the specified severity.
    """
    return sum(1 for issue in issues if issue["severity"] == severity)

def _build_readiness_reasons(
    quality_gate: str | None,
    blocker_count: int,
    critical_count: int,
    coverage: float,
) -> list[str]:
    """
    Return a list of reasons why a branch is not PR-ready.
    Args:
    - quality_gate: The current quality gate status (e.g., "OK", "ERROR").
    - blocker_count: The number of open BLOCKER issues.
    - critical_count: The number of open CRITICAL issues.
    - coverage: The current code coverage percentage.
    Returns: 
        A list of strings describing the reasons the branch is not ready for PR review.
        If the list is empty, the branch is considered PR-ready based on SonarQube metrics.
    """
    reasons: list[str] = []
    if quality_gate not in ("OK", "PASSED"):
        reasons.append(f"Quality gate is {quality_gate or 'UNAVAILABLE'}.")
    if blocker_count > 0:
        reasons.append(f"{blocker_count} BLOCKER issue(s) are still open.")
    if critical_count > 0:
        reasons.append(f"{critical_count} CRITICAL issue(s) are still open.")
    if coverage < 80:
        reasons.append(f"Coverage is {coverage}%, which is below the 80% target.")
    return reasons

def _build_readiness_report(
    project_key: str,
    branch: str,
    verdict: str,
    quality_gate: str | None,
    coverage: float,
    total_issues: int,
    blocker_count: int,
    critical_count: int,
    reasons: list[str],
) -> str:
    """
    Format the PR readiness report as a string.
    Args:    
    - project_key: The key of the SonarQube project.
    - branch: The branch name.
    - verdict: The PR readiness verdict.
    - quality_gate: The quality gate status.
    - coverage: The code coverage percentage.
    - total_issues: The total number of open issues.
    - blocker_count: The number of open BLOCKER issues.
    - critical_count: The number of open CRITICAL issues.
    - reasons: A list of strings describing the reasons the branch is not ready for PR review.
    Returns:
    A formatted string representing the PR readiness report.
    """
    lines = [
        f"PR Readiness for {project_key} / {branch}",
        f"Verdict: {verdict}",
        f"Quality gate: {quality_gate}",
        f"Coverage: {coverage}%",
        f"Open issues: {total_issues}",
        f"Open BLOCKER issues: {blocker_count}",
        f"Open CRITICAL issues: {critical_count}",
        "",
        "Reasons:",
    ]
    if reasons:
        lines.extend(f"- {reason}" for reason in reasons)
    else:
        lines.append("- No blocker conditions detected in the latest SonarQube branch snapshot.")
    return "\n".join(lines)

def _build_groq_messages(sampling_payload: dict) -> list[dict]:
    """
    Build the messages list for the Groq LLM API call.
    Args:  
        - sampling_payload: The structured payload containing issues and instructions for grouping.
    Returns:
        A list of message dictionaries formatted for the Groq API.
    """
    return [
        {
            "role": "system",
            "content": (
                "You are a SonarQube quality analyst. Group issues by engineering root cause, "
                "not by file name. Prefer actionable batch fixes."
            ),
        },
        {
            "role": "user",
            "content": "\n".join([
                f"Project key: {sampling_payload['project_key']}",
                sampling_payload["instruction"],
                "",
                "Issues to analyze:",
                str(sampling_payload["issues"]),
                "",
                "Return JSON with these keys:",
                "- root_cause_groups: array of grouped patterns",
                "- high_risk_items: array of the most urgent issues",
                "- batch_fix_plan: array of recommended bulk-remediation actions",
            ]),
        },
    ]

def _get_analyzed_at(project_status: dict, quality_gate: dict) -> str | None:
    """
    Extract the analysis timestamp from a quality gate response.
    Args:   
        - project_status: The 'projectStatus' section of the quality gate response, which may contain a 'period' with a 'date' field.
        - quality_gate: The full quality gate response, which may contain an 'analysedAt' field at the top level.
    Returns:
        The timestamp of when the analysis was performed, preferring the most specific 'period.date'
        if available, and falling back to 'analysedAt' if not. If neither is available, returns "UNAVAILABLE".
    """
    return (
        project_status.get("period", {}).get("date")
        or project_status.get("analysedAt")
        or quality_gate.get("analysedAt")
    )

async def _handle_quality_gate_notification(
    project_key: str,
    previous_status: str | None,
    project_service: ProjectService,
) -> dict:
    """
    Build and emit a quality gate changed notification.
    Args:
    - project_key: The key of the SonarQube project.
    - previous_status: The previous quality gate status before the change. This is required to provide context in the notification.
    - project_service: An instance of ProjectService to fetch the latest quality gate status and analysis timestamp.
    Returns:
    A dictionary representing the emitted notification payload.
    Note: The current_status and analyzed_at fields in the notification will be set to "UNAVAILABLE" if
    the necessary data cannot be retrieved from SonarQube, but the notification will still be emitted.
   """
    if previous_status is None:
        raise ValueError("previous_status is required for sonarqube.quality_gate.changed")

    quality_gate = await project_service.get_quality_gate_status(project_key)
    project_status = quality_gate.get("projectStatus", {})
    current_status = project_status.get("status")
    analyzed_at = _get_analyzed_at(project_status, quality_gate)

    payload = build_quality_gate_changed_notification(
        project_key=project_key,
        previous_status=previous_status,
        current_status=current_status,
        analyzed_at=analyzed_at,
    )
    await notification_runtime._emit_notification(payload)
    return {"notification": payload}

async def _handle_blocker_issue_notification(
    project_key: str,
    issue_service: IssueService,
) -> dict:
    """
    Build and emit a new blocker issue notification.
    Args:    
        - project_key: The key of the SonarQube project.
        - issue_service: An instance of IssueService to fetch the latest BLOCKER issue details.
    Returns:
        A dictionary representing the emitted notification payload.
    Note: If no open BLOCKER issues are found, a ValueError is raised and no notification is emitted. 
    If issue details cannot be retrieved, the notification will still be emitted with "UNAVAILABLE" placeholders for missing data.
    """
    latest_issue = await issue_service.get_latest_blocker_issue(project_key)
    if latest_issue is None:
        raise ValueError(f"No open BLOCKER issues found for project {project_key}")

    payload = build_new_blocker_issue_notification(
        project_key=project_key,
        issue_key=latest_issue.get("key"),
        component=latest_issue.get("component"),
        message=latest_issue.get("message"),
        introduced_at=latest_issue.get("creationDate"),
    )
    await notification_runtime._emit_notification(payload)
    return {"notification": payload}

def register_tools(mcp: FastMCP) -> None:
    quality_report_service = QualityReportService()
    issue_service = IssueService()
    comparison_service = ComparisonService()
    project_service = ProjectService()

    @mcp.tool()
    async def list_projects() -> dict:
        """List SonarQube projects visible to the current token."""
        return await project_service.list_projects()

    @mcp.tool()
    async def get_quality_report(
        project_key: str,
        period: Literal["last_7d", "last_30d", "since_last_release"] = "last_7d",
    ) -> str:
        """Generate a formatted quality summary with trends for a project."""
        return await quality_report_service.get_quality_report(project_key, period)

    @mcp.tool()
    async def find_critical_issues(
        project_key: str,
        severity: Literal["BLOCKER", "CRITICAL", "MAJOR", "MINOR", "INFO"],
        issue_type: Literal["BUG", "VULNERABILITY", "CODE_SMELL"] | None = None,
        assigned_to: str | None = None,
    ) -> str:
        """Find critical or blocker issues with optional filters."""
        return await issue_service.find_critical_issues(
            project_key=project_key,
            severity=severity,
            issue_type=issue_type,
            assigned_to=assigned_to,
        )

    @mcp.tool()
    async def compare_quality(project_key_1: str, project_key_2: str) -> str:
        """
        Compare quality metrics for two projects side by side.
        Args:
        - project_key_1: The key of the first SonarQube project.
        - project_key_2: The key of the second SonarQube project.
        Returns:
        A formatted string comparing key quality metrics and issue counts between the two projects, highlighting strengths and weaknesses.
        """
        return await comparison_service.compare_projects(project_key_1, project_key_2)

    @mcp.tool()
    async def list_project_branches(project_key: str) -> dict:
        """
        List SonarQube branches available for a project.
        Args:
        - project_key: The key of the SonarQube project.
        Returns:
        A dictionary containing a list of branch names and their metadata for the specified project.
        """
        return await project_service.list_project_branches(project_key)

    @mcp.tool()
    async def check_pr_readiness(project_key: str, branch: str) -> str:
        """
        Check whether a SonarQube branch looks ready for PR based on current branch metrics and issues.
        Args:
        - project_key: The key of the SonarQube project.
        - branch: The name of the branch to check.
        Returns:
        A string indicating the readiness status of the branch for a pull request.
        """
        overview = await project_service.get_branch_overview(project_key, branch)
        issues = await project_service.get_branch_issues(project_key, branch)

        metrics = overview["metrics"]
        quality_gate = overview.get("quality_gate_status")
        coverage = float(metrics.get("coverage") or 0)
        total_issues = issues["total"]
        blocker_count = _count_issues_by_severity(issues["issues"], "BLOCKER")
        critical_count = _count_issues_by_severity(issues["issues"], "CRITICAL")

        reasons = _build_readiness_reasons(quality_gate, blocker_count, critical_count, coverage)
        verdict = "PR Ready" if not reasons else "Not Ready"

        return _build_readiness_report(
            project_key, branch, verdict, quality_gate,
            coverage, total_issues, blocker_count, critical_count, reasons,
        )

    @mcp.tool()
    async def prepare_issue_sampling(project_key: str) -> dict:
        """
        Prepare a sampling payload that groups 30+ SonarQube issues by root-cause pattern.
        Args:
        - project_key: The key of the SonarQube project.
        Returns:
        A dictionary containing the sampling payload and flow description.
        """
        issues_response = await project_service.get_project_issues(project_key)
        return {
            "sampling_payload": build_issue_sampling_payload(project_key, issues_response),
            "sampling_flow": build_sampling_flow_description(),
        }

    @mcp.tool()
    async def group_issue_patterns_with_sampling(project_key: str, ctx: Context) -> dict:
        """
        Group SonarQube issues by root-cause pattern using LLM analysis.
        Args:
        - project_key: The key of the SonarQube project.
        - ctx: The context for the LLM analysis.
        Returns:
        A dictionary containing the grouped issue patterns and analysis results.
        """
        issues_response = await project_service.get_project_issues(project_key)
        sampling_payload = build_issue_sampling_payload(project_key, issues_response)

        client = Groq()  # reads GROQ_API_KEY from env automatically
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=2048,
            messages=_build_groq_messages(sampling_payload),
        )

        return {
            "sampling_flow": build_sampling_flow_description(),
            "sampling_payload": sampling_payload,
            "llm_result": {
                "model": response.model,
                "stop_reason": response.choices[0].finish_reason,
                "content": {
                    "type": "text",
                    "text": response.choices[0].message.content,
                },
            },
        }

    @mcp.tool()
    async def list_notification_types() -> dict:
        """
        List the SonarQube notification events this MCP server is designed to support.
        Returns:
        A dictionary containing the list of supported notification types.
        """
        return {"notifications": get_notification_catalog()}

    @mcp.tool()
    async def watch_project_notifications(project_key: str) -> dict:
        """
        Start watching a project for quality gate changes and new BLOCKER issues.
        Args:
        - project_key: The key of the SonarQube project.
        Returns:
        A dictionary indicating the success or failure of the operation.
        """
        return await notification_runtime.add_project(project_key)

    @mcp.tool()
    async def unwatch_project_notifications(project_key: str) -> dict:
        """
        Stop watching a project for quality gate changes and new BLOCKER issues.
        Args:
        - project_key: The key of the SonarQube project.
        Returns:
        A dictionary indicating the success or failure of the operation.
        """
        return await notification_runtime.remove_project(project_key)

    @mcp.tool()
    async def get_recent_notifications() -> dict:
        """
        Return the latest notification events detected by the background watcher.
        Returns:
        A dictionary containing the recent notification events.
        """
        return await notification_runtime.list_notifications()

    @mcp.tool()
    async def preview_notification_event(
        event_type: Literal[
            "sonarqube.quality_gate.changed",
            "sonarqube.issue.blocker_created",
        ],
        project_key: str,
        previous_status: str,
    ) -> dict:
        """
        Build a live notification payload from SonarQube data for the requested event type.
        Args:
        - event_type: The type of notification event.
        - project_key: The key of the SonarQube project.
        - previous_status: The previous status of the quality gate.
        Returns:
        A dictionary containing the previewed notification event.
        """
        if event_type == "sonarqube.quality_gate.changed":
            return await _handle_quality_gate_notification(
                project_key, previous_status, project_service
            )
        return await _handle_blocker_issue_notification(project_key, issue_service)

    @mcp.tool()
    async def assign_issue(issue_key: str, assignee: str | None = None) -> dict:
        """
        Assign or unassign a SonarQube issue. This is a write operation and should be used deliberately.
        Args:
        - issue_key: The key of the SonarQube issue.
        - assignee: The user to assign the issue to, or None to unassign.
        Returns:
        A dictionary indicating the success or failure of the operation.
        """
        return await issue_service.assign_issue(issue_key, assignee)
