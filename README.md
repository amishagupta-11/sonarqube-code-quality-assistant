# sonarqube-quality-assistant

`sonarqube-quality-assistant` is a Python Model Context Protocol (MCP) server that lets an AI assistant fetch and summarize SonarQube quality data such as projects, issues, hotspots, and quality gates.

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

## Run Tests with Coverage

Use the following command to run all test cases and generate a coverage report:

```bash
python -m pytest tests/ --cov=src --cov-report=xml:coverage.xml -v