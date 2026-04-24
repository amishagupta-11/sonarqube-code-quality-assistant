"""
Main MCP server entrypoint for the SonarQube Quality Assistant.

This module initializes the FastMCP server, loads environment configuration,
registers resources/tools/prompts, patches request handling to capture the
active client session, and enables runtime notifications to be pushed back
to connected clients.
"""

from mcp.server.fastmcp import FastMCP
from sonarqube_quality_assistant.server.notifications import get_notification_catalog
from sonarqube_quality_assistant.server.prompts import register_prompts
from sonarqube_quality_assistant.server.resources import register_resources
from sonarqube_quality_assistant.server.tools import register_tools
from sonarqube_quality_assistant.server.watcher import watcher_lifespan
from sonarqube_quality_assistant.server.notification_runtime import notification_runtime
from sonarqube_quality_assistant.utils.env import load_env
import logging

load_env()

_log = logging.getLogger("app.notifier")
_active_session = None

mcp = FastMCP("sonarqube-quality-assistant", lifespan=watcher_lifespan)

original_handle_request = mcp._mcp_server._handle_request


async def _patched_handle_request(req, *args, **kwargs):
    """
    Intercept incoming MCP requests and capture the active session.

    This wrapper patches the internal FastMCP request handler so the current
    client session can be stored and later used for sending runtime
    notifications.

    Args:
        req: Incoming MCP request object.
        *args: Additional positional arguments.
        **kwargs: Additional keyword arguments.

    Returns:
        Result of the original request handler execution.
    """
    global _active_session

    try:
        ctx = mcp._mcp_server.request_context.get()

        if ctx is not None and hasattr(ctx, "session"):
            _active_session = ctx.session
            _log.info(f"Session captured: {type(_active_session)}")

    except Exception as e:
        _log.warning(f"Session capture failed: {e}")

    return await original_handle_request(req, *args, **kwargs)


mcp._mcp_server._handle_request = _patched_handle_request


async def send_runtime_notification(payload):
    """
    Send runtime notifications to the currently active MCP client session.

    If no active session exists, the notification is skipped. If sending fails,
    the stored session is cleared to allow future reconnection.

    Args:
        payload (dict): Notification payload containing message details.

    Returns:
        None
    """
    global _active_session

    if _active_session is None:
        _log.warning("No active session yet, notification dropped")
        return

    try:
        await _active_session.send_log_message(
            level="info",
            data=payload,
            logger="sonarqube-quality-assistant",
        )

        _log.info(f"Notification sent: {payload.get('type')}")

    except Exception as e:
        _log.error(f"Failed to send notification: {e}", exc_info=True)
        _active_session = None


# Register runtime notification listener
notification_runtime.register_listener(send_runtime_notification)

# Register MCP components
register_resources(mcp)
register_tools(mcp)
register_prompts(mcp)

# Load supported notification definitions
NOTIFICATION_CATALOG = get_notification_catalog()