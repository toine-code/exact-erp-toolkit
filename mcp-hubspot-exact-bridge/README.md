# mcp-hubspot-exact-bridge

The pain almost every MKB on Exact + HubSpot has:

- Sales closed a deal in HubSpot, three weeks later finance still hasn't
  invoiced it. Nobody notices.
- Finance is chasing a 90-days-overdue customer that sales is currently
  pitching a follow-up project to.
- Nobody knows which HubSpot customers are actually their top revenue
  generators in Exact.

This MCP server bridges the two systems on demand.

## Tools

| Tool | Question it answers |
|---|---|
| `find_uninvoiced_won_deals` | Which closed-won HubSpot deals haven't shown up as Exact invoices yet? |
| `customer_360` | Full HubSpot + Exact view for one customer |
| `top_customers_by_revenue` | Real revenue ranking (Exact), not pipeline (HubSpot) |
| `credit_risk_flags` | Customers HubSpot is pitching while their AR is on fire |

## Setup

```bash
pip install mcp requests
```

Register in Claude Desktop:

```json
{
  "mcpServers": {
    "hubspot-exact-bridge": {
      "command": "python",
      "args": ["/Users/you/sense-cloud-flex/mcp-hubspot-exact-bridge/server.py"],
      "env": {
        "EXACT_MOCK": "1",
        "EXACT_VARIANT": "online",
        "HUBSPOT_MOCK": "1",
        "HUBSPOT_TOKEN": ""
      }
    }
  }
}
```

For live use: generate a HubSpot private-app token with `crm.objects.deals.read`
and `crm.objects.companies.read`, set `HUBSPOT_MOCK=0`, fill `HUBSPOT_TOKEN`.

On the HubSpot side, expose an `exact_customer_code` custom property on
companies and map it 1:1 with the Exact debtor code. That's the bridge.
