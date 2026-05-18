# Exact ERP (Globe + Financials) — Python client

Open-source Python client for **Exact Globe** and **Exact Financials** —
the two on-prem Exact ERPs that don't have a public REST API.

This is the layer Clickker and other middleware vendors claim is
proprietary. It isn't. It's two well-known transports:

| Direction | Transport |
|---|---|
| Read | Direct MS SQL Server (ODBC) against the administration database |
| Write | Exact-XML (the XSD-schema XML that Exact officially supports), dropped in a watched folder or POSTed to the XML webservice |

One Python interface for both products, mock mode out of the box.

## Quick start

```bash
pip install -r requirements.txt
python example_demo.py
```

Mock-mode output (no Exact required):
- 5 customers + 5 suppliers
- 6 AR invoices (2 overdue 30+ days)
- 5 AP invoices (2 overdue)
- monthly financial summary
- generated Exact-XML for a sales invoice + a purchase invoice

## Going live

1. Copy `.env.example` to `.env`.
2. Pick `EXACT_VARIANT`: `globe` or `financials`.
3. Get an ODBC user on the SQL Server hosting the administration.
   Read-only is enough; the writes go through XML.
4. Either point `EXACT_XML_DROP_FOLDER` at Globe's watched import folder,
   or fill in the XML webservice URL + credentials.
5. Set `EXACT_MOCK=0`.

## What's in the box

| File | Purpose |
|---|---|
| `exact_client.py` | `ExactGlobeClient`, `ExactFinancialsClient`, `make_client()` factory, dataclasses |
| `example_demo.py` | Runnable demo |
| `.env.example` | Every config flag explained |
| `requirements.txt` | pyodbc + requests |

## The "exclusive API" claim, debunked

Vendors like Clickker market this layer as "the only API connection to
Exact". What they actually built is:

1. SQL queries against well-known tables (`Accountants`, `bptran`, etc.)
2. An Exact-XML generator that respects the official XSD

Both are open. With ODBC credentials and the XSD (which Exact ships with
the product), anyone can replicate it. What you pay middleware vendors
for is **operations**: retry queues, monitoring, error handling, a
support team that knows the Globe quirks. Real services — but not a
moat, and not "exclusive".
