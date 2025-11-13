#!/usr/bin/env python3
"""
MCP Server for paginated data fetching tools.

This MCP server exposes tools for fetching paginated user activity data.
Run with: python mcp_servers/data_mcp_server.py
"""

import time

from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("Data Tools MCP Server")


@mcp.tool()
def get_total_pages() -> int:
    """
    Get the total number of data pages available.

    Returns:
        The total number of pages (always returns 30 for this demo)
    """
    # Simulate API latency
    time.sleep(0.1)
    return 30


@mcp.tool()
def get_data_chunk(page: int) -> dict:
    """
    Fetch a chunk of user activity data for a specific page.

    This simulates a paginated API endpoint that returns user activity data.
    Each page contains 10 records with timestamps and activity types.

    Args:
        page: The page number to fetch (1-indexed, must be between 1 and 30)

    Returns:
        Dictionary containing page metadata and records with user activity data
    """
    # Simulate API latency
    time.sleep(0.2)

    if page < 1 or page > 30:
        return {
            "error": f"Invalid page number: {page}. Must be between 1 and 30.",
            "records": [],
        }

    # Generate simulated data
    records = []
    for i in range(10):
        record_id = (page - 1) * 10 + i + 1
        records.append(
            {
                "id": record_id,
                "user_id": f"user_{record_id % 7 + 1}",  # 7 different users
                "activity": _get_activity_type(record_id),
                "timestamp": f"2024-01-{page:02d}T{i:02d}:00:00Z",
                "metadata": {
                    "duration_seconds": (record_id * 13) % 120 + 10,
                    "success": record_id % 4 != 0,  # Every 4th record is a failure
                },
            }
        )

    return {"page": page, "total_pages": 30, "records": records}


def _get_activity_type(record_id: int) -> str:
    """Helper to generate activity types."""
    activities = ["login", "page_view", "api_call", "file_upload", "search"]
    return activities[record_id % len(activities)]


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
