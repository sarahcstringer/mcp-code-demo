"""
Example 1: Traditional tool calling with MCP

SCENARIO: Analyzing paginated API logs. Each API call returns 10 user activity
records. There are 30 pages total (300 records).

TASK: Calculate total failed activities, most active user, and average duration.

HOW IT WORKS (traditional tool calling):
1. MCP tools are passed to Claude as available tools
2. Claude calls get_total_pages() → integer 30 → goes to context window
3. Claude calls get_data_chunk(1) → 10 full JSON records → all go to context
4. Claude calls get_data_chunk(2) → 10 more records → all go to context
5. ... repeats for all 30 pages ...
6. All 300 records are now sitting in the context window
7. Claude processes them in context (counting, filtering, averaging)

RESULT: ~300 records × ~200 tokens per record = ~60,000 tokens just for intermediate data
that only needed processing, not reasoning.
"""

import os
import sys
import time

from anthropic import Anthropic
from dotenv import load_dotenv

# Add parent directory to path so we can import mcp_tools
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mcp_tools import get_data_chunk, get_total_pages

load_dotenv()


# Define MCP tools for Claude (traditional approach)
MCP_TOOLS = [
    {
        "name": "get_total_pages",
        "description": "Get the total number of data pages available. Returns an integer.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_data_chunk",
        "description": "Fetch a chunk of user activity data for a specific page. Returns a dict with page metadata and records.",
        "input_schema": {
            "type": "object",
            "properties": {
                "page": {
                    "type": "integer",
                    "description": "The page number to fetch (1-indexed). Use get_total_pages() first to determine the valid range.",
                }
            },
            "required": ["page"],
        },
    },
]


def call_mcp_tool(tool_name: str, arguments: dict) -> dict:
    """Call an MCP tool and return result."""
    if tool_name == "get_total_pages":
        return {"result": get_total_pages()}
    elif tool_name == "get_data_chunk":
        return {"result": get_data_chunk(arguments["page"])}
    else:
        return {"error": f"Unknown tool: {tool_name}"}


def main():
    """Run the traditional tool calling example."""

    start_time = time.time()

    print("=" * 80)
    print("EXAMPLE 1: TRADITIONAL TOOL CALLING (WITH MCP)")
    print("=" * 80)
    print("\nMCP tools loaded: get_total_pages, get_data_chunk")
    print()

    # Initialize the Anthropic client
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # System prompt
    system_prompt = """You are a data analyst. You MUST complete this entire task:

1. Call get_total_pages() to get the number of pages
2. Call get_data_chunk(page) for EVERY SINGLE page from 1 to total_pages. If there are 30 pages, you MUST fetch all 30 pages. Do not stop early.
3. Once you have fetched ALL pages, analyze the complete dataset to calculate:
   - Total number of failed activities (where metadata.success == false)
   - Most active user (the user_id with the most activities)
   - Average duration of all activities (mean of metadata.duration_seconds)
4. Return a summary with these three metrics

CRITICAL: You must fetch ALL pages (page 1 through page total_pages). Do not stop at page 5 or any other arbitrary number. Complete the entire task."""

    print("Task: Fetch and analyze 30 pages of user activity data (300 records)")
    print("Approach: Traditional - each MCP tool call returns data to context window")
    print("-" * 80)
    print()

    # Initial task
    task = "Fetch all available data pages and analyze the user activity to calculate total failures, most active user, and average duration."

    # Agent loop
    messages = [{"role": "user", "content": task}]
    total_input_tokens = 0
    total_output_tokens = 0

    while True:
        # Call Claude with MCP tools
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=4096,
            system=system_prompt,
            tools=MCP_TOOLS,
            messages=messages,
        )

        # Track token usage
        total_input_tokens += response.usage.input_tokens
        total_output_tokens += response.usage.output_tokens

        # Add assistant response to messages
        messages.append({"role": "assistant", "content": response.content})

        # Check if we're done
        if response.stop_reason == "end_turn":
            # Extract final text response
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text
            break

        # Handle tool use
        if response.stop_reason == "tool_use":
            tool_results = []

            for block in response.content:
                if block.type == "tool_use":
                    print(f"Tool call: {block.name}({block.input})")

                    # Call the MCP tool
                    result = call_mcp_tool(block.name, block.input)

                    # Show result size for data chunks
                    if block.name == "get_data_chunk":
                        print(
                            f"  → Returned {len(result['result']['records'])} records to context"
                        )

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result["result"]),
                        }
                    )

            # Add tool results to messages
            messages.append({"role": "user", "content": tool_results})
        else:
            print(f"Unexpected stop reason: {response.stop_reason}")
            break

    print("\n" + "=" * 80)
    print("RESULT")
    print("=" * 80)
    print(final_text)
    print()

    # Show token usage and timing
    end_time = time.time()
    total_time = end_time - start_time

    print("=" * 80)
    print("METRICS")
    print("=" * 80)
    print(f"Input tokens:  {total_input_tokens:,}")
    print(f"Output tokens: {total_output_tokens:,}")
    print(f"Total tokens:  {total_input_tokens + total_output_tokens:,}")
    print(f"Total time:    {total_time:.2f}s")
    print()

    print(
        "Note: All 300 records from the MCP server passed through the context window,"
    )
    print(
        "consuming significant tokens for intermediate data that only needed processing."
    )
    print("=" * 80)


if __name__ == "__main__":
    main()
