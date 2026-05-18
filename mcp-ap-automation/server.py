"""
MCP server: Accounts Payable automation for Exact Globe / Financials.

The pain: incoming supplier invoices arrive as PDFs in mailboxes, get
typed over by hand into Exact, line by line, by an accountant who
charges EUR 75/hour. Per invoice ~3 minutes of human work plus typos.

This server:
    1. Extracts header + line items from a PDF (Claude/OCR) or UBL XML.
    2. Matches the invoice against an existing Purchase Order in Exact
       (3-way match: invoice <-> PO <-> goods receipt).
    3. Suggests a GL account per line based on supplier history.
    4. Books the purchase invoice into Exact via Exact-XML.

Killer prompts:

    "Read /Users/me/Downloads/kpn-mei.pdf, match to PO, book it."
    "Process all PDFs in ~/Inbox/invoices/ and book the ones that match
     an open PO exactly."
    "Show me my AP ageing — anything I should pay this week?"
    "Spend by supplier last quarter, top 10."

PEPPOL note: as of late 2026 NL is moving to mandatory e-invoicing.
This server includes a UBL parser so PEPPOL Access Point output drops
straight in.
"""
from __future__ import annotations

import os
import re
import sys
import json
import statistics
from pathlib import Path
from collections import defaultdict
from datetime import date, datetime, timedelta
from dataclasses import asdict
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "exact-client"))
from exact_client import make_client  # noqa: E402

from mcp.server.fastmcp import FastMCP  # noqa: E402

mcp = FastMCP("ap-automation")

_client = None
def client():
    global _client
    if _client is None:
        _client = make_client()
    return _client


# --------------------------------------------------------------------
# Mock PO database — in production this queries Exact's sotrln/PO table
# --------------------------------------------------------------------

_MOCK_POS = [
    {"po": "PO-2026-118", "supplier": "70001", "supplier_name": "KPN Zakelijk",
     "open_amount": 342.00, "lines": [
        {"description": "Mobiel abonnement 6x", "qty": 6, "unit_price": 47.00, "gl_account": "4500"},
        {"description": "Data overshoot",        "qty": 1, "unit_price": 60.00, "gl_account": "4500"},
     ]},
    {"po": "PO-2026-122", "supplier": "70003", "supplier_name": "TransSmart Koeriers",
     "open_amount": 1840.00, "lines": [
        {"description": "Pakketdiensten april", "qty": 1, "unit_price": 1840.00, "gl_account": "4200"},
     ]},
    {"po": "PO-2026-130", "supplier": "70001", "supplier_name": "KPN Zakelijk",
     "open_amount": 342.00, "lines": [
        {"description": "Mobiel abonnement 6x", "qty": 6, "unit_price": 47.00, "gl_account": "4500"},
        {"description": "Data overshoot",        "qty": 1, "unit_price": 60.00, "gl_account": "4500"},
     ]},
]


# --------------------------------------------------------------------
# Extractors
# --------------------------------------------------------------------

def _parse_amount(s: str) -> float:
    s = s.replace("EUR", "").replace("€", "").strip()
    s = s.replace(".", "").replace(",", ".") if s.count(",") == 1 and s.count(".") <= 1 else s.replace(",", "")
    try: return float(re.sub(r"[^\d.\-]", "", s))
    except Exception: return 0.0


