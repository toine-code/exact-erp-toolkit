# Exact ERP — open client + 4 MCP servers

Dit is wat Clickker "de énige API-verbinding tussen Exact en uw
bedrijfssoftware" noemt. In de open gebouwd, in een paar uur, voor de
twee on-prem Exact ERP's die geen publieke REST API hebben.

| Doel | Wat deze repo spreekt |
|---|---|
| **Exact Globe** (Windows ERP, MS SQL) | Directe ODBC voor reads, Exact-XML voor writes |
| **Exact Financials** (on-prem boekhouding) | Idem — ander schema / andere tabellen |

Er is geen "exclusieve API". Er is een SQL Server en een XML import-
folder, beide gewoon meegeleverd en gedocumenteerd door Exact zelf. Met
ODBC-credentials kan iedereen ermee praten. Deze repo bewijst dat, en
voegt vier MCP servers toe zodat Claude / Cursor / elke MCP host het
echt kan gebruiken.

## Layout

```
exact-erp-toolkit/
├── README.md                        ← dit bestand
├── exact-client/                    ← Python lib (Globe + Financials)
│   ├── exact_client.py                SQL reads + Exact-XML writes
│   ├── example_demo.py                draait, mock-mode out of the box
│   ├── requirements.txt
│   ├── .env.example
│   └── README.md
│
├── mcp-exact/                       ← Natural-language Exact CRUD
├── mcp-hubspot-exact-bridge/        ← Sales (HubSpot) ↔ Finance (Exact)
├── mcp-business-insights/           ← DSO, cashflow-forecast, concentratie-risico
└── mcp-ap-automation/               ← PDF/UBL → match → boek inkoopfacturen
```

## Probeer het (geen Exact nodig)

```bash
cd exact-client
pip install -r requirements.txt
python example_demo.py
```

Output: 5 klanten, 5 leveranciers, openstaande AR + AP met aging,
financiële samenvatting, plus gegenereerde Exact-XML voor zowel een
verkoop- als inkoopfactuur. Mock-mode, deterministisch.

## MCP servers koppelen aan Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "exact": {
      "command": "python",
      "args": ["/abs/pad/naar/exact-erp-toolkit/mcp-exact/server.py"],
      "env": { "EXACT_MOCK": "1", "EXACT_VARIANT": "globe" }
    },
    "hubspot-exact-bridge": {
      "command": "python",
      "args": ["/abs/pad/naar/exact-erp-toolkit/mcp-hubspot-exact-bridge/server.py"],
      "env": { "EXACT_MOCK": "1", "EXACT_VARIANT": "globe", "HUBSPOT_MOCK": "1" }
    },
    "business-insights": {
      "command": "python",
      "args": ["/abs/pad/naar/exact-erp-toolkit/mcp-business-insights/server.py"],
      "env": { "EXACT_MOCK": "1", "EXACT_VARIANT": "globe" }
    },
    "ap-automation": {
      "command": "python",
      "args": ["/abs/pad/naar/exact-erp-toolkit/mcp-ap-automation/server.py"],
      "env": { "EXACT_MOCK": "1", "EXACT_VARIANT": "globe" }
    }
  }
}
```

Herstart Claude Desktop en probeer prompts zoals:

- *"Welke openstaande facturen zijn ouder dan 60 dagen?"*
- *"Welke closed-won HubSpot deals zijn nog niet gefactureerd?"*
- *"Geef me een 13-weeks cash forecast."*
- *"Lees deze PDF, match aan een PO, en boek 'm in Exact."*

## Wat elke MCP doet

### `mcp-exact`
De basis CRUD-laag. Lees klanten, leveranciers, openstaande AR,
openstaande AP, financiële samenvatting; schrijf verkoop- en
inkoopfacturen weg via Exact-XML.

### `mcp-hubspot-exact-bridge`
Het gat dat elk MKB heeft — sales heeft HubSpot, finance heeft Exact,
niemand verbindt ze. Tools: welke gewonnen deals zijn nog niet
gefactureerd, klant-360 over beide systemen, échte omzet-ranking,
credit-risico flags.

### `mcp-business-insights`
Sla het BI-tool over. DSO met aging-buckets, top overdue klanten,
omzetconcentratie-risico, 13-weeks cash forecast, marge-gezondheid.

### `mcp-ap-automation`
End-to-end AP. Parseert PDF of UBL (PEPPOL/NLCIUS), 3-way match tegen
open inkooporders, GL-suggestie op basis van leveranciershistorie +
keywords, auto-boek via Exact-XML. Bespaart een boekhouder ~3 minuten
per factuur.

## Live gaan

1. Krijg een ODBC-user op de SQL Server die de Exact-administratie
   host. Read-only is genoeg voor alles behalve writes.
2. Wijs `EXACT_XML_DROP_FOLDER` aan op Globe's watched-folder voor XML
   imports, óf vul `EXACT_XML_WEBSERVICE_URL` in als de XML webservice
   add-on gelicenseerd is.
3. Voor de HubSpot-bridge: private-app token met
   `crm.objects.deals.read` en `crm.objects.companies.read`. Voeg een
   `exact_customer_code` custom property toe aan companies als join-key.
4. Zet `EXACT_MOCK=0` in de MCP server `env` blokken.

## De Clickker-claim, ontkracht

> *"Clickker, de énige API-verbinding tussen Exact en uw bedrijfssoftware."*

Dat is het niet. De "API" is:

1. `SELECT` op `Accountants`, `bptran`, `sotran` — tabellen die met
   Globe meegeleverd worden en in de SQL Server van de klant zélf
   staan.
2. XML-bestanden volgens `eExact-Schema.xsd` — het schema dat Exact
   zelf publiceert en ondersteunt.

Beide zijn open. Met ODBC-credentials en de XSD (die Exact bij het
product meelevert) kan iedereen dit nabouwen. Wat propriëtaire
middleware echt verkoopt zijn **operations**: retry-queues, monitoring,
een ops-team dat de Globe-quirks kent. Echte diensten, geld waard. Maar
geen moat, geen exclusieve API, en niet iets wat een competente
ontwikkelaar niet in een middag kan repliceren.

Deze repo ís die middag.

## Licentie

Doe ermee wat je wilt (MIT).
