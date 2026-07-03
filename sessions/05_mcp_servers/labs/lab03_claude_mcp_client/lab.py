#!/usr/bin/env python3
"""
Lab 03: Claude as MCP Client
==============================
Connect Claude (via the Anthropic SDK) to the pre-built MCP server in server.py.

This is the bridge between Session 04 (function calling) and MCP:
  - Session 04: you hardcoded tool schemas + ran the tool loop yourself
  - Lab 03: tools come FROM the MCP server dynamically — no hardcoding

Flow:
  1. Connect to the MCP server (spawns server.py as a subprocess via stdio)
  2. Discover available tools (list_tools())
  3. Convert MCP tool definitions to Anthropic API format
  4. Run a conversation with Claude that uses those tools
  5. When Claude calls a tool, call it through the MCP session

Run:
    python lab.py

Prerequisites:
    pip install fastmcp mcp anthropic python-dotenv
    ANTHROPIC_API_KEY set in .env (two levels up)

When stuck: check solution.py
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

# Load API key from .env (two directories up from here)
load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

MODEL = "claude-haiku-4-5-20251001"   # fast + cheap for labs
SERVER_SCRIPT = str(Path(__file__).parent / "server.py")


# ---------------------------------------------------------------------------
# TODO 1: Convert MCP tool definitions to Anthropic format
# ---------------------------------------------------------------------------
# MCP gives you tools like this (mcp.types.Tool objects):
#   tool.name        -> "get_service_status"
#   tool.description -> "Get the current operational status..."
#   tool.inputSchema -> {"type": "object", "properties": {...}, "required": [...]}
#
# Anthropic API expects tools like this:
#   {
#     "name": "get_service_status",
#     "description": "...",
#     "input_schema": {...}   # same as inputSchema, different key name
#   }
#
# Complete the function below.
#
def mcp_tools_to_anthropic(mcp_tools) -> list[dict]:
    """
    Convert a list of MCP Tool objects to Anthropic API tool format.

    Args:
        mcp_tools: list of mcp.types.Tool objects from session.list_tools()

    Returns:
        list of dicts in Anthropic tool format
    """
    # TODO: iterate over mcp_tools, build and return the Anthropic format
    pass


# ---------------------------------------------------------------------------
# TODO 2: Execute a tool call via the MCP session
# ---------------------------------------------------------------------------
# When Claude returns a tool_use block, you need to:
#   1. Get the tool name and input arguments from the block
#   2. Call session.call_tool(name, arguments) — this calls the MCP server
#   3. Extract the text result from the response
#   4. Return it as a string so you can put it in a tool_result message
#
async def call_mcp_tool(session: ClientSession, tool_name: str, tool_input: dict) -> str:
    """
    Call a tool on the MCP server and return the result as a string.

    Args:
        session: Active MCP ClientSession
        tool_name: Name of the tool to call
        tool_input: Dict of arguments for the tool

    Returns:
        String result to send back to Claude as a tool_result
    """
    # TODO: call session.call_tool(tool_name, tool_input)
    # The result has a .content list; each item has a .text attribute.
    # Return the .text of the first content item, or "no result" if empty.
    pass


# ---------------------------------------------------------------------------
# TODO 3: Run the full Claude + MCP conversation loop
# ---------------------------------------------------------------------------
# This is similar to the tool loop from Session 04 — but now:
#   - Tools come from the MCP server (dynamic discovery)
#   - Tool execution goes through the MCP session
#
# Steps:
#   1. List tools from the MCP session
#   2. Convert to Anthropic format using mcp_tools_to_anthropic()
#   3. Send to Claude with the user message
#   4. While the response has tool_use blocks:
#       a. For each tool_use block:
#          - Print which tool is being called and with what args
#          - Call it via call_mcp_tool()
#          - Add the tool_result to messages
#       b. Send the updated messages back to Claude
#   5. Print Claude's final text response
#
async def run_conversation(session: ClientSession, user_message: str) -> None:
    """Run a multi-turn Claude conversation with MCP tools available."""
    client = anthropic.Anthropic()

    # TODO: implement the conversation loop
    # Hint: it's the same loop as Session 04, but replace:
    #   - hardcoded tool schemas → mcp_tools_to_anthropic(tools.tools)
    #   - manual tool execution → await call_mcp_tool(session, name, input)
    pass


# ---------------------------------------------------------------------------
# Main — connects to the MCP server and runs a demo conversation
# ---------------------------------------------------------------------------

async def main() -> None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY not set. Check your .env file.")
        sys.exit(1)

    print("Lab 03: Claude as MCP Client")
    print("=" * 40)

    # Connect to the MCP server (spawns server.py as a subprocess)
    server_params = StdioServerParameters(
        command="python",
        args=[SERVER_SCRIPT],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the connection
            await session.initialize()

            # Show what tools the server exposes
            tools = await session.list_tools()
            print(f"\nDiscovered {len(tools.tools)} tools from server:")
            for t in tools.tools:
                print(f"  - {t.name}: {t.description}")

            if any(f is None for f in [mcp_tools_to_anthropic([]), ]):
                print("\nTODO functions not complete yet — check the TODOs above.")
                return

            # Run a conversation
            print("\n" + "=" * 40)
            question = "What is the current status of the payments service in prod? Are there any recent alerts I should know about?"
            print(f"User: {question}")
            print("=" * 40)

            await run_conversation(session, question)


if __name__ == "__main__":
    asyncio.run(main())
