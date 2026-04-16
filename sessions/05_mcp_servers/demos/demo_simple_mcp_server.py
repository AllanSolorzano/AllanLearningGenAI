#!/usr/bin/env python3
"""
Demo: Simple MCP Server
========================
The absolute minimum to build a working MCP server with FastMCP.

This demo focuses on the contrast with function calling:
  - Function calling: schemas inline, loop in your app, tools exist nowhere
  - MCP server: run once, any client connects, tools live in the server

Run:
    # Test interactively with the MCP inspector
    fastmcp dev demo_simple_mcp_server.py

    # Run as stdio server
    python demo_simple_mcp_server.py

    # Point Claude Desktop at it — add to claude_desktop_config.json:
    # "simple-tools": {
    #   "command": "python",
    #   "args": ["/absolute/path/to/demo_simple_mcp_server.py"]
    # }
"""

from fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Create the server
# ---------------------------------------------------------------------------
# The name is shown to the model and appears in Claude Desktop's tool list.
mcp = FastMCP(
    "simple-tools",
    instructions="Basic arithmetic and string tools for demonstration.",
)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
# @mcp.tool() is all you need. FastMCP reads:
#   - function name    -> tool name
#   - type hints       -> JSON schema (auto-generated)
#   - docstring        -> description shown to the model
#   - default values   -> optional parameters

@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers together."""
    return a + b


@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers together."""
    return a * b


@mcp.tool()
def word_count(text: str) -> dict:
    """
    Count words, characters, and lines in a text string.

    Args:
        text: The text to analyze
    """
    return {
        "words": len(text.split()),
        "characters": len(text),
        "lines": text.count("\n") + 1,
    }


@mcp.tool()
def to_uppercase(text: str) -> str:
    """Convert text to UPPERCASE."""
    return text.upper()


# ---------------------------------------------------------------------------
# What the model sees
# ---------------------------------------------------------------------------
# When a client connects, it calls list_tools() and gets:
#
#   Tool(name="add",
#        description="Add two numbers together.",
#        inputSchema={
#          "type": "object",
#          "properties": {
#            "a": {"type": "number"},
#            "b": {"type": "number"}
#          },
#          "required": ["a", "b"]
#        })
#
# FastMCP generated that schema automatically from the function signature.
# Compare this to Session 04 where you had to write that JSON by hand
# and pass it in every single API call.


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Simple MCP Server")
    print("-" * 30)
    print("Tools: add, multiply, word_count, to_uppercase")
    print()
    print("Connect with:")
    print("  fastmcp dev demo_simple_mcp_server.py   (browser inspector)")
    print("  python demo_simple_mcp_server.py         (stdio — for Claude Desktop)")
    print()
    mcp.run()
