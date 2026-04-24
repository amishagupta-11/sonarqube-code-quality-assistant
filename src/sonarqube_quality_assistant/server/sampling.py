from __future__ import annotations
from typing import Any

def build_issue_sampling_payload(project_key: str, issues_response: dict[str, Any]) -> dict[str, Any]:
    """Build a payload for issue sampling and grouping by root cause patterns.
    Args:
        project_key: The key of the SonarQube project.
        issues_response: The raw response from SonarQube containing issue details.
    Returns:
        A structured payload with a subset of issues and instructions for grouping and analysis."""
    issues = issues_response.get("issues", [])
    sampled_issues: list[dict[str, Any]] = []

    for issue in issues[:30]:
        sampled_issues.append(
            {
                "key": issue.get("key"),
                "severity": issue.get("severity"),
                "type": issue.get("type"),
                "component": issue.get("component"),
                "line": issue.get("line"),
                "message": issue.get("message"),
                "rule": issue.get("rule"),
                "effort": issue.get("effort"),
            }
        )

    return {
        "project_key": project_key,
        "sampling_purpose": "Group SonarQube issues by root-cause pattern and recommend batch fixes.",
        "instruction": (
            "Group the issues by root cause pattern such as missing null checks, hardcoded credentials, "
            "duplicate logic, unused imports, or weak error handling. For each group, explain the pattern, "
            "estimate risk, and propose a batch-fix strategy the team can apply across files."
        ),
        "issue_count": len(sampled_issues),
        "issues": sampled_issues,
    }

def build_sampling_flow_description() -> list[dict[str, str]]:
    """Provide a step-by-step description of the issue sampling and grouping flow.
    Returns:
        A list of dictionaries, each describing a step in the sampling and grouping process.
    """
    return [
        {
            "step": "server_to_client",
            "description": (
                "The MCP server fetches 30+ issues from SonarQube and sends a structured sampling request "
                "to the client with grouping instructions."
            ),
        },
        {
            "step": "client_to_llm",
            "description": (
                "The MCP client forwards the sampling payload to the LLM so the model can cluster issues by "
                "root cause and reason about batch remediation."
            ),
        },
        {
            "step": "llm_to_client",
            "description": (
                "The LLM returns grouped issue families, high-risk findings, and suggested batch fixes."
            ),
        },
        {
            "step": "client_to_server",
            "description": (
                "The client returns the sampling result to the MCP server, which can then present the grouped "
                "analysis in a report or a follow-up tool result."
            ),
        },
    ]