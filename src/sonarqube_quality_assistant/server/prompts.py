from mcp.server.fastmcp import FastMCP

def register_prompts(mcp: FastMCP) -> None:
    """
    Register all MCP prompts related to SonarQube quality analysis.
    This function defines and registers prompts that guide the assistant in performing specific tasks, 
    such as analyzing pull request readiness based on SonarQube data.
    Args:
        mcp: The FastMCP instance to register prompts with.
    """
    @mcp.prompt()
    def pr_readiness_check(project_key: str, branch: str) -> str:
        """Check whether a branch is ready for pull request review."""
        return "\n".join(
            [
                "System role: SonarQube PR readiness analyst.",
                f"Project key: {project_key}",
                f"Branch: {branch}",
                "",
                "Message sequence:",
                "1. Fetch the project quality gate status for the specified branch.",
                "2. Fetch the new issues introduced on that branch and summarize their severities and types.",
                "3. Fetch the branch coverage delta compared to the target branch or previous baseline.",
                "4. Decide whether the PR is Ready or Not Ready.",
                "5. Return a concise verdict, key risks, and recommended next actions for the developer.",
            ]
        )
