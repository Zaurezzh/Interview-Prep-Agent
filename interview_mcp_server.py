"""
Interview Prep - Company Research MCP Server
--------------------------------------------
A minimal Model Context Protocol (MCP) server exposing ONE tool, research_company,
which runs a live web search (DuckDuckGo) and returns snippets for the agent to
reason over.

Why an MCP server instead of a plain function?
  - It decouples the capability (web research) from the agent. Any MCP client
    (our ADK agent, Claude Desktop, etc.) can consume it over a standard protocol.
  - It demonstrates the client/server tool architecture the capstone asks for.

Transport: stdio. The ADK agent launches this file as a subprocess and talks to
it over standard input/output.
"""
import asyncio
import json

from mcp import types as mcp_types
from mcp.server.lowlevel import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio

from ddgs import DDGS

# Named MCP server instance.
app = Server("interview-research-mcp")


def _search_web(query, max_results=6):
    """Run a DuckDuckGo text search and return a compact, readable digest."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
    except Exception as e:  # network hiccups, rate limits, etc.
        return "[search error] " + str(e)
    if not results:
        return "[no results]"
    lines = []
    for r in results:
        lines.append("- " + r.get("title", "") + "\n  " + r.get("body", "") + "\n  (" + r.get("href", "") + ")")
    return "\n".join(lines)


@app.list_tools()
async def list_tools():
    """Advertise the tools this server exposes to any MCP client."""
    return [
        mcp_types.Tool(
            name="research_company",
            description=(
                "Research a company for a specific job interview. Returns recent "
                "web snippets about the company business, news, values, and likely "
                "interview themes for the given role."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "company": {"type": "string", "description": "Company name"},
                    "role": {"type": "string", "description": "Target job title"},
                },
                "required": ["company", "role"],
            },
        )
    ]


@app.call_tool()
async def call_tool(name, arguments):
    """Execute a tool call requested by the MCP client (our ADK agent)."""
    if name != "research_company":
        return [mcp_types.TextContent(type="text", text=json.dumps({"error": "unknown tool " + str(name)}))]

    company = (arguments.get("company") or "").strip()
    role = (arguments.get("role") or "").strip()
    # Three focused searches beat one vague query.
    digest = "\n\n".join([
        "### " + company + " - overview\n" + _search_web(company + " company overview products"),
        "### " + company + " - recent news\n" + _search_web(company + " news 2026"),
        "### " + role + " interview\n" + _search_web(company + " " + role + " interview questions"),
    ])
    return [mcp_types.TextContent(type="text", text=digest)]


async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name=app.name,
                server_version="0.1.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
