#!/usr/bin/env python3
"""
Lab 03 Solution: Claude as MCP Client
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

MODEL = "claude-haiku-4-5-20251001"
SERVER_SCRIPT = str(Path(__file__).parent / "server.py")


# TODO 1 Solution: Convert MCP tools to Anthropic format
def mcp_tools_to_anthropic(mcp_tools) -> list[dict]:
    """Convert MCP Tool objects to Anthropic API tool format."""
    anthropic_tools = []
    for tool in mcp_tools:
        anthropic_tools.append({
            "name": tool.name,
            "description": tool.description or "",
            "input_schema": tool.inputSchema,
        })
    return anthropic_tools


# TODO 2 Solution: Execute a tool call via the MCP session
async def call_mcp_tool(session: ClientSession, tool_name: str, tool_input: dict) -> str:
    """Call a tool on the MCP server and return the result as a string."""
    result = await session.call_tool(tool_name, tool_input)
    if result.content:
        return result.content[0].text
    return "no result"


# TODO 3 Solution: Full Claude + MCP conversation loop
async def run_conversation(session: ClientSession, user_message: str) -> None:
    """Run a multi-turn Claude conversation with MCP tools available."""
    client = anthropic.Anthropic()

    # Discover tools from the MCP server
    tools_response = await session.list_tools()
    tools = mcp_tools_to_anthropic(tools_response.tools)

    messages = [{"role": "user", "content": user_message}]

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            tools=tools,
            messages=messages,
        )

        # Add assistant turn to messages
        messages.append({"role": "assistant", "content": response.content})

        # Check if we're done
        if response.stop_reason != "tool_use":
            # Print the final text response
            for block in response.content:
                if hasattr(block, "text"):
                    print(f"\nClaude: {block.text}")
            break

        # Process tool calls
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            print(f"\n[Tool call] {block.name}({json.dumps(block.input, indent=2)})")

            result_text = await call_mcp_tool(session, block.name, block.input)
            print(f"[Tool result] {result_text[:200]}{'...' if len(result_text) > 200 else ''}")

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result_text,
            })

        # Send tool results back to Claude
        messages.append({"role": "user", "content": tool_results})


async def main() -> None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY not set. Check your .env file.")
        sys.exit(1)

    print("Lab 03 Solution: Claude as MCP Client")
    print("=" * 40)

    server_params = StdioServerParameters(
        command="python",
        args=[SERVER_SCRIPT],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print(f"\nDiscovered {len(tools.tools)} tools from server:")
            for t in tools.tools:
                print(f"  - {t.name}: {t.description}")

            print("\n" + "=" * 40)
            question = "What is the current status of the payments service in prod? Are there any recent alerts I should know about?"
            print(f"User: {question}")
            print("=" * 40)

            await run_conversation(session, question)


if __name__ == "__main__":
    asyncio.run(main())
