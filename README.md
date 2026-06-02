# sonarqube-quality-assistant

`sonarqube-quality-assistant` is a Python Model Context Protocol (MCP) server that lets an AI assistant fetch and summarize SonarQube quality data such as projects, issues, hotspots, and quality gates.

## Key Features

- MCP-based SonarQube integration
- Natural language querying of code quality metrics
- Release readiness assessment
- Security and quality risk analysis
- Executive quality summaries
- AI-generated remediation recommendations
  
## Project Goals

- Connect an AI assistant to SonarQube through a reusable MCP server
- Support developer workflows like PR readiness checks and critical issue lookup
- Support reporting workflows for leads and client-facing quality summaries
- Submit a clean assignment package with implementation, schemas, docs, and screenshots

## Suggested Workflow

1. Create a virtual environment and install dependencies with `pip install -e .`
2. Copy the `.env.example` keys to `.env` and fill in your SonarQube URL,token and Groq key
3. Run the server with `python -m sonarqube_quality_assistant.main`
4. Connect the server in MCP Inspector
5. Add the server to Claude Desktop using `claude_desktop_config.json`

## Project Structure

sonarqube-quality-assistant/
├── src/
│   └── sonarqube_quality_assistant/
│       ├── server/
│       ├── tools/
│       ├── resources/
│       └── prompts/
├── tests/
├── .env.example
├── .gitignore
├── pyproject.toml
├── uv.lock
└── README.md
- ``

- `pyproject.toml` – Main Python project configuration file for dependencies, build settings, and tool configs.

## Example AI Workflow

### Release Readiness Assessment

A developer can ask:

> Can I merge this release branch?

The AI assistant uses MCP tools to retrieve:

* Critical issues
* Security hotspots
* Quality gate status
* Code coverage metrics
* Technical debt indicators

The assistant then analyzes the retrieved data and generates:

* Release readiness assessment
* Risk summary
* Prioritized remediation recommendations
* Executive-friendly quality summary

### Sample Response

**Release Readiness:** Not Recommended

**Risk Level:** High

**Findings:**

* 4 Critical Issues detected
* 2 Open Security Hotspots
* Quality Gate Failed
* Coverage below required threshold

**Recommended Actions:**

1. Resolve critical security findings.
2. Address high-severity bugs impacting maintainability.
3. Increase test coverage to meet release standards.

### Why AI Is Required

Traditional dashboards present raw metrics but require engineers to manually interpret the results.

This assistant combines quality data, contextual reasoning, and natural language interaction to provide actionable recommendations, enabling developers, leads, and stakeholders to make faster and more informed release decisions.


## Run Tests with Coverage

Use the following command to run all test cases and generate a coverage report:

```bash
python -m pytest tests/ --cov=src --cov-report=xml:coverage.xml -v
