"""
Example 2: Code execution with MCP

SCENARIO: Same as Example 1 - analyzing 300 paginated API log records across 30 pages.
Same data structure, same task.

TASK: Calculate total failed activities, most active user, and average duration.

HOW IT WORKS (code execution + MCP):
1. Agent connects to Data Tools MCP server
2. Agent has BOTH python_repl (code execution) AND MCP tools available
3. Agent can discover what MCP tools are available by listing them
4. Agent writes Python code that CALLS THE MCP TOOLS directly:

   # MCP tools are available as callable functions in the execution environment
   total = get_total_pages()  # Calls MCP tool
   all_records = []
   for page in range(1, total + 1):
       data = get_data_chunk(page)  # Calls MCP tool - gets dict with 10 records
       all_records.extend(data['records'])

   # Process locally in execution environment
   failed = sum(1 for r in all_records if not r['metadata']['success'])
   user_counts = {}
   for r in all_records:
       user_counts[r['user_id']] = user_counts.get(r['user_id'], 0) + 1
   most_active = max(user_counts.items(), key=lambda x: x[1])
   avg = sum(r['metadata']['duration_seconds'] for r in all_records) / len(all_records)

   print(f"Failed: {failed}, Most active: {most_active[0]}, Avg: {avg:.1f}s")

5. Code runs in execution environment
6. MCP tool calls happen IN THE EXECUTION ENVIRONMENT (not in context!)
7. All 300 JSON records are fetched via MCP and processed in execution environment
8. Only the final 3-line summary string goes back to context window

KEY INSIGHT: MCP + code execution means MCP tool results stay in execution
environment and never hit the context window. This is the whole point!

RESULT: The 300 records never enter context. MCP provides the standardized
interface to external tools, code execution provides the processing environment.
"""

import os
import subprocess
import time

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()


# Bash tool definition for Claude
BASH_TOOL = {
    "name": "bash",
    "description": "Execute bash commands. Use this to run Python code, list files, read files, etc.",
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The bash command to execute"}
        },
        "required": ["command"],
    },
}


def execute_bash(command: str) -> str:
    """Execute a bash command and return output."""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30
        )
        output = result.stdout
        if result.stderr:
            output += f"\nSTDERR: {result.stderr}"
        return output
    except subprocess.TimeoutExpired:
        return "Command timed out after 30 seconds"
    except Exception as e:
        return f"Error executing command: {str(e)}"


def main():
    """Run the code execution example with MCP."""

    start_time = time.time()

    print("=" * 80)
    print("EXAMPLE 2: CODE EXECUTION WITH MCP")
    print("=" * 80)
    print("\nNo direct MCP connection - agent will discover tools via file system!")
    print()

    # Initialize the Anthropic client
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # System prompt
    system_prompt = """You are a data analyst with bash command execution capabilities.

You have access to a Python execution environment with MCP tool wrappers available on the file system.

Explore the 'mcp_tools' directory to see what's available. You can:
1. List files to see available modules
2. Read the Python files to understand what functions they expose
3. Import and use those functions in your code

Your task is to:
1. Explore mcp_tools/ to discover available tools
2. Write Python code that imports and uses the tools to fetch all data pages
3. Process the data in the execution environment to calculate:
   - Total number of failed activities (where metadata['success'] == False)
   - Most active user (user_id with most activities)
   - Average duration of all activities (mean of metadata['duration_seconds'])
4. Return ONLY a concise summary with these three metrics

Important: All tool calls happen in the execution environment by importing from mcp_tools.
Process ALL data in your code. Don't return raw records - only the final summary."""

    print("Task: Fetch and analyze 30 pages of user activity data (300 records)")
    print(
        "Approach: Agent explores file system, imports MCP wrappers, calls them in execution environment"
    )
    print("-" * 80)
    print()

    # Initial task
    task = """Explore the mcp_tools directory to see what's available, then write Python code to:
1. Import the data fetching tools
2. Fetch all data pages
3. Analyze to calculate total failed activities, most active user, and average duration
4. Return only the summary"""

    # Agent loop
    messages = [{"role": "user", "content": task}]
    total_input_tokens = 0
    total_output_tokens = 0

    while True:
        # Call Claude with bash tool
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=4096,
            system=system_prompt,
            tools=[BASH_TOOL],
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
                    command = block.input["command"]

                    # Show truncated version for very long commands
                    if len(command) > 200:
                        print(f"\n[Executing: {command[:200]}...]")
                        print(f"[Full command length: {len(command)} characters]")
                    else:
                        print(f"\n[Executing: {command}]")

                    # Execute the bash command
                    result = execute_bash(command)

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
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

    print("Note: Agent discovered MCP tools via file system and called them from code.")
    print("The 300 records from the MCP server never entered the context window.")
    print("This demonstrates MCP + code execution following Anthropic's pattern!")
    print("=" * 80)


if __name__ == "__main__":
    main()
