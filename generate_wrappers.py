#!/usr/bin/env python3
"""
Generate Python wrapper files for MCP tools.

This script connects to MCP servers and generates importable Python modules
that wrap the MCP tools, allowing code execution environments to call them.

Based on: https://www.anthropic.com/engineering/code-execution-with-mcp
"""

import json
from pathlib import Path
from mcp import ClientSession, stdio_client, StdioServerParameters


def sanitize_name(name: str) -> str:
    """Convert tool name to valid Python identifier."""
    return name.replace("-", "_").replace(".", "_")


def get_python_type(json_schema: dict) -> str:
    """Convert JSON schema type to Python type hint."""
    if not json_schema:
        return "Any"

    type_str = json_schema.get("type", "any")

    type_mapping = {
        "string": "str",
        "integer": "int",
        "number": "float",
        "boolean": "bool",
        "array": "list",
        "object": "dict",
        "null": "None",
    }

    return type_mapping.get(type_str, "Any")


def generate_wrapper_file(server_name: str, mcp_tools: list, output_dir: Path):
    """Generate a Python wrapper file for MCP tools from a server."""

    # Create the wrapper content
    lines = [
        '"""',
        f'Auto-generated wrappers for {server_name} MCP server.',
        '',
        'These functions can be imported and called from code execution environments.',
        'They make calls to the underlying MCP server.',
        '"""',
        '',
        'from typing import Any',
        'from .mcp_client import call_mcp_tool',
        '',
        '',
    ]

    # Generate a function for each tool
    for tool in mcp_tools:
        tool_name = tool.name
        description = tool.description or "No description available."

        # Get input schema
        input_schema = tool.inputSchema if hasattr(tool, 'inputSchema') else {}
        properties = input_schema.get("properties", {})
        required = input_schema.get("required", [])

        # Build function signature
        params = []
        for param_name, param_schema in properties.items():
            param_type = get_python_type(param_schema)
            if param_name in required:
                params.append(f"{param_name}: {param_type}")
            else:
                params.append(f"{param_name}: {param_type} = None")

        params_str = ", ".join(params) if params else ""

        # Build function
        lines.extend([
            f'def {sanitize_name(tool_name)}({params_str}) -> Any:',
            f'    """',
            f'    {description}',
        ])

        # Add parameter documentation
        if properties:
            lines.append('    ')
            lines.append('    Args:')
            for param_name, param_schema in properties.items():
                param_desc = param_schema.get("description", "")
                lines.append(f'        {param_name}: {param_desc}')

        lines.extend([
            '    """',
            f'    return call_mcp_tool("{server_name}", "{tool_name}", {{',
        ])

        # Add parameters to call
        for param_name in properties.keys():
            lines.append(f'        "{param_name}": {param_name},')

        lines.extend([
            '    })',
            '',
            '',
        ])

    # Write the file
    output_file = output_dir / f"{sanitize_name(server_name)}.py"
    output_file.write_text('\n'.join(lines))
    print(f"Generated: {output_file}")

    return [tool.name for tool in mcp_tools]


