# mcp-business-insights

Sla het dashboard over. Vraag het gewoon.

> "Wat is mijn DSO en is die gezond?"
> "Top 5 klanten die ik als eerste moet bellen."
> "Wat is mijn omzetconcentratie-risico?"
> "Voorspel mijn cash voor de komende 90 dagen."
> "Hoe houdt mijn marge zich?"

Elke tool draait direct op Exact-data via de gedeelde `exact-client/`
bibliotheek, dus werkt out of the box in mock mode.

## Tools

| Tool | Wat het beantwoordt |
|---|---|
| `dso_analysis` | Days Sales Outstanding, aging-buckets, gezondheids-oordeel |
| `top_overdue_customers` | Ranked chase-lijst (bedrag, dagen, aantal) |
| `revenue_concentration` | Top-1 / top-3 / top-5 omzetaandeel + risico-flag |
| `cash_forecast_90d` | 13-weeks cashflow-forecast op basis van huidige AR/AP |
| `margin_health` | Bruto marge en percentage tegen gezonde drempels |

## Waarom MKB hier wat aan heeft

De meeste accountants draaien deze berekeningen één keer per kwartaal,
met de hand, in Excel. Met deze MCP krijgt een directeur dezelfde
inzichten in seconden, in een gesprek, zonder een BI-tool te kopen.

## Setup

```bash
pip install mcp requests
```

```json
{
  "mcpServers": {
    "business-insights": {
      "command": "python",
      "args": ["/Users/jij/exact-erp-toolkit/mcp-business-insights/server.py"],
      "env": { "EXACT_MOCK": "1", "EXACT_VARIANT": "globe" }
    }
  }
}
```
