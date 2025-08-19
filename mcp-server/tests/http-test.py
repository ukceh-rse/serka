from fastmcp import Client
import asyncio


async def test_deployed_server():
	# Connect to a running server
	async with Client("http://localhost:8000/mcp/") as client:
		await client.ping()

		# Test with real network transport
		tools = await client.list_tools()
		print(tools)


if __name__ == "__main__":
	asyncio.run(test_deployed_server())
