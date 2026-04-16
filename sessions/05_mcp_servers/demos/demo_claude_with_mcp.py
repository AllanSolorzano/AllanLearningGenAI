#!/usr/bin/env python3
"""
Demo: Claude Programmatically Using an MCP Server
===================================================
Shows Claude connected to demo_incident_mcp_server.py via the MCP Python client.

This is the end-to-end picture:
  1. Spawn the MCP server as a subprocess (stdio transport)
  2. Discover its tools dynamically
  3. Run a multi-turn Claude conversation
  4. Tool calls go through the MCP session — not hardcoded in your app

Compare to Session 04 (function calling):
  Session 04: you wrote schemas by hand, ran the tool loop yourself
  This demo: schemas come from the server, loop wires through MCP protocol

Run:
    python demo_claude_with_mcp.py
    python demo_claude_with_mcp.py --question "List all open incidents"

Prerequisites:
    pip install fastmcp mcp anthropic python-dotenv
    ANTHROPIC_API_KEY in .env (project root)
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

load_dotenv(Path(__file__).parent.parent.parent / ".env")

MODEL = "claude-haiku-4-5-20251001"
SERVER = str(Path(__file__).parent / "demo_incident_mcp_server.py")

DEFAULT_QUESTION = (
    "What are the open incidents right now? "
    "For each unowned incident, recommend whether I should claim it as an SRE on-call "
    "and what the first action should be. My name is sre-student."
)


# ---------------------------------------------------------------------------
# MCP → Anthropic format conversion
# ---------------------------------------------------------------------------

def mcp_tools_to_anthropic(mcp_tools) -> list[dict]:
    """
    Convert MCP Tool objects to Anthropic API format.

    MCP gives us:   tool.name, tool.description, tool.inputSchema
    Anthropic wants: {"name": ..., "description": ..., "input_schema": ...}
    """
    return [
        {
            "name": tool.name,
            "description": tool.description or "",
            "input_schema": tool.inputSchema,
        }
        for tool in mcp_tools
    ]


# ---------------------------------------------------------------------------
# Tool execution through MCP
# ---------------------------------------------------------------------------

async def call_mcp_tool(session: ClientSession, name: str, args: dict) -> str:
    """Execute a tool on the MCP server and return the text result."""
    result = await session.call_tool(name, args)
    if result.content:
        return result.content[0].text
    return "no result"


# ---------------------------------------------------------------------------
# Full conversation loop
# ---------------------------------------------------------------------------

async def run_conversation(
    session: ClientSession,
    question: str,
    verbose: bool = True,
) -> str:
    """
    Run a multi-turn Claude conversation using tools from the MCP server.
    Returns Claude's final text response.
    """
    client = anthropic.Anthropic()

    # Discover tools from server — no hardcoding
    tools_response = await session.list_tools()
    tools = mcp_tools_to_anthropic(tools_response.tools)

    if verbose:
        print(f"\nTools from MCP server ({len(tools)}):")
        for t in tools:
            print(f"  - {t['name']}")

    messages = [{"role": "user", "content": question}]
    final_response = ""

    turn = 0
    while True:
        turn += 1
        if verbose:
            print(f"\n--- Turn {turn} ---")

        response = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            tools=tools,
            messages=messages,
        )

        # Append assistant response
        messages.append({"role": "assistant", "content": response.content})

        if verbose:
            print(f"Stop reason: {response.stop_reason}")

        # Done — no more tool calls
        if response.stop_reason != "tool_use":
            for block in response.content:
                if hasattr(block, "text"):
                    final_response = block.text
                    if verbose:
                        print(f"\nClaude:\n{block.text}")
            break

        # Process tool calls through the MCP session
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            if verbose:
                print(f"\n[Calling tool] {block.name}")
                print(f"  args: {json.dumps(block.input, indent=2)}")

            result_text = await call_mcp_tool(session, block.name, block.input)

            if verbose:
                # Truncate long results for readability
                preview = result_text[:400] + ("..." if len(result_text) > 400 else "")
                print(f"  result: {preview}")

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result_text,
            })

        messages.append({"role": "user", "content": tool_results})

    return final_response


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY not set. Add it to your .env file.")
        sys.exit(1)

    # Parse optional --question flag
    question = DEFAULT_QUESTION
    if "--question" in sys.argv:
        idx = sys.argv.index("--question")
        if idx + 1 < len(sys.argv):
            question = sys.argv[idx + 1]

    print("Demo: Claude with MCP Server")
    print("=" * 50)
    print(f"Server: {Path(SERVER).name}")
    print(f"Model:  {MODEL}")
    print(f"\nUser: {question}")
    print("=" * 50)

    # Spawn the MCP server and connect
    server_params = StdioServerParameters(
        command="python",
        args=[SERVER],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await run_conversation(session, question)

    print("\n" + "=" * 50)
    print("Demo complete.")


if __name__ == "__main__":
    asyncio.run(main())
