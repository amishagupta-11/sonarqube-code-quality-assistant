from typing import Any

def map_project_list_response(response: dict[str, Any]) -> dict[str, Any]:
    """
    Map the raw response from the SonarQube API for project listing into a structured format.
    Args:
        response: The raw JSON response from the SonarQube API containing project details.
    Returns:
        A dictionary containing a list of projects with their key details and pagination information.
    """
    projects: list[dict[str, Any]] = []

    for project in response.get("components", []):
        projects.append(
            {
                "key": project.get("key"),
                "name": project.get("name"),
                "last_analysis_date": project.get("lastAnalysisDate"),
                "visibility": project.get("visibility"),
            }
        )

    return {
        "projects": projects,
        "paging": response.get("paging", {}),
    }

def map_branch_list_response(response: dict[str, Any]) -> dict[str, Any]:
    """
    Map the raw response from the SonarQube API for branch listing into a structured format.
    Args:
        response: The raw JSON response from the SonarQube API containing branch details.
    Returns:
        A dictionary containing a list of branches with their key details.
    """
    branches: list[dict[str, Any]] = []

    for branch in response.get("branches", []):
        branches.append(
            {
                "name": branch.get("name"),
                "is_main": branch.get("isMain"),
                "type": branch.get("type"),
                "status": branch.get("status", {}).get("qualityGateStatus"),
                "analysis_date": branch.get("analysisDate"),
                "excluded_from_purge": branch.get("excludedFromPurge"),
            }
        )

    return {"branches": branches}

def map_overview_response(
    measures_response: dict[str, Any], quality_gate_response: dict[str, Any]
) -> dict[str, Any]:
    """
    Map the raw responses from the SonarQube API for project measures and quality gate status into a structured overview format.
    Args:
        measures_response: The raw JSON response from the SonarQube API containing project measures.
        quality_gate_response: The raw JSON response from the SonarQube API containing quality gate status.
    Returns:
        A dictionary containing the project's key, name, key metrics (bugs, vulnerabilities, code smells, coverage, duplications), quality gate status, conditions, and analysis date.
    """
    component = measures_response.get("component", {})
    measures = component.get("measures", [])
    metric_map = {measure.get("metric"): measure.get("value") for measure in measures}
    project_status = quality_gate_response.get("projectStatus", {})

    return {
        "project_key": component.get("key"),
        "project_name": component.get("name"),
        "metrics": {
            "bugs": _to_int(metric_map.get("bugs")),
            "vulnerabilities": _to_int(metric_map.get("vulnerabilities")),
            "code_smells": _to_int(metric_map.get("code_smells")),
            "coverage": _to_float(metric_map.get("coverage")),
            "duplications": _to_float(metric_map.get("duplicated_lines_density")),
        },
        "quality_gate_status": project_status.get("status"),
        "conditions": project_status.get("conditions", []),
        "analysis_date": project_status.get("period", {}).get("date")
        or quality_gate_response.get("analysedAt"),
    }

def map_issue_response(response: dict[str, Any]) -> dict[str, Any]:
    """
    Map the raw response from the SonarQube API for issues into a structured format.
    Args:
        response: The raw JSON response from the SonarQube API containing issue details.
    Returns:
        A dictionary containing a list of issues with their key details and pagination information.
    """
    issues: list[dict[str, Any]] = []

    for issue in response.get("issues", []):
        issues.append(
            {
                "key": issue.get("key"),
                "severity": issue.get("severity"),
                "type": issue.get("type"),
                "component": issue.get("component"),
                "line": issue.get("line"),
                "message": issue.get("message"),
                "status": issue.get("status"),
                "assignee": issue.get("assignee"),
                "effort": issue.get("effort"),
                "creation_date": issue.get("creationDate"),
            }
        )

    return {
        "issues": issues,
        "total": response.get("total", len(issues)),
        "paging": response.get("paging", {}),
    }

def map_hotspot_response(response: dict[str, Any]) -> dict[str, Any]:
    """
        Map the raw response from the SonarQube API for security hotspots into a structured format.
        Args:
            response: The raw JSON response from the SonarQube API containing security hotspot details.
        Returns:
            A dictionary containing a list of security hotspots with their key details and pagination information.
        """
    hotspots: list[dict[str, Any]] = []

    for hotspot in response.get("hotspots", []):
        hotspots.append(
            {
                "key": hotspot.get("key"),
                "component": hotspot.get("component"),
                "line": hotspot.get("line"),
                "message": hotspot.get("message"),
                "status": hotspot.get("status"),
                "security_category": hotspot.get("securityCategory"),
                "vulnerability_probability": hotspot.get("vulnerabilityProbability"),
                "author": hotspot.get("author"),
                "creation_date": hotspot.get("creationDate"),
            }
        )

    return {
        "hotspots": hotspots,
        "total": response.get("paging", {}).get("total", len(hotspots)),
        "paging": response.get("paging", {}),
    }

def _to_int(value: Any) -> int | None:
    """Convert a value to an integer if possible, otherwise return None.
    Args:
        value: The value to convert, which may be a string, number, or None.
    Returns:
        The integer representation of the value, or None if the value is None or cannot be converted.
    """
    if value is None:
        return None
    return int(float(value))

def _to_float(value: Any) -> float | None:
    """Convert a value to a float if possible, otherwise return None.
    Args:       
        value: The value to convert, which may be a string, number, or None.   
    Returns:
        The float representation of the value, or None if the value is None or cannot be converted.
    """
    if value is None:
        return None
    return float(value)
