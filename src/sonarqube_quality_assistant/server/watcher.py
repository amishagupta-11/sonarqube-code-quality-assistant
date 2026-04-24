from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator
from sonarqube_quality_assistant.server.notification_runtime import notification_runtime
from sonarqube_quality_assistant.utils.env import get_optional_env
from sonarqube_quality_assistant.utils.logger import get_logger

logger = get_logger("notification-watcher")

@asynccontextmanager
async def watcher_lifespan(app) -> AsyncIterator[dict]:
    """
    Lifespan context manager for the SonarQube notification watcher background task.
    This sets up a background task that periodically polls SonarQube for quality gate changes and new BLOCKER issues for watched projects. The task runs until the server shuts down, at which point it is cleanly cancelled.
    Yields:
        A dictionary containing the notification runtime instance for use in tools and resources.
    """
    poll_interval = int(get_optional_env("SONARQUBE_NOTIFICATION_POLL_SECONDS", "10") or "10")
    bootstrap_projects = [
        project.strip()
        for project in (get_optional_env("SONARQUBE_NOTIFY_PROJECTS", "") or "").split(",")
        if project.strip()
    ]

    for project_key in bootstrap_projects:
        try:
            await notification_runtime.add_project(project_key)
        except Exception as exc:
            logger.warning(f"Failed to bootstrap notification watch for {project_key}: {exc}")

    stop_event = asyncio.Event()
    task = asyncio.create_task(_poll_loop(poll_interval, stop_event))

    try:
        yield {"notification_runtime": notification_runtime}
    finally:
        stop_event.set()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            logger.info("Watcher task cancelled cleanly.")
            return


async def _poll_loop(poll_interval: int, stop_event: asyncio.Event) -> None:
    """
    Background loop that polls SonarQube for notifications at a specified interval until stopped.
    Args:
        poll_interval: The number of seconds to wait between polls.
        stop_event: An asyncio.Event that signals the loop to stop when set.
    This loop continuously polls for notifications and handles graceful shutdown when the stop_event is set."""
    while not stop_event.is_set():
        logger.info("Polling all watched projects...")
        await notification_runtime.poll_once()
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=poll_interval)
        except asyncio.CancelledError:
            logger.info("Poll loop cancelled, shutting down.")
            return
        except asyncio.TimeoutError:
            continue
