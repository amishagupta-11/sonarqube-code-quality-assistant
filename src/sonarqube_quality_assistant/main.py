import sys
from sonarqube_quality_assistant.utils.env import load_env
from sonarqube_quality_assistant.utils.logger import get_logger

def main() -> None:
    load_env()
    logger = get_logger("bootstrap")
    logger.info("main() entered")

    try:
        from sonarqube_quality_assistant.server.app import mcp

        logger.info("Starting sonarqube-quality-assistant")
        logger.info("calling mcp.run()")
        mcp.run(transport="stdio")
        logger.info("mcp.run() returned")
    except Exception as exc:
        logger.error(f"server crashed: {exc!r}")
        raise

if __name__ == "__main__":
    main()
