# mcp-ap-automation

End-to-end crediteuren-automatisering voor Exact Globe / Financials.

De onsexy realiteit van MKB-finance: iemand typt PDF-facturen over in
Exact, 3 minuten per stuk, regel voor regel, met typfouten. Met deze
MCP wordt de flow:

1. PDF of UBL valt binnen in een folder.
2. *"Verwerk nieuwe facturen, match aan PO's, boek de schone."*
3. Klaar.

## Tools

| Tool | Wat het doet |
|---|---|
| `extract_invoice_from_pdf` | Lees een PDF, haal header + regels eruit (heuristiek; vervang door Claude vision in productie) |
| `extract_invoice_from_ubl` | Parseer PEPPOL / NLCIUS UBL 2.1 XML (in NL verplicht eind 2026) |
| `extract_invoice_from_text` | Zelfde extractor op platte tekst |
| `match_to_purchase_order` | 3-way match: leverancier + bedrag (+ optionele PO-ref), tolerantie configureerbaar |
| `suggest_gl_account` | Heuristische grootboekrekening-suggestie op basis van keywords |
| `auto_book_invoice` | Genereer de Exact-XML inkoopfactuur; dry-run by default |
| `ap_ageing` | Crediteuren-aging buckets |
| `pay_this_week` | Vervalt binnen 7 dagen — de hit-list voor de boekhouder |
| `spend_by_supplier` | Top leveranciers op uitgaven |

## PEPPOL-notitie

Vanaf eind 2026 moeten Nederlandse B2B-facturen PEPPOL / NLCIUS UBL
ondersteunen. Deze server parseert UBL native, dus elke PEPPOL Access
Point output kun je rechtstreeks gebruiken.

## Setup

```bash
pip install mcp pypdf requests
```

```json
{
  "mcpServers": {
    "ap-automation": {
      "command": "python",
      "args": ["/Users/jij/exact-erp-toolkit/mcp-ap-automation/server.py"],
      "env": { "EXACT_MOCK": "1", "EXACT_VARIANT": "globe" }
    }
  }
}
```

## Typische sessie

```
Jij: Lees ~/Downloads/kpn-mei.pdf en boek 'm als 'ie matcht met PO-2026-118.

Claude (roept extract_invoice_from_pdf):
  Leverancier: KPN Zakelijk, factuur KPN-2026-0500, EUR 413.82, vervalt 31 mei.

Claude (roept match_to_purchase_order):
  Exact reference match op PO-2026-118, delta EUR 0.00.

Claude (roept auto_book_invoice, dry_run=true):
  XML gegenereerd, 6 regels, GL 4500 (Telecom). Zal ik 'm boeken?

Jij: Ja, stuur 'm.

Claude (auto_book_invoice, dry_run=false):
  Geboekt. XML weggeschreven naar /exact/import/purchase_70001_1779138712.xml.
  Exact verwerkt 'm bij de volgende poll (~2 min).
```

## Productie-grade extractie

De meegeleverde `extract_invoice_from_pdf` is een regex-heuristiek —
prima voor schone digitale PDFs, zwak op scans en exotische layouts.
Voor productie: vervang die tool-body door één call naar Claude (vision)
en vraag om gestructureerd JSON. Dat tilt de nauwkeurigheid van ~70%
naar ~98% en handelt scans native af.
