from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from sonarqube_quality_assistant.server.notifications import (
    build_new_blocker_issue_notification,
    build_quality_gate_changed_notification,
    build_issue_severity_changed_notification,
)
from sonarqube_quality_assistant.services.project_service import ProjectService
from sonarqube_quality_assistant.utils.logger import get_logger


@dataclass
class ProjectWatchState:
    """
    Maintains the last known state of a watched project for change detection.
    Attributes:
        quality_gate_status: The last known quality gate status (e.g., "OK", "ERROR").
        blocker_issue_keys: Set of issue keys currently classified as BLOCKER.
        issue_severities: Mapping of issue keys to their last known severity levels.
    """
    quality_gate_status: str | None = None
    blocker_issue_keys: set[str] = field(default_factory=set)
    issue_severities: dict[str, str] = field(default_factory=dict)


class NotificationRuntime:
    def __init__(self) -> None:
        self._logger = get_logger("notification-runtime")
        self._project_service: ProjectService | None = None
        self._watched_projects: set[str] = set()
        self._project_states: dict[str, ProjectWatchState] = {}
        self._notifications: deque[dict[str, Any]] = deque(maxlen=100)
        self._lock = asyncio.Lock()
        self._listeners = []

    async def add_project(self, project_key: str) -> dict[str, Any]:
        """
        Add a project to the watch list and prime its state for change detection.
        Args:
            project_key (str): The key of the SonarQube project to watch.
        Returns:
            dict: A response containing the success status and the updated list of watched projects.
        """
        async with self._lock:
            self._watched_projects.add(project_key)
            self._project_states.setdefault(project_key, ProjectWatchState())

        await self._prime_project_state(project_key)
        return {
            "success": True,
            "watched_projects": sorted(self._watched_projects),
        }
    
    def register_listener(self, callback):
        """
        Register a callback to receive notifications when they are emitted.
        Args:            
            callback (callable): An async function that accepts a notification payload.
        """
        self._listeners.append(callback)

    async def _emit_notification(self, payload):
        """
        Emit a notification to all registered listeners.
        Args:
            payload (dict): The notification payload to send to listeners.
        """
        for listener in self._listeners:
            await listener(payload)

    async def remove_project(self, project_key: str) -> dict[str, Any]:
        """
        Remove a project from the watch list and clear its stored state.
        Args:
            project_key (str): The key of the SonarQube project to stop watching.
        Returns:
            dict: A response containing the success status and the updated list of watched projects.
        """
        async with self._lock:
            self._watched_projects.discard(project_key)
            self._project_states.pop(project_key, None)

        return {
            "success": True,
            "watched_projects": sorted(self._watched_projects),
        }

    async def list_watched_projects(self) -> dict[str, Any]:
        """
        List the currently watched projects.
        Returns:
            dict: A response containing the list of currently watched project keys.
        """
        async with self._lock:
            return {"watched_projects": sorted(self._watched_projects)}

    async def list_notifications(self) -> dict[str, Any]:
        """
        List recent notifications that have been emitted.
        Returns:
            dict: A response containing a list of recent notifications and the currently watched projects.
        """
        async with self._lock:
            return {
                "notifications": list(self._notifications),
                "watched_projects": sorted(self._watched_projects),
            }

    async def poll_once(self) -> None:
        """
        Poll all watched projects for changes and emit notifications as needed.
        This method can be called periodically to check for updates on the watched projects.
        """
        async with self._lock:
            project_keys = list(self._watched_projects)

        for project_key in project_keys:
            try:
                await self._poll_project(project_key)
            except Exception as exc:
                self._logger.warning(
                    f"Notification polling failed for {project_key}: {exc}"
                )

    async def _prime_project_state(self, project_key: str) -> None:
        """
        Fetch the current state of the project to initialize change detection.
        Args:
            project_key (str): The key of the SonarQube project to prime.
        """
        project_service = self._get_project_service()
        quality_gate = await project_service.get_quality_gate_status(project_key)
        issues = await project_service.get_project_issues(project_key)

        quality_gate_status = quality_gate.get("projectStatus", {}).get("status")
        
        all_issues = issues.get("issues", [])
        blocker_keys = {
            issue["key"] for issue in all_issues if issue.get("severity") == "BLOCKER"
        }
        issue_severities = {
            issue["key"]: issue.get("severity")
            for issue in all_issues
            if issue.get("key") and issue.get("severity")
        }

        async with self._lock:
            self._project_states[project_key] = ProjectWatchState(
                quality_gate_status=quality_gate_status,
                blocker_issue_keys=blocker_keys,
                issue_severities=issue_severities,
            )
        self._logger.info(f"Primed {project_key}: gate={quality_gate_status}, issues={len(issue_severities)}")

    async def _poll_project(self, project_key: str) -> None:
        """
        Poll the project for changes and emit notifications if any relevant changes are detected.
        Args:
            project_key (str): The key of the SonarQube project to poll.
        """
        project_service = self._get_project_service()
        quality_gate = await project_service.get_quality_gate_status(project_key)
        issues = await project_service.get_project_issues(project_key)

        current_status = quality_gate.get("projectStatus", {}).get("status")
        analyzed_at = (
            quality_gate.get("projectStatus", {}).get("period", {}).get("date")
            or quality_gate.get("analysedAt")
        )

        all_issues = issues.get("issues", [])
        blocker_issues = [i for i in all_issues if i.get("severity") == "BLOCKER"]
        current_blocker_keys = {i["key"] for i in blocker_issues if i.get("key")}
        current_severities = {
            i["key"]: i.get("severity")
            for i in all_issues
            if i.get("key") and i.get("severity")
        }

        async with self._lock:
            state = self._project_states.setdefault(project_key, ProjectWatchState())

            # Quality gate changed status
            if (
                state.quality_gate_status is not None
                and current_status is not None
                and current_status != state.quality_gate_status
            ):
                notification = build_quality_gate_changed_notification(
                    project_key=project_key,
                    previous_status=state.quality_gate_status,
                    current_status=current_status,
                    analyzed_at=analyzed_at,
                )
                self._notifications.appendleft(notification)
                await self._emit_notification(notification)

            # New BLOCKER issues
            new_blocker_keys = current_blocker_keys - state.blocker_issue_keys
            for issue in blocker_issues:
                if issue.get("key") in new_blocker_keys:
                    notification = build_new_blocker_issue_notification(
                        project_key=project_key,
                        issue_key=issue.get("key"),
                        component=issue.get("component"),
                        message=issue.get("message"),
                        introduced_at=issue.get("creationDate"),
                    )
                    self._notifications.appendleft(notification)
                    await self._emit_notification(notification)

            # Severity changed on existing issues
            for issue_key, current_severity in current_severities.items():
                previous_severity = state.issue_severities.get(issue_key)
                if previous_severity and current_severity != previous_severity:
                    notification = build_issue_severity_changed_notification(
                        project_key=project_key,
                        issue_key=issue_key,
                        previous_severity=previous_severity,
                        current_severity=current_severity,
                    )
                    self._notifications.appendleft(notification)
                    await self._emit_notification(notification)

            # Update state
            state.quality_gate_status = current_status
            state.blocker_issue_keys = current_blocker_keys
            state.issue_severities = current_severities 

    def _get_project_service(self) -> ProjectService:
            """
            Lazily initialize the ProjectService instance.
            Returns:
                ProjectService: An instance of the ProjectService class.
            """
            if self._project_service is None:
                self._project_service = ProjectService()
            return self._project_service


notification_runtime = NotificationRuntime()
