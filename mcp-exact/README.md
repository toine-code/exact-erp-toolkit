# mcp-exact

Talk to Exact in natural language.

> "Show me all overdue invoices older than 30 days."
> "What's our gross margin this month?"
> "Create an invoice for customer 60002, 8 hours of consultancy at 145 EUR."

The MCP server exposes Exact (Online / Globe / Financials) as tools that
any MCP host can call — Claude Desktop, Claude Code, Cursor, Continue,
Zed, you name it.

## Tools

| Tool | What it does |
|---|---|
| `list_customers` | Browse customers |
| `get_customer` | Look up one customer by code |
| `list_open_invoices` | Filter open/overdue invoices |
| `overdue_total` | One-shot DSO summary |
| `get_financial_summary` | Revenue / costs / margin / cash for a period |
| `create_sales_invoice` | Write back to Exact |

## Install

```bash
pip install mcp requests
```

The server imports the client from `../exact-client/exact_client.py`. Keep
the folder layout intact, or set `PYTHONPATH` accordingly.

## Register with Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "exact": {
      "command": "python",
      "args": ["/Users/you/sense-cloud-flex/mcp-exact/server.py"],
      "env": {
        "EXACT_MOCK": "1",
        "EXACT_VARIANT": "online"
      }
    }
  }
}
```

Restart Claude Desktop. Ask: *"Welke openstaande facturen zijn ouder dan
30 dagen?"* — you should see the tool calls land.

## Going live

Drop `EXACT_MOCK=0` and fill in the real credentials in the `env` block
(or load them from a `.env` next to the server). The same tools then hit
the real Exact instance.
