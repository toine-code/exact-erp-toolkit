# mcp-hubspot-exact-bridge

De pijn die bijna elk MKB op Exact + HubSpot heeft:

- Sales heeft een deal gewonnen in HubSpot, drie weken later heeft
  finance 'm nog steeds niet gefactureerd. Niemand merkt het.
- Finance jaagt op een klant met 90 dagen achterstand terwijl sales
  diezelfde klant een vervolgproject probeert te pitchen.
- Niemand weet welke HubSpot-klanten werkelijk top-omzet leveren in
  Exact.

Deze MCP-server overbrugt de twee systemen on-demand.

## Tools

| Tool | Wat het beantwoordt |
|---|---|
| `find_uninvoiced_won_deals` | Welke closed-won HubSpot deals zijn nog niet als factuur in Exact verschenen? |
| `customer_360` | Volledig HubSpot + Exact beeld voor één klant |
| `top_customers_by_revenue` | Échte omzet-ranking (Exact), niet pipeline (HubSpot) |
| `credit_risk_flags` | Klanten waar HubSpot mee pitched terwijl hun openstaande post in brand staat |

## Setup

```bash
pip install mcp requests
```

Koppelen aan Claude Desktop:

```json
{
  "mcpServers": {
    "hubspot-exact-bridge": {
      "command": "python",
      "args": ["/Users/jij/exact-erp-toolkit/mcp-hubspot-exact-bridge/server.py"],
      "env": {
        "EXACT_MOCK": "1",
        "EXACT_VARIANT": "globe",
        "HUBSPOT_MOCK": "1",
        "HUBSPOT_TOKEN": ""
      }
    }
  }
}
```

Voor live gebruik: genereer een HubSpot private-app token met
`crm.objects.deals.read` en `crm.objects.companies.read`, zet
`HUBSPOT_MOCK=0`, vul `HUBSPOT_TOKEN` in.

Aan de HubSpot-kant: maak een custom property `exact_customer_code` op
companies en mapping deze 1:1 met de Exact debiteurcode. Dat is de
brug.
