"""
Ember Bridge MCP Interface
===========================
Minimal MCP-compatible server info
(Full STDIO server can be added later)
"""

import json
from perception.bridge_router import graph_summary, ROUTES
from perception.bridge_transport import get_transport_stats


MCP_INFO = {
    "name": "ember-bridge",
    "version": "1.0.0",
    "description": "Ember Signal Multi-Terminal Bridge",
    "capabilities": {
        "tools": ["route_command", "process_inbox", "graph_summary", "sign", "verify"],
        "transport": "sqlite",
        "terminals": list(ROUTES.keys())
    }
}


def get_mcp_info() -> dict:
    """MCP Server Info"""
    stats = get_transport_stats()
    graph = graph_summary()
    
    return {
        **MCP_INFO,
        "status": {
            "channels": stats["channels"],
            "messages": stats["messages_by_status"],
            "graph_nodes": graph["nodes"],
            "graph_edges": graph["edges"],
            "terminals": graph["terminals"]
        }
    }


def list_tools() -> list:
    """MCP Tools စာရင်း"""
    return [
        {"name": "route_command", "description": "Route command between terminals"},
        {"name": "process_inbox", "description": "Get pending messages for terminal"},
        {"name": "graph_summary", "description": "Signed evidence graph summary"},
        {"name": "sign", "description": "Ed25519 sign payload"},
        {"name": "verify", "description": "Verify Ed25519 signature"},
    ]


if __name__ == "__main__":
    print("=" * 60)
    print("  Testing MCP Interface (P4.5)")
    print("=" * 60)
    print()
    info = get_mcp_info()
    print(json.dumps(info, indent=2, ensure_ascii=False))
    print()
    print(f"✅ {len(list_tools())} tools available.")
