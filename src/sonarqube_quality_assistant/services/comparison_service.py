from sonarqube_quality_assistant.services.project_service import ProjectService

class ComparisonService:
    def __init__(self) -> None:
        self.project_service = ProjectService()

    async def compare_projects(self, project_key_1: str, project_key_2: str) -> str:
        """
        Compare the quality metrics of two SonarQube projects and return a formatted string summarizing the differences.
        Args:
            project_key_1: The key of the first SonarQube project.
            project_key_2: The key of the second SonarQube project.
        Returns:
            A string summarizing the quality gate status, bugs, vulnerabilities, 
            code smells, coverage, and duplications for both projects for easy comparison.
        """
        project_1 = await self.project_service.get_project_overview(project_key_1)
        project_2 = await self.project_service.get_project_overview(project_key_2)
        metrics_1 = project_1["metrics"]
        metrics_2 = project_2["metrics"]

        return "\n".join(
            [
                "Quality Comparison",
                f"{project_key_1} vs {project_key_2}",
                "",
                f"{project_key_1} quality gate: {project_1.get('quality_gate_status')}",
                f"{project_key_1} bugs: {metrics_1.get('bugs')}",
                f"{project_key_1} vulnerabilities: {metrics_1.get('vulnerabilities')}",
                f"{project_key_1} code smells: {metrics_1.get('code_smells')}",
                f"{project_key_1} coverage: {metrics_1.get('coverage')}%",
                f"{project_key_1} duplications: {metrics_1.get('duplications')}%",
                "",
                f"{project_key_2} quality gate: {project_2.get('quality_gate_status')}",
                f"{project_key_2} bugs: {metrics_2.get('bugs')}",
                f"{project_key_2} vulnerabilities: {metrics_2.get('vulnerabilities')}",
                f"{project_key_2} code smells: {metrics_2.get('code_smells')}",
                f"{project_key_2} coverage: {metrics_2.get('coverage')}%",
                f"{project_key_2} duplications: {metrics_2.get('duplications')}%",
            ]
        )
