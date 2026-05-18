"""
Demo. Runs in mock mode out of the box.

    python example_demo.py

For real Globe / Financials access:
    export EXACT_MOCK=0
    export EXACT_VARIANT=globe              # or 'financials'
    export EXACT_ODBC='DRIVER={ODBC Driver 18 for SQL Server};SERVER=...;DATABASE=...;UID=...;PWD=...'
    export EXACT_XML_DROP_FOLDER=/path/to/exact/xml/import
"""
from __future__ import annotations
import os
from exact_client import make_client

os.environ.setdefault("EXACT_MOCK", "1")
os.environ.setdefault("EXACT_VARIANT", "globe")  # try also 'financials'

print(f"Variant: {os.environ['EXACT_VARIANT']}  |  Mock: {os.environ['EXACT_MOCK']}\n")
c = make_client()

print("== Customers (read via SQL) ==")
for cust in c.list_customers(limit=5):
    print(f"  {cust.code:<7} {cust.name:<40} {cust.email}")

print("\n== Suppliers (read via SQL) ==")
for sup in c.list_suppliers(limit=5):
    print(f"  {sup.code:<7} {sup.name:<32} {sup.iban}")

print("\n== Open AR invoices (30+ days overdue) ==")
for inv in c.list_invoices(min_days_overdue=30):
    print(f"  {inv.invoice_number}  {inv.customer_name:<35} "
          f"EUR {inv.amount_incl_vat:>10,.2f}  {inv.days_overdue}d overdue")

print("\n== Open AP invoices (supplier payables) ==")
for pi in c.list_purchase_invoices():
    flag = "!" if pi.status == "overdue" else " "
    print(f" {flag} {pi.invoice_number:<14} {pi.supplier_name:<26} "
          f"EUR {pi.amount_incl_vat:>9,.2f}  due {pi.due_date}  "
          f"PO={pi.po_reference or '-'}")

print("\n== Financial summary ==")
s = c.get_financial_summary()
print(f"  Period           {s.period}")
print(f"  Revenue          EUR {s.revenue:>12,.2f}")
print(f"  Costs            EUR {s.costs:>12,.2f}")
print(f"  Gross margin     EUR {s.gross_margin:>12,.2f}")
print(f"  Receivables open EUR {s.open_receivables:>12,.2f}")
print(f"  Payables open    EUR {s.open_payables:>12,.2f}")
print(f"  Cash position    EUR {s.cash_position:>12,.2f}")

print("\n== Create sales invoice via Exact-XML ==")
r = c.create_sales_invoice({
    "customer_code": "60002",
    "description":   "Consultancy uren mei",
    "lines": [
        {"description": "Senior consult", "qty": 8, "unit_price": 145.00},
        {"description": "Travel",         "qty": 1, "unit_price":  85.00},
    ],
})
print(f"  transport={r['transport']}  filename={r.get('filename', r.get('path'))}  bytes={r['bytes']}")
print(f"  (first 200 chars of XML:)\n  {r['xml'][:200]}...")

print("\n== Book purchase invoice via Exact-XML ==")
r = c.book_purchase_invoice({
    "invoice_number": "KPN-2026-0500",
    "supplier_code":  "70001",
    "date":           "2026-05-17",
    "due_date":       "2026-05-31",
    "po_reference":   "PO-2026-130",
    "description":    "KPN zakelijk mobiel mei",
    "lines": [
        {"description": "Mobiel abonnement 6x",  "qty": 6, "amount": 282.00, "gl_account": "4500", "vat_code": "1"},
        {"description": "Data overshoot",        "qty": 1, "amount":  60.00, "gl_account": "4500", "vat_code": "1"},
    ],
})
print(f"  transport={r['transport']}  bytes={r['bytes']}")