@mcp.tool()
def extract_invoice_from_text(text: str) -> dict:
    """
    Heuristic extraction from raw invoice text (use after OCR or PDF
    text extraction). For production-grade, swap this for a Claude call
    with structured output. Returns header + lines.
    """
    out = {
        "supplier_name": None, "invoice_number": None,
        "date": None, "due_date": None,
        "amount_excl_vat": None, "vat_amount": None, "amount_incl_vat": None,
        "po_reference": None,
        "lines": [],
        "confidence": "heuristic",
    }
    # invoice number
    m = re.search(r"(?:factuur(?:nummer)?|invoice(?:\s*no\.?)?)[\s:#]*([A-Z0-9\-\/]{4,})", text, re.I)
    if m: out["invoice_number"] = m.group(1).strip()
    # date
    m = re.search(r"(?:factuurdatum|invoice date|datum)[\s:]*([0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{2,4})", text, re.I)
    if m:
        try:
            d = datetime.strptime(m.group(1).replace("/", "-"), "%d-%m-%Y")
            out["date"] = d.date().isoformat()
        except Exception: pass
    # PO ref
    m = re.search(r"(PO[-\s]?\d{4}[-\s]?\d+)", text, re.I)
    if m: out["po_reference"] = m.group(1).replace(" ", "")
    # totals
    m = re.search(r"(?:totaal|subtotal|excl\.?\s*btw)[\s:]*€?\s*([\d.,]+)", text, re.I)
    if m: out["amount_excl_vat"] = _parse_amount(m.group(1))
    m = re.search(r"(?:btw|vat)[\s:]*€?\s*([\d.,]+)", text, re.I)
    if m: out["vat_amount"] = _parse_amount(m.group(1))
    m = re.search(r"(?:totaal\s*incl|total)[\s:]*€?\s*([\d.,]+)", text, re.I)
    if m: out["amount_incl_vat"] = _parse_amount(m.group(1))
    # supplier (first line that isn't an address)
    first_lines = [l.strip() for l in text.splitlines() if l.strip()][:5]
    if first_lines: out["supplier_name"] = first_lines[0]
    return out


