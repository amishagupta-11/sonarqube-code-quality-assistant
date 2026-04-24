import sys
import unittest
from pathlib import Path

SRC_PATH = Path(__file__).resolve().parents[1] / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from sonarqube_quality_assistant.sonarqube.mappers import (
    _to_float,
    _to_int,
    map_branch_list_response,
    map_hotspot_response,
    map_issue_response,
    map_overview_response,
    map_project_list_response,
)

class MapperTests(unittest.TestCase):
    def test_map_project_list_response_keeps_project_metadata(self):
        response = {
            "components": [
                {
                    "key": "app",
                    "name": "Main App",
                    "lastAnalysisDate": "2026-04-22T10:00:00+0000",
                    "visibility": "private",
                }
            ],
            "paging": {"pageIndex": 1, "pageSize": 100},
        }

        mapped = map_project_list_response(response)

        self.assertEqual(
            mapped,
            {
                "projects": [
                    {
                        "key": "app",
                        "name": "Main App",
                        "last_analysis_date": "2026-04-22T10:00:00+0000",
                        "visibility": "private",
                    }
                ],
                "paging": {"pageIndex": 1, "pageSize": 100},
            },
        )

    def test_map_branch_list_response_extracts_quality_gate_status(self):
        response = {
            "branches": [
                {
                    "name": "main",
                    "isMain": True,
                    "type": "LONG",
                    "status": {"qualityGateStatus": "OK"},
                    "analysisDate": "2026-04-21T09:00:00+0000",
                    "excludedFromPurge": False,
                }
            ]
        }

        mapped = map_branch_list_response(response)

        self.assertEqual(
            mapped,
            {
                "branches": [
                    {
                        "name": "main",
                        "is_main": True,
                        "type": "LONG",
                        "status": "OK",
                        "analysis_date": "2026-04-21T09:00:00+0000",
                        "excluded_from_purge": False,
                    }
                ]
            },
        )

    def test_map_overview_response_converts_numeric_metrics_and_uses_period_date(self):
        measures_response = {
            "component": {
                "key": "app",
                "name": "Main App",
                "measures": [
                    {"metric": "bugs", "value": "2"},
                    {"metric": "vulnerabilities", "value": "3"},
                    {"metric": "code_smells", "value": "14"},
                    {"metric": "coverage", "value": "81.5"},
                    {"metric": "duplicated_lines_density", "value": "1.2"},
                ],
            }
        }
        quality_gate_response = {
            "projectStatus": {
                "status": "ERROR",
                "conditions": [{"metricKey": "coverage", "status": "ERROR"}],
                "period": {"date": "2026-04-20T08:00:00+0000"},
            },
            "analysedAt": "2026-04-19T08:00:00+0000",
        }

        mapped = map_overview_response(measures_response, quality_gate_response)

        self.assertEqual(mapped["project_key"], "app")
        self.assertEqual(mapped["project_name"], "Main App")
        self.assertEqual(mapped["quality_gate_status"], "ERROR")
        self.assertEqual(mapped["conditions"], [{"metricKey": "coverage", "status": "ERROR"}])
        self.assertEqual(mapped["analysis_date"], "2026-04-20T08:00:00+0000")
        self.assertEqual(
            mapped["metrics"],
            {
                "bugs": 2,
                "vulnerabilities": 3,
                "code_smells": 14,
                "coverage": 81.5,
                "duplications": 1.2,
            },
        )

    def test_map_overview_response_falls_back_to_analysed_at(self):
        mapped = map_overview_response(
            {"component": {"key": "app", "name": "Main App", "measures": []}},
            {"projectStatus": {"status": "OK"}, "analysedAt": "2026-04-18T07:00:00+0000"},
        )

        self.assertEqual(mapped["analysis_date"], "2026-04-18T07:00:00+0000")
        self.assertIsNone(mapped["metrics"]["coverage"])

    def test_map_issue_response_preserves_issue_fields_and_total(self):
        response = {
            "issues": [
                {
                    "key": "ISSUE-1",
                    "severity": "CRITICAL",
                    "type": "BUG",
                    "component": "app:src/main.py",
                    "line": 12,
                    "message": "Fix me",
                    "status": "OPEN",
                    "assignee": "alice",
                    "effort": "20min",
                    "creationDate": "2026-04-17T06:00:00+0000",
                }
            ],
            "total": 3,
            "paging": {"pageIndex": 1},
        }

        mapped = map_issue_response(response)

        self.assertEqual(mapped["total"], 3)
        self.assertEqual(mapped["paging"], {"pageIndex": 1})
        self.assertEqual(mapped["issues"][0]["line"], 12)
        self.assertEqual(mapped["issues"][0]["assignee"], "alice")

    def test_map_hotspot_response_uses_paging_total_when_available(self):
        response = {
            "hotspots": [
                {
                    "key": "HOT-1",
                    "component": "app:src/security.py",
                    "line": 8,
                    "message": "Review this hotspot",
                    "status": "TO_REVIEW",
                    "securityCategory": "sql-injection",
                    "vulnerabilityProbability": "HIGH",
                    "author": "bob",
                    "creationDate": "2026-04-16T05:00:00+0000",
                }
            ],
            "paging": {"total": 9},
        }

        mapped = map_hotspot_response(response)

        self.assertEqual(mapped["total"], 9)
        self.assertEqual(mapped["hotspots"][0]["security_category"], "sql-injection")

    def test_numeric_helpers_handle_none_and_strings(self):
        self.assertEqual(_to_int("3.0"), 3)
        self.assertEqual(_to_float("7.25"), 7.25)
        self.assertIsNone(_to_int(None))
        self.assertIsNone(_to_float(None))
