import prompts  # noqa: F401 — registers prompts with mcp
import tools  # noqa: F401 — registers tools with mcp
from app import logger, mcp, neo4j_driver

if __name__ == "__main__":
	logger.info("Starting MCP server...")
	mcp.run(transport="http", host="0.0.0.0", port=8000)
	neo4j_driver.close()
	logger.info("Stopping MCP server")