def generate_mcp_client(output_dir: Path, server_configs: dict):
    """Generate the mcp_client.py that handles actual MCP calls."""

    lines = [
        '"""',
        'MCP client for making tool calls from code execution environment.',
        '',
        'This module maintains connections to MCP servers and handles tool calls.',
        '"""',
        '',
        'import asyncio',
        'import json',
        'from typing import Any',
        'from mcp import ClientSession, stdio_client, StdioServerParameters',
        '',
        '',
        '# MCP server configurations',
        'SERVERS = {',
    ]

    # Add server configs
    for name, config in server_configs.items():
        lines.append(f'    "{name}": {{')
        lines.append(f'        "command": "{config["command"]}",')
        lines.append(f'        "args": {config["args"]},')
        lines.append('    },')

    lines.extend([
        '}',
        '',
        '',
        'def call_mcp_tool(server_name: str, tool_name: str, arguments: dict) -> Any:',
        '    """',
        '    Call an MCP tool and return its result.',
        '    ',
        '    Args:',
        '        server_name: Name of the MCP server',
        '        tool_name: Name of the tool to call',
        '        arguments: Tool arguments',
        '    ',
        '    Returns:',
        '        The tool result',
        '    """',
        '    async def _call():',
        '        config = SERVERS[server_name]',
        '        async with stdio_client(StdioServerParameters(',
        '            command=config["command"],',
        '            args=config["args"]',
        '        )) as (read, write):',
        '            async with ClientSession(read, write) as session:',
        '                await session.initialize()',
        '                result = await session.call_tool(tool_name, arguments)',
        '                ',
        '                # Extract content from result',
        '                if hasattr(result, "content") and result.content:',
        '                    if len(result.content) == 1:',
        '                        content = result.content[0]',
        '                        if hasattr(content, "text"):',
        '                            try:',
        '                                return json.loads(content.text)',
        '                            except json.JSONDecodeError:',
        '                                return content.text',
        '                    texts = []',
        '                    for item in result.content:',
        '                        if hasattr(item, "text"):',
        '                            texts.append(item.text)',
        '                    return texts',
        '                ',
        '                return None',
        '    ',
        '    return asyncio.run(_call())',
        '',
    ])

    output_file = output_dir / "mcp_client.py"
    output_file.write_text('\n'.join(lines))
    print(f"Generated: {output_file}")


def generate_init_file(output_dir: Path, server_tools: dict):
    """Generate __init__.py to make it a package and expose all tools."""

    lines = [
        '"""',
        'MCP tool wrappers for code execution.',
        '',
        'Import MCP tools directly:',
        '    from mcp_tools import get_total_pages, get_data_chunk',
        '',
        'Or import from specific servers:',
        '    from mcp_tools.data_tools import get_total_pages',
        '"""',
        '',
    ]

    # Import from each module
    for server_name, tool_names in server_tools.items():
        sanitized = sanitize_name(server_name)
        tools_str = ', '.join(tool_names)
        lines.append(f'from .{sanitized} import {tools_str}')

    lines.extend([
        '',
        '__all__ = [',
    ])

    # Export all tools
    for tool_names in server_tools.values():
        for tool_name in tool_names:
            lines.append(f'    "{tool_name}",')

    lines.extend([
        ']',
        '',
    ])

    output_file = output_dir / "__init__.py"
    output_file.write_text('\n'.join(lines))
    print(f"Generated: {output_file}")


def main():
    """Generate wrappers for all configured MCP servers."""

    # Server configurations
    servers = {
        "data_tools": {
            "command": "python",
            "args": ["mcp_servers/data_mcp_server.py"],
        },
    }

    # Create output directory
    output_dir = Path("mcp_tools")
    output_dir.mkdir(exist_ok=True)

    print("Generating MCP tool wrappers...")
    print("=" * 80)

    server_tools = {}

    # Generate wrapper for each server
    import asyncio

    async def get_tools_from_server(server_name, config):
        async with stdio_client(StdioServerParameters(
            command=config["command"],
            args=config["args"]
        )) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                return result.tools

    for server_name, config in servers.items():
        print(f"\nConnecting to {server_name}...")

        # Connect to MCP server and get tools
        mcp_tools = asyncio.run(get_tools_from_server(server_name, config))
        print(f"Found {len(mcp_tools)} tools: {[t.name for t in mcp_tools]}")

        # Generate wrapper file
        tool_names = generate_wrapper_file(server_name, mcp_tools, output_dir)
        server_tools[server_name] = tool_names

    # Generate mcp_client.py
    print("\nGenerating MCP client...")
    generate_mcp_client(output_dir, servers)

    # Generate __init__.py
    print("\nGenerating package init...")
    generate_init_file(output_dir, server_tools)

    print("\n" + "=" * 80)
    print("✓ Wrapper generation complete!")
    print(f"\nGenerated files in {output_dir}/")
    print("\nYou can now import tools in code execution:")
    print("    from mcp_tools import get_total_pages, get_data_chunk")


if __name__ == "__main__":
    main()
