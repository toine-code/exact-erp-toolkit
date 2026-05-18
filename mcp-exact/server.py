"""
MCP server: Exact ERP (Globe + Financials).

Exposes the on-prem Exact products to any MCP host as natural-language
tools. Reads via direct SQL Server, writes via Exact-XML.

Register in Claude Desktop:
    {
      "mcpServers": {
        "exact": {
          "command": "python",
          "args": ["/abs/path/to/mcp-exact/server.py"],
          "env": { "EXACT_MOCK": "1", "EXACT_VARIANT": "globe" }
        }
      }
    }
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from dataclasses import asdict

# allow `from exact_client import ...` when this folder sits next to exact-client/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "exact-client"))

from exact_client import make_client  # noqa: E402

from mcp.server.fastmcp import FastMCP  # noqa: E402

mcp = FastMCP("exact")

_client = None
def client():
    global _client
    if _client is None:
        _client = make_client()
    return _client


# ---------------- read tools ----------------

@mcp.tool()
def list_customers(limit: int = 25) -> list[dict]:
    """List customers from Exact. Returns code, name, email, phone, country, credit_limit."""
    return [asdict(c) for c in client().list_customers(limit=limit)]


@mcp.tool()
def get_customer(code: str) -> dict | None:
    """Get one customer by Exact customer code (e.g. '60001')."""
    c = client().get_customer(code)
    return asdict(c) if c else None


@mcp.tool()
def list_open_invoices(min_days_overdue: int = 0, customer_code: str | None = None, limit: int = 100) -> list[dict]:
    """
    List open (unpaid) invoices. Filter by overdue days or customer code.
    min_days_overdue=30 -> only invoices 30+ days past due.
    """
    invs = client().list_invoices(
        status=None, min_days_overdue=min_days_overdue,
        customer_code=customer_code, limit=limit,
    )
    return [asdict(i) for i in invs if i.status != "paid"]


@mcp.tool()
def get_financial_summary(period: str | None = None) -> dict:
    """
    Get revenue, costs, gross margin, receivables, payables, cash for a period.
    period format 'YYYY-MM'. Defaults to current month.
    """
    return asdict(client().get_financial_summary(period=period))


@mcp.tool()
def overdue_total() -> dict:
    """Total amount and count of overdue invoices, plus the worst offender."""
    invs = client().list_invoices(min_days_overdue=1)
    if not invs:
        return {"count": 0, "total_eur": 0.0, "worst": None}
    total = sum(i.amount_incl_vat for i in invs)
    worst = max(invs, key=lambda i: i.days_overdue)
    return {
        "count":   len(invs),
        "total_eur": round(total, 2),
        "worst": {
            "invoice": worst.invoice_number,
            "customer": worst.customer_name,
            "amount":   worst.amount_incl_vat,
            "days_overdue": worst.days_overdue,
        },
    }


@mcp.tool()
def list_suppliers(limit: int = 25) -> list[dict]:
    """List suppliers (creditors) from Exact."""
    return [asdict(s) for s in client().list_suppliers(limit=limit)]


@mcp.tool()
def list_purchase_invoices(min_days_outstanding: int = 0, supplier_code: str | None = None, limit: int = 100) -> list[dict]:
    """List open purchase (supplier) invoices — the AP/payables side."""
    invs = client().list_purchase_invoices(
        min_days_outstanding=min_days_outstanding,
        supplier_code=supplier_code, limit=limit,
    )
    return [asdict(i) for i in invs if i.status != "paid"]


# ---------------- write tools (via Exact-XML) ----------------

@mcp.tool()
def create_sales_invoice(
    customer_code: str,
    description: str,
    lines: list[dict],
) -> dict:
    """
    Create a sales invoice in Exact.

    lines example:
        [
          {"description": "Consultancy", "qty": 8, "unit_price": 145, "vat_code": "1"},
          {"description": "Travel",      "qty": 1, "unit_price":  85, "vat_code": "1"}
        ]
    """
    return client().create_sales_invoice({
        "customer_code": customer_code,
        "description":   description,
        "lines":         lines,
    })


@mcp.tool()
def book_purchase_invoice(
    invoice_number: str,
    supplier_code:  str,
    date:           str,
    due_date:       str,
    lines:          list[dict],
    po_reference:   str | None = None,
    description:    str | None = None,
) -> dict:
    """
    Book an incoming supplier invoice via Exact-XML.

    lines example:
        [{"description": "Mobile plans 6x", "qty": 6, "amount": 282.00,
          "gl_account": "4500", "vat_code": "1"}]
    """
    return client().book_purchase_invoice({
        "invoice_number": invoice_number,
        "supplier_code":  supplier_code,
        "date":           date,
        "due_date":       due_date,
        "po_reference":   po_reference,
        "description":    description or invoice_number,
        "lines":          lines,
    })


# ---------------- main ----------------

if __name__ == "__main__":
    mcp.run()