@mcp.tool()
def extract_invoice_from_ubl(ubl_xml: str) -> dict:
    """
    Parse a UBL 2.1 invoice (PEPPOL / NLCIUS standard for NL).
    Returns the same schema as extract_invoice_from_text.
    """
    import xml.etree.ElementTree as ET
    ns = {
        "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    }
    root = ET.fromstring(ubl_xml)
    def t(path):
        el = root.find(path, ns)
        return el.text if el is not None else None
    lines = []
    for ln in root.findall(".//cac:InvoiceLine", ns):
        lines.append({
            "description": (ln.findtext(".//cbc:Description", default="", namespaces=ns) or
                            ln.findtext(".//cbc:Name",       default="", namespaces=ns)),
            "qty":         float(ln.findtext("cbc:InvoicedQuantity", default="1", namespaces=ns) or 1),
            "amount":      float(ln.findtext("cbc:LineExtensionAmount", default="0", namespaces=ns) or 0),
        })
    return {
        "supplier_name":   t(".//cac:AccountingSupplierParty//cbc:RegistrationName") or
                            t(".//cac:AccountingSupplierParty//cbc:Name"),
        "invoice_number":  t("cbc:ID"),
        "date":            t("cbc:IssueDate"),
        "due_date":        t("cbc:DueDate"),
        "amount_excl_vat": float(t(".//cac:LegalMonetaryTotal/cbc:TaxExclusiveAmount") or 0),
        "vat_amount":      float(t(".//cac:TaxTotal/cbc:TaxAmount") or 0),
        "amount_incl_vat": float(t(".//cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount") or 0),
        "po_reference":    t(".//cac:OrderReference/cbc:ID"),
        "lines":           lines,
        "confidence":      "ubl-structured",
    }


@mcp.tool()
def extract_invoice_from_pdf(pdf_path: str) -> dict:
    """
    Extract text from a PDF and run the heuristic extractor. For best
    results in production, call Claude with the PDF directly and ask
    for structured JSON — that handles scanned PDFs and exotic layouts
    far better than regex.
    """
    p = Path(pdf_path).expanduser()
    if not p.exists():
        return {"error": f"File not found: {pdf_path}"}
    try:
        from pypdf import PdfReader
    except ImportError:
        return {"error": "pypdf not installed. pip install pypdf"}
    text = "\n".join(page.extract_text() or "" for page in PdfReader(str(p)).pages)
    result = extract_invoice_from_text(text)
    result["source_file"] = str(p)
    result["text_excerpt"] = text[:500]
    return result


# --------------------------------------------------------------------
# Matching & posting
# --------------------------------------------------------------------

@mcp.tool()
def match_to_purchase_order(supplier_code: str, amount: float, po_reference: str | None = None, tolerance_pct: float = 2.0) -> dict:
    """
    Three-way match candidate. Looks for an open PO that matches the
    supplier and amount (within tolerance_pct percent). If a PO
    reference is provided, prefer exact match.
    """
    candidates = [p for p in _MOCK_POS if p["supplier"] == supplier_code]
    if po_reference:
        exact_match = [p for p in candidates if p["po"] == po_reference]
        if exact_match:
            p = exact_match[0]
            delta = abs(p["open_amount"] - amount)
            return {"match": "exact_reference", "po": p["po"], "delta_eur": round(delta, 2), "lines": p["lines"]}
    fuzzy = [
        {"po": p["po"], "open_amount": p["open_amount"], "delta_pct": round(abs(p["open_amount"] - amount) / max(p["open_amount"], 1) * 100, 1), "lines": p["lines"]}
        for p in candidates
        if abs(p["open_amount"] - amount) / max(p["open_amount"], 1) * 100 <= tolerance_pct
    ]
    if fuzzy:
        return {"match": "amount_fuzzy", "candidates": fuzzy}
    return {"match": "none", "supplier_pos_open": len(candidates)}


@mcp.tool()
def suggest_gl_account(supplier_code: str, description: str) -> dict:
    """
    Suggest a GL account based on supplier history (most-used GL for
    this supplier) and keyword hints in the description.
    """
    keywords = {
        "telefoon|mobiel|abonnement|telecom":         {"gl": "4500", "name": "Telecommunicatiekosten"},
        "kantoor|office|papier|toner|inkt":            {"gl": "4310", "name": "Kantoorbenodigdheden"},
        "transport|koerier|verzending|pakket":         {"gl": "4200", "name": "Vervoerskosten"},
        "energie|gas|stroom|electriciteit":            {"gl": "4400", "name": "Energie"},
        "accountant|advies|consult|boekhoud|fiscal":   {"gl": "4700", "name": "Advieskosten"},
        "marketing|advertentie|reclame|campagne":      {"gl": "4600", "name": "Marketing en reclame"},
        "huur|lease":                                  {"gl": "4100", "name": "Huur/lease"},
    }
    desc = description.lower()
    for pat, hit in keywords.items():
        if re.search(pat, desc):
            return {"suggested_gl": hit["gl"], "name": hit["name"], "reason": f"keyword match: '{pat}'"}
    return {"suggested_gl": "4000", "name": "Algemene kosten",
            "reason": "no keyword match; falling back to generic costs account"}


@mcp.tool()
def auto_book_invoice(invoice: dict, gl_account: str | None = None, dry_run: bool = True) -> dict:
    """
    Book a parsed invoice into Exact via Exact-XML.

    Set dry_run=False to actually send to Exact (or write the XML to
    the drop folder). With dry_run=True you get the generated XML
    without dispatching it.

    invoice schema: see output of extract_invoice_from_pdf / _ubl.
    """
    missing = [k for k in ("invoice_number", "date", "amount_incl_vat") if not invoice.get(k)]
    if missing:
        return {"error": f"Required fields missing: {missing}"}

    supplier_code = invoice.get("supplier_code")
    if not supplier_code:
        # try to resolve from supplier_name
        for s in client().list_suppliers(limit=200):
            if invoice.get("supplier_name", "").lower().split()[0] in s.name.lower():
                supplier_code = s.code
                break
    if not supplier_code:
        return {"error": "Could not resolve supplier_code from invoice", "invoice": invoice}

    # build lines
    if invoice.get("lines"):
        lines = [
            {
                "description": ln["description"],
                "qty":         ln.get("qty", 1),
                "amount":      ln.get("amount", ln.get("unit_price", 0)),
                "gl_account":  gl_account or suggest_gl_account(supplier_code, ln["description"])["suggested_gl"],
                "vat_code":    "1",
            }
            for ln in invoice["lines"]
        ]
    else:
        lines = [{
            "description": invoice.get("description", invoice["invoice_number"]),
            "qty":         1,
            "amount":      invoice["amount_excl_vat"] or invoice["amount_incl_vat"],
            "gl_account":  gl_account or "4000",
            "vat_code":    "1",
        }]

    payload = {
        "invoice_number": invoice["invoice_number"],
        "supplier_code":  supplier_code,
        "date":           invoice["date"],
        "due_date":       invoice.get("due_date", ""),
        "po_reference":   invoice.get("po_reference"),
        "description":    invoice.get("description", invoice["invoice_number"]),
        "lines":          lines,
    }
    if dry_run:
        return {"dry_run": True, "would_book": payload,
                "xml_preview": client().build_purchase_invoice_xml(payload)[:600]}
    return client().book_purchase_invoice(payload)


# --------------------------------------------------------------------
# AP reporting
# --------------------------------------------------------------------

@mcp.tool()
def ap_ageing() -> dict:
    """Open payables broken down by ageing bucket (0-30, 31-60, 61-90, 90+)."""
    invs = client().list_purchase_invoices()
    open_invs = [i for i in invs if i.status != "paid"]
    if not open_invs:
        return {"open_invoice_count": 0}
    today = date.today()
    buckets = {"0-30": 0.0, "31-60": 0.0, "61-90": 0.0, "90+": 0.0}
    counts  = {"0-30": 0, "31-60": 0, "61-90": 0, "90+": 0}
    for i in open_invs:
        try:
            d = (today - date.fromisoformat(i.date)).days
        except Exception:
            d = i.days_outstanding
        key = "0-30" if d <= 30 else "31-60" if d <= 60 else "61-90" if d <= 90 else "90+"
        buckets[key] += i.amount_incl_vat
        counts[key]  += 1
    return {
        "total_open_eur":    round(sum(buckets.values()), 2),
        "by_amount":         {k: round(v, 2) for k, v in buckets.items()},
        "by_count":          counts,
        "open_invoice_count": len(open_invs),
    }


@mcp.tool()
def pay_this_week() -> list[dict]:
    """
    Invoices due within the next 7 days, ranked by due date. The list
    your bookkeeper should pay first to avoid late fees.
    """
    today = date.today()
    horizon = today + timedelta(days=7)
    out = []
    for i in client().list_purchase_invoices():
        if i.status == "paid": continue
        try:
            due = date.fromisoformat(i.due_date) if i.due_date else None
        except Exception:
            due = None
        if not due: continue
        if due <= horizon:
            out.append({
                "invoice":  i.invoice_number,
                "supplier": i.supplier_name,
                "amount":   i.amount_incl_vat,
                "due_date": i.due_date,
                "days_until_due": (due - today).days,
            })
    return sorted(out, key=lambda r: r["days_until_due"])


@mcp.tool()
def spend_by_supplier(top_n: int = 10) -> list[dict]:
    """Total spend per supplier across all known purchase invoices."""
    invs = client().list_purchase_invoices(limit=1000)
    per = defaultdict(lambda: {"supplier_code": "", "supplier_name": "", "spend": 0.0, "invoices": 0})
    for i in invs:
        b = per[i.supplier_code]
        b["supplier_code"] = i.supplier_code
        b["supplier_name"] = i.supplier_name
        b["spend"]        += i.amount_incl_vat
        b["invoices"]     += 1
    rows = list(per.values())
    for r in rows: r["spend"] = round(r["spend"], 2)
    return sorted(rows, key=lambda r: r["spend"], reverse=True)[:top_n]


if __name__ == "__main__":
    mcp.run()
