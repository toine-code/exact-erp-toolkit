# mcp-business-insights

Skip the dashboards. Ask.

> "What's my DSO and is it healthy?"
> "Top 5 customers I should chase first."
> "What's my revenue concentration risk?"
> "Project cash for the next 90 days."
> "How's the margin holding up?"

Every tool runs straight on Exact data via the shared `exact-client/`
library, so it works in mock mode out of the box.

## Tools

| Tool | What it answers |
|---|---|
| `dso_analysis` | Days Sales Outstanding, ageing buckets, health interpretation |
| `top_overdue_customers` | Ranked chase list (amount, days, count) |
| `revenue_concentration` | Top-1 / top-3 / top-5 share of revenue + risk flag |
| `cash_forecast_90d` | 13-week cash forecast from current AR/AP |
| `margin_health` | Gross margin and pct vs healthy thresholds |

## Why MKB cares

Most accountants run these calculations once a quarter, manually, in
Excel. With this MCP a managing director gets the same insight in
seconds, in a conversation, without buying a BI tool.

## Setup

```bash
pip install mcp requests
```

```json
{
  "mcpServers": {
    "business-insights": {
      "command": "python",
      "args": ["/Users/you/sense-cloud-flex/mcp-business-insights/server.py"],
      "env": { "EXACT_MOCK": "1", "EXACT_VARIANT": "online" }
    }
  }
}
```
