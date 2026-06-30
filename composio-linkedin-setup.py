"""
Composio LinkedIn MCP Setup
- Creates a Composio session with LinkedIn toolkit
- Prints the MCP URL and configuration for pi

Usage:
  1. Set your API key:  set COMPOSIO_API_KEY=your_key_here  (Windows)
     or: export COMPOSIO_API_KEY=your_key_here  (Mac/Linux)
  2. Run: python composio-linkedin-setup.py
  3. Add the MCP URL to pi's mcp.json
"""

import os
from composio import Composio

API_KEY = os.environ.get("COMPOSIO_API_KEY")
if not API_KEY:
    print("❌ COMPOSIO_API_KEY not set!")
    print("   Run: set COMPOSIO_API_KEY=your_api_key")
    print("   Get your key from: https://dashboard.composio.dev")
    exit(1)

USER_ID = "ticketpilot-user"

print("🔑 Connecting to Composio...")
composio = Composio(api_key=API_KEY)

print("📦 Creating LinkedIn session...")
session = composio.create(
    user_id=USER_ID,
    toolkits=["linkedin"],
)

MCP_URL = session.mcp.url
MCP_HEADERS = session.mcp.headers  # {"x-api-key": "..."}

print("\n" + "=" * 60)
print("✅ LinkedIn MCP session ready!")
print("=" * 60)
print(f"\n📌 MCP URL:")
print(f"   {MCP_URL}")
print(f"\n📌 Headers:")
print(f"   {MCP_HEADERS}")
print(f"\n📌 Copy this into {os.path.expanduser('~/.pi/agent/mcp.json')}:")
print(f"""
{{
    "linkedin-composio": {{
        "type": "http",
        "url": "{MCP_URL}",
        "headers": {MCP_HEADERS},
        "enabled": true
    }}
}}
""")

print("=" * 60)
print("🔗 Next steps:")
print("1. Add the above config to mcp.json")
print("2. Authenticate LinkedIn at: https://dashboard.composio.dev")
print("3. Restart pi")
print("4. Use mcp() to call LinkedIn tools (or let the linkedin subagent use them)")
print("=" * 60)
