# mcp-ap-automation

End-to-end accounts payable automation for Exact Globe / Financials.

The unsexy reality of MKB finance: someone retypes PDF supplier invoices
into Exact, 3 minutes each, line by line, with typos. With this MCP,
the workflow becomes:

1. PDF or UBL lands in a folder.
2. *"Process new invoices, match to POs, book the clean ones."*
3. Done.

## Tools

| Tool | What it does |
|---|---|
| `extract_invoice_from_pdf` | Read a PDF, pull header + lines (heuristic; swap for Claude vision in prod) |
| `extract_invoice_from_ubl` | Parse PEPPOL / NLCIUS UBL 2.1 XML (mandatory in NL late 2026) |
| `extract_invoice_from_text` | Same extractor on raw text |
| `match_to_purchase_order` | 3-way match: supplier + amount (+ optional PO ref), tolerance configurable |
| `suggest_gl_account` | Heuristic GL suggestion from description keywords |
| `auto_book_invoice` | Generate the Exact-XML purchase invoice; dry-run by default |
| `ap_ageing` | Payables ageing buckets |
| `pay_this_week` | Due within 7 days — the bookkeeper's hit list |
| `spend_by_supplier` | Top suppliers by spend |

## PEPPOL note

Starting late 2026 Dutch B2B invoices must support PEPPOL / NLCIUS UBL.
This server parses UBL natively so any PEPPOL Access Point output drops
straight in.

## Setup

```bash
pip install mcp pypdf requests
```

```json
{
  "mcpServers": {
    "ap-automation": {
      "command": "python",
      "args": ["/Users/you/sense-cloud-flex/mcp-ap-automation/server.py"],
      "env": { "EXACT_MOCK": "1", "EXACT_VARIANT": "globe" }
    }
  }
}
```

## Typical session

```
You: Read ~/Downloads/kpn-mei.pdf and book it if it matches PO-2026-118.

Claude (calls extract_invoice_from_pdf):
  Supplier: KPN Zakelijk, Invoice KPN-2026-0500, EUR 413.82, due 31 mei.

Claude (calls match_to_purchase_order):
  Exact reference match on PO-2026-118, delta EUR 0.00.

Claude (calls auto_book_invoice, dry_run=true):
  XML generated, 6 lines, GL 4500 (Telecom). Want me to book it?

You: Yes, send it.

Claude (auto_book_invoice, dry_run=false):
  Booked. XML written to /exact/import/purchase_70001_1779138712.xml.
  Exact will process on next polling cycle (~2 min).
```

## Production-grade extraction

The bundled `extract_invoice_from_pdf` is a regex heuristic — fine for
clean digital PDFs, weak on scans and exotic layouts. For production,
replace the body of that tool with a single call to Claude (vision) and
ask for structured JSON. That moves accuracy from ~70% to ~98% and
handles scans natively.
