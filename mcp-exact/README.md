# mcp-exact

Praat met Exact in natuurlijke taal.

> "Laat me alle openstaande facturen ouder dan 30 dagen zien."
> "Wat is onze bruto marge deze maand?"
> "Maak een factuur voor klant 60002, 8 uur consultancy à 145 EUR."

De MCP-server stelt Exact (Globe / Financials) beschikbaar als tools
voor elke MCP-host — Claude Desktop, Claude Code, Cursor, Continue, Zed,
noem maar op.

## Tools

| Tool | Wat het doet |
|---|---|
| `list_customers` | Klanten doorbladeren |
| `get_customer` | Eén klant opzoeken op code |
| `list_suppliers` | Leveranciers doorbladeren |
| `list_open_invoices` | Filter open/overdue verkoopfacturen |
| `list_purchase_invoices` | Open inkoopfacturen (AP) |
| `overdue_total` | DSO samenvatting in één keer |
| `get_financial_summary` | Omzet / kosten / marge / cash voor een periode |
| `create_sales_invoice` | Verkoopfactuur schrijven via Exact-XML |
| `book_purchase_invoice` | Inkoopfactuur boeken via Exact-XML |

## Installeren

```bash
pip install mcp requests
```

De server importeert de client uit `../exact-client/exact_client.py`.
Behoud de folder-structuur, of zet `PYTHONPATH` ernaar.

## Koppelen aan Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "exact": {
      "command": "python",
      "args": ["/Users/jij/exact-erp-toolkit/mcp-exact/server.py"],
      "env": {
        "EXACT_MOCK": "1",
        "EXACT_VARIANT": "globe"
      }
    }
  }
}
```

Herstart Claude Desktop. Vraag: *"Welke openstaande facturen zijn ouder
dan 30 dagen?"* — je ziet de tool-calls landen.

## Live gaan

Zet `EXACT_MOCK=0` en vul de echte credentials in het `env`-blok in
(of laad ze uit een `.env` naast de server). Dezelfde tools raken dan
de echte Exact-instantie.
