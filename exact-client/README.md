# Exact ERP (Globe + Financials) — Python client

Open-source Python client voor **Exact Globe** en **Exact Financials** —
de twee on-prem Exact ERP's zonder publieke REST API.

Dit is de laag die Clickker en andere middleware-leveranciers
propriëtair noemen. Maar het is gewoon twee bekende transports:

| Richting | Transport |
|---|---|
| Read | Directe MS SQL Server (ODBC) tegen de administratie-database |
| Write | Exact-XML (het XSD-schema dat Exact officieel ondersteunt), gedropt in een watched folder of POSTed naar de XML webservice |

Eén Python-interface voor beide producten, mock-mode out of the box.

## Quick start

```bash
pip install -r requirements.txt
python example_demo.py
```

Mock-mode output (geen Exact-installatie nodig):
- 5 klanten + 5 leveranciers
- 6 AR-facturen (2 overdue 30+ dagen)
- 5 AP-facturen (2 overdue)
- maandelijkse financiële samenvatting
- gegenereerde Exact-XML voor verkoop- en inkoopfactuur

## Live gaan

1. Kopieer `.env.example` naar `.env`.
2. Kies `EXACT_VARIANT`: `globe` of `financials`.
3. Krijg een ODBC-user op de SQL Server die de administratie host.
   Read-only is genoeg; writes gaan via XML.
4. Wijs `EXACT_XML_DROP_FOLDER` aan op de XML import-folder van Globe,
   óf vul de XML webservice URL + credentials in.
5. Zet `EXACT_MOCK=0`.

## Wat zit erin

| Bestand | Doel |
|---|---|
| `exact_client.py` | `ExactGlobeClient`, `ExactFinancialsClient`, `make_client()` factory, dataclasses |
| `example_demo.py` | Werkende demo |
| `.env.example` | Elke config-flag uitgelegd |
| `requirements.txt` | pyodbc + requests |

## De "exclusieve API"-claim, ontkracht

Vendors zoals Clickker verkopen deze laag als "de enige API-koppeling
met Exact". Wat ze in werkelijkheid hebben gebouwd:

1. SQL queries tegen bekende tabellen (`Accountants`, `bptran`, etc.)
2. Een Exact-XML generator die het officiële XSD respecteert

Beide zijn open. Met ODBC-credentials en de XSD (die Exact met het
product meelevert) kan iedereen het repliceren. Wat je middleware-
leveranciers wél betaalt is **operations**: retry-queues, monitoring,
foutafhandeling, een support-team dat de Globe-quirks kent. Echte
diensten — maar geen moat, en geen "exclusieve" API.
