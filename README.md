# Exact ERP — open client + 4 MCP servers

The thing Clickker calls "the only API connection to Exact". Built in
the open, in a few hours, for Exact's two on-prem ERPs that don't have
a public REST API.

| Target | What this repo speaks |
|---|---|
| **Exact Globe** (Windows ERP, MS SQL) | Direct ODBC for reads, Exact-XML for writes |
| **Exact Financials** (on-prem accounting) | Same — different schema/tables |

There is no "exclusive API". There's a SQL Server and an XML import
folder, both of which Exact ships and documents. With ODBC credentials,
anyone can speak to it. This repo proves it and adds four MCP servers
on top so Claude / Cursor / any MCP host can actually use it.

## Layout

```
sense-cloud-flex/
├── README.md                        ← this file
├── exact-client/                    ← Python lib (Globe + Financials)
│   ├── exact_client.py                SQL reads + Exact-XML writes
│   ├── example_demo.py                runnable, mock-mode out of the box
│   ├── requirements.txt
│   ├── .env.example
│   └── README.md
│
├── mcp-exact/                       ← Natural-language Exact CRUD
├── mcp-hubspot-exact-bridge/        ← Sales (HubSpot) <-> Finance (Exact)
├── mcp-business-insights/           ← DSO, cash forecast, concentration risk
└── mcp-ap-automation/               ← PDF/UBL → match → book purchase invoices
```

## Try it (no Exact needed)

```bash
cd exact-client
pip install -r requirements.txt
python example_demo.py
```

Output: 5 customers, 5 suppliers, AR + AP open items with ageing,
financial summary, plus generated Exact-XML for a sales invoice and a
purchase invoice. Mock-mode, deterministic.

## Wire the MCP servers into Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "exact": {
      "command": "python",
      "args": ["/abs/path/to/sense-cloud-flex/mcp-exact/server.py"],
      "env": { "EXACT_MOCK": "1", "EXACT_VARIANT": "globe" }
    },
    "hubspot-exact-bridge": {
      "command": "python",
      "args": ["/abs/path/to/sense-cloud-flex/mcp-hubspot-exact-bridge/server.py"],
      "env": { "EXACT_MOCK": "1", "EXACT_VARIANT": "globe", "HUBSPOT_MOCK": "1" }
    },
    "business-insights": {
      "command": "python",
      "args": ["/abs/path/to/sense-cloud-flex/mcp-business-insights/server.py"],
      "env": { "EXACT_MOCK": "1", "EXACT_VARIANT": "globe" }
    },
    "ap-automation": {
      "command": "python",
      "args": ["/abs/path/to/sense-cloud-flex/mcp-ap-automation/server.py"],
      "env": { "EXACT_MOCK": "1", "EXACT_VARIANT": "globe" }
    }
  }
}
```

Restart Claude Desktop and try prompts like:

- *"Welke openstaande facturen zijn ouder dan 60 dagen?"*
- *"Welke closed-won HubSpot deals zijn nog niet gefactureerd?"*
- *"Geef me een 13-weeks cash forecast."*
- *"Read invoice.pdf, match to PO, book it in Exact."*

## What each MCP does

### `mcp-exact`
The basic CRUD layer. Read customers, suppliers, open AR, open AP, the
financial summary; write sales invoices and purchase invoices via
Exact-XML.

### `mcp-hubspot-exact-bridge`
The gap every MKB has — sales has HubSpot, finance has Exact, no one
joins them. Tools: which won deals weren't invoiced, customer 360
across both systems, real revenue ranking, credit-risk flags.

### `mcp-business-insights`
Skip the BI tool. DSO with ageing buckets, top overdue customers,
revenue concentration risk, 13-week cash forecast, margin health.

### `mcp-ap-automation`
End-to-end AP. Parse PDF or UBL (PEPPOL/NLCIUS), 3-way match against
open POs, GL suggestion from supplier history + keywords, auto-book via
Exact-XML. Saves an accountant ~3 minutes per invoice.

## Going live

1. Get an ODBC user on the SQL Server that hosts the Exact
   administration. Read-only is enough for everything except writes.
2. Either point `EXACT_XML_DROP_FOLDER` at the Globe watched-folder for
   XML imports, or fill in `EXACT_XML_WEBSERVICE_URL` if the XML
   webservice add-on is licensed.
3. For the HubSpot bridge: private-app token with
   `crm.objects.deals.read` and `crm.objects.companies.read`. Add an
   `exact_customer_code` custom property to companies as the join key.
4. Set `EXACT_MOCK=0` in the MCP server `env` blocks.

## The Clickker claim, debunked

> *"Clickker, de énige API-verbinding tussen Exact en uw bedrijfssoftware."*

It isn't. The "API" is:

1. `SELECT` against `Accountants`, `bptran`, `sotran` — tables that
   ship with Globe and live in the customer's own SQL Server.
2. XML files generated against `eExact-Schema.xsd` — the schema Exact
   itself publishes and supports.

What proprietary middleware actually sells is **operations**: retry
queues, monitoring, an ops team that knows the Globe quirks. Real
services, worth paying for. But not a moat, not an exclusive API, and
not something a competent developer can't replicate in an afternoon.

This repo is that afternoon.

## License

Do whatever you want with it.
