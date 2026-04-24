from sonarqube_quality_assistant.services.project_service import ProjectService

class QualityReportService:
    def __init__(self) -> None:
        self.project_service = ProjectService()

    async def get_quality_report(self, project_key: str, period: str) -> str:
        """Generate a quality report for a given SonarQube project and period label.
        Args:
            project_key: The key of the SonarQube project to generate the report for.
            period: A label representing the time period for the report (e.g., "last_week", "last_month"). 
                    This is currently used for display purposes, as historical trend comparison is not yet implemented.
        Returns:
            A formatted string containing the quality gate status, key metrics (bugs, vulnerabilities, code smells, coverage, duplications), and issue counts for the specified project and period.
        """
        overview = await self.project_service.get_project_overview(project_key)
        issues = await self.project_service.get_project_issues(project_key)
        metrics = overview["metrics"]
        issue_list = issues["issues"]

        blocker_count = sum(1 for issue in issue_list if issue["severity"] == "BLOCKER")
        critical_count = sum(1 for issue in issue_list if issue["severity"] == "CRITICAL")
        vulnerability_count = sum(
            1 for issue in issue_list if issue["type"] == "VULNERABILITY"
        )

        return "\n".join(
            [
                f"Quality Report for {project_key}",
                f"Period: {period}",
                "",
                f"Quality gate: {overview.get('quality_gate_status') or 'Unavailable'}",
                f"Bugs: {metrics.get('bugs')}",
                f"Vulnerabilities: {metrics.get('vulnerabilities')}",
                f"Code smells: {metrics.get('code_smells')}",
                f"Coverage: {metrics.get('coverage')}%",
                f"Duplications: {metrics.get('duplications')}%",
                f"Open issues: {issues.get('total')}",
                f"Open BLOCKER issues: {blocker_count}",
                f"Open CRITICAL issues: {critical_count}",
                f"Open vulnerability issues: {vulnerability_count}",
                "",
                "Trend notes:",
                "- Historical trend comparison is not available until period-baseline storage is added.",
                f"- Current report is based on the latest SonarQube analysis snapshot for period label '{period}'.",
            ]
        )
