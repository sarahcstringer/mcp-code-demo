# Code execution with MCP

This repository demonstrates the key difference between traditional tool calling and code execution with the [Model Context Protocol (MCP)](https://modelcontextprotocol.io). It shows how separating context from execution environment makes AI agents more efficient and cost-effective.

This demo is based blog posts from [Anthropic](https://www.anthropic.com/engineering/code-execution-with-mcp) and [Cloudflare](https://blog.cloudflare.com/code-mode/) about code execution with MCP.

The examples here use a local MCP server to demonstrate the full MCP + code execution stack. The MCP server simulates latency and provides synthetic data. Run the demos below or read the [writeup](WRITEUP.md) for more details about the concepts.

## Run the demos

This demo shows two examples of using MCP + code execution. The first example uses traditional tool calling, where all tool results pass through the context window. The second example uses code execution, where the agent writes code that calls the MCP tools directly in an execution environment.

It uses a local MCP server (`mcp_servers/data_mcp_server.py`) that exposes an API for fetching paginated data about synthetic user activity. The server introduces a 100ms delay to simulate latency in a real API.

### Prerequisites

- Python 3.10+
- Anthropic API key (get one at [console.anthropic.com](https://console.anthropic.com/))

### Installation

The following commands do the following:
- Clone the repository
- Install dependencies
- Copy `.env.example` to `.env`
    - **You must add your ANTHROPIC_API_KEY to the `.env` file**
- Generate MCP tool wrappers for the code execution MCP example

```bash
# Clone this repository
git clone https://github.com/sarahcstringer/mcp-code-demo
cd mcp-code-demo

# Create a virtual environment
python -m venv venv
source venv/bin/activate # On Windows use `source venv/Scripts/activate`

# Install dependencies
pip install -r requirements.txt

# Set up your API key
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# Generate MCP tool wrappers (required for Example 2)
python generate_wrappers.py
```

> The MCP tool wrappers are used for the code execution MCP example. 

### Examples

### Example 1: Traditional MCP tool calling

```bash
python examples/traditional_tool_calling.py
```

This example demonstrates traditional MCP tool calling where all tool results pass through the context window. The agent analyzes paginated API logs by fetching user activity data from an MCP server.

**The MCP server exposes:**
- `get_total_pages()` - Returns total number of pages (30)
- `get_data_chunk(page)` - Returns dict with 10 user activity records

**Each record contains:**
```json
{
  "id": 1,
  "user_id": "user_3",
  "activity": "login",
  "timestamp": "2024-01-01T00:00:00Z",
  "metadata": {
    "duration_seconds": 45,
    "success": true
  }
}
```

**The task:** Calculate total failed activities, identify the most active user, and compute average duration.

**What happens:**
- MCP tool descriptions for the Data Tools server are loaded into context window up front
- Agent calls `get_total_pages()` MCP tool → gets integer `30` → goes to context
- Agent calls `get_data_chunk(1)` MCP tool → gets JSON with 10 full records → all go to context
- Agent calls `get_data_chunk(2)` MCP tool → 10 more full records → all go to context
- Repeats for all 30 pages
- All 300 complete records from MCP server are now sitting in the context window
- Agent processes this data in context (counting failures, grouping by user, averaging durations)
- Every MCP tool result consumes context window tokens (~60,000 tokens just for the data)

### Example 2: Code execution with MCP

```bash
python examples/code_execution.py
```

> **Note:**: you must generate the `mcp_tools/` directory first by running `python generate_wrappers.py`

This example does the same task as the previous example, but with code execution instead of traditional tool calling. It follows [Anthropic's pattern](https://www.anthropic.com/engineering/code-execution-with-mcp) for using code execution with MCP.

**What happens:**
- Agent has access to bash tool (code execution environment)
- No MCP tools passed directly to agent - agent must discover them via the file system
- Agent explores the file system and discovers `mcp_tools/` directory
- Agent reads the Python wrapper files to understand available functions
- Agent writes bash commands that execute Python code importing and calling the MCP wrappers:
  ```python
  from mcp_tools import get_total_pages, get_data_chunk

  total = get_total_pages()  # Wrapper calls MCP server - gets 30
  all_records = []
  for page in range(1, total + 1):
      data = get_data_chunk(page)  # Wrapper calls MCP server - gets 10 records
      all_records.extend(data['records'])

  # Process locally in execution environment
  failed = sum(1 for r in all_records if not r['metadata']['success'])
  # ... more processing ...
  print(f"Failed: {failed}, Most active: user_2, Avg duration: 69s")
  ```
- The code runs in execution environment via bash tool
- MCP wrappers make the actual MCP server calls IN THE EXECUTION ENVIRONMENT
- All 300 records are fetched from the MCP server and processed there
- The 300 full JSON records from MCP never enter the context window
- Only the final summary string (3 lines) goes back to context
- Token savings: ~50,000 tokens avoided by keeping data out of context

## The core insight

**Traditional tool calling** loads all MCP tool descriptions, parameter schemas, return types, and usage instructions into the context window upfront. Then it sends all intermediate results through the LLM's context window as the agent orchestrates tool calls one by one.

**Code execution** allows dynamic discovery—the agent explores the file system to find available tools and reads their implementations. It runs processing in a separate execution environment and only sends final results back to context.

This can reduce token usage by 80+% while enabling new capabilities like polling, waiting, and stateful processing.

**Demo scenario:** Both examples analyze paginated user activity logs from an MCP server. The task is to calculate total failed activities, identify the most active user, and compute average duration across 300 records (30 pages of 10 records each).

![Comparison diagram showing traditional tool calling with all operations in the context window versus code execution with a separate execution environment for processing, demonstrating 82% token reduction](./mcp-code.png)

**Implementation note:** Modern agent frameworks like [Claude Code](https://www.anthropic.com/engineering/code-execution-with-mcp) and [Cloudflare Agents](https://blog.cloudflare.com/code-mode/) provide code execution environments built-in. However, you can achieve the same pattern by giving an LLM a bash tool that executes commands - this is the approach used in these examples.

**Security consideration:** When giving an LLM the ability to execute code, implement appropriate guardrails such as sandboxing, human-in-the-loop verification for sensitive operations, code review before execution, and limiting filesystem/network access. Only run code in environments where you can verify and trust what's being executed.

## Project structure

```
mcp-code/
├── examples/                         # Runnable examples
│   ├── traditional_tool_calling.py  # Example 1: Traditional MCP tool calling
│   └── code_execution.py            # Example 2: Code execution + MCP (file system wrappers)
├── mcp_servers/                      # MCP server for demo
│   └── data_mcp_server.py           # MCP server: paginated data fetching tools
├── mcp_tools/                        # Auto-generated Python wrappers (run generate_wrappers.py)
│   ├── __init__.py                  # Package exports
│   ├── mcp_client.py                # Handles actual MCP communication
│   └── data_tools.py                # Wrappers for data_tools MCP server
├── generate_wrappers.py             # Script to generate mcp_tools/ from MCP servers
├── WRITEUP.md                       # Writeup of the demo and my thoughts on the concepts
├── COMPARISON.md                    # Visual comparison of approaches
├── README.md                        # This file
└── requirements.txt                 # Python dependencies
```

## Learn more

- [Read the full writeup](WRITEUP.md) - Detailed explanation of concepts

## Next steps

- [Read about MCP](https://modelcontextprotocol.io)
