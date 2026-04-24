from __future__ import annotations

from typing import Any


def build_quality_gate_changed_notification(
    project_key: str,
    previous_status: str,
    current_status: str | None,
    analyzed_at: str | None,
) -> dict[str, Any]:
    """
    Build a notification payload for quality gate status changes.
    Args:
    - project_key: The key of the SonarQube project.
    - previous_status: The previous quality gate status.
    - current_status: The new quality gate status (can be None if unavailable).
    - analyzed_at: The timestamp of the analysis that triggered the change (can be None if unavailable).
    Returns:
    A dictionary representing the notification payload.
    """
    resolved_current_status = current_status or "UNAVAILABLE"
    resolved_analyzed_at = analyzed_at or "UNAVAILABLE"
    return {
        "type": "sonarqube.quality_gate.changed",
        "project_key": project_key,
        "payload": {
            "previous_status": previous_status,
            "current_status": resolved_current_status,
            "analyzed_at": resolved_analyzed_at,
            "summary": (
                f"Quality gate changed for {project_key}: {previous_status} -> {resolved_current_status}."
            ),
        },
    }


def build_new_blocker_issue_notification(
    project_key: str,
    issue_key: str | None,
    component: str | None,
    message: str | None,
    introduced_at: str | None,
) -> dict[str, Any]:
    """
    Build a notification payload for new BLOCKER issues.
    Args:
    - project_key: The key of the SonarQube project.
    - issue_key: The key of the new issue (can be None if unavailable).
    - component: The component where the issue was found (can be None if unavailable).
    - message: The issue message (can be None if unavailable).
    - introduced_at: The timestamp of when the issue was introduced (can be None if unavailable).
    Returns:
    A dictionary representing the notification payload.
    """
    resolved_issue_key = issue_key or "UNAVAILABLE"
    resolved_component = component or "UNAVAILABLE"
    resolved_message = message or "UNAVAILABLE"
    resolved_introduced_at = introduced_at or "UNAVAILABLE"
    return {
        "type": "sonarqube.issue.blocker_created",
        "project_key": project_key,
        "payload": {
            "issue_key": resolved_issue_key,
            "severity": "BLOCKER",
            "component": resolved_component,
            "message": resolved_message,
            "introduced_at": resolved_introduced_at,
            "summary": (
                f"New BLOCKER issue detected in {project_key} at {resolved_component}: {resolved_message}"
            ),
        },
    }

def get_notification_catalog() -> list[dict[str, Any]]:
    """
    Return a catalog of available notification types and their descriptions.
    Returns:        
        A list of dictionaries, each containing an 'event' key with the notification type and a '
    """
    return [
        {
            "event": "sonarqube.quality_gate.changed",
            "description": "Triggered when a new analysis changes the quality gate from one state to another.",
        },
        {
            "event": "sonarqube.issue.blocker_created",
            "description": "Triggered when a new BLOCKER-severity issue appears after analysis.",
        },
        {
            "event": "sonarqube.issue.severity_changed",
            "description": "Triggered when the severity of an existing issue changes.",
        },
    ]

def build_issue_severity_changed_notification(
    project_key: str,
    issue_key: str,
    previous_severity: str,
    current_severity: str,
) -> dict[str, Any]:
    """Build a notification payload for issue severity changes.
    Args:
    - project_key: The key of the SonarQube project.
    - issue_key: The key of the issue whose severity changed.
    - previous_severity: The previous severity level of the issue.
    - current_severity: The new severity level of the issue.
    Returns:
    A dictionary representing the notification payload.
    """
    return {
        "type": "sonarqube.issue.severity_changed",
        "project_key": project_key,
        "payload": {
            "issue_key": issue_key,
            "previous_severity": previous_severity,
            "current_severity": current_severity,
            "summary": (
                f"Issue {issue_key} in {project_key} severity changed: "
                f"{previous_severity} -> {current_severity}"
            ),
        },
    }