"""
Demo. Draait in mock mode out of the box.

    python example_demo.py

Voor echte Globe / Financials toegang:
    export EXACT_MOCK=0
    export EXACT_VARIANT=globe              # of 'financials'
    export EXACT_ODBC='DRIVER={ODBC Driver 18 for SQL Server};SERVER=...;DATABASE=...;UID=...;PWD=...'
    export EXACT_XML_DROP_FOLDER=/pad/naar/exact/xml/import
"""
from __future__ import annotations
import os
from exact_client import make_client

os.environ.setdefault("EXACT_MOCK", "1")
os.environ.setdefault("EXACT_VARIANT", "globe")  # probeer ook 'financials'

print(f"Variant: {os.environ['EXACT_VARIANT']}  |  Mock: {os.environ['EXACT_MOCK']}\n")
c = make_client()

print("== Klanten (gelezen via SQL) ==")
for cust in c.list_customers(limit=5):
    print(f"  {cust.code:<7} {cust.name:<40} {cust.email}")

print("\n== Leveranciers (gelezen via SQL) ==")
for sup in c.list_suppliers(limit=5):
    print(f"  {sup.code:<7} {sup.name:<32} {sup.iban}")

print("\n== Openstaande verkoopfacturen (30+ dagen overdue) ==")
for inv in c.list_invoices(min_days_overdue=30):
    print(f"  {inv.invoice_number}  {inv.customer_name:<35} "
          f"EUR {inv.amount_incl_vat:>10,.2f}  {inv.days_overdue}d overdue")

print("\n== Openstaande inkoopfacturen (crediteuren) ==")
for pi in c.list_purchase_invoices():
    flag = "!" if pi.status == "overdue" else " "
    print(f" {flag} {pi.invoice_number:<14} {pi.supplier_name:<26} "
          f"EUR {pi.amount_incl_vat:>9,.2f}  vervalt {pi.due_date}  "
          f"PO={pi.po_reference or '-'}")

print("\n== Financiële samenvatting ==")
s = c.get_financial_summary()
print(f"  Periode          {s.period}")
print(f"  Omzet            EUR {s.revenue:>12,.2f}")
print(f"  Kosten           EUR {s.costs:>12,.2f}")
print(f"  Bruto marge      EUR {s.gross_margin:>12,.2f}")
print(f"  Debiteuren open  EUR {s.open_receivables:>12,.2f}")
print(f"  Crediteuren open EUR {s.open_payables:>12,.2f}")
print(f"  Kaspositie       EUR {s.cash_position:>12,.2f}")

print("\n== Verkoopfactuur aanmaken via Exact-XML ==")
r = c.create_sales_invoice({
    "customer_code": "60002",
    "description":   "Consultancy uren mei",
    "lines": [
        {"description": "Senior consult", "qty": 8, "unit_price": 145.00},
        {"description": "Reiskosten",     "qty": 1, "unit_price":  85.00},
    ],
})
print(f"  transport={r['transport']}  filename={r.get('filename', r.get('path'))}  bytes={r['bytes']}")
print(f"  (eerste 200 chars van XML:)\n  {r['xml'][:200]}...")

print("\n== Inkoopfactuur boeken via Exact-XML ==")
r = c.book_purchase_invoice({
    "invoice_number": "KPN-2026-0500",
    "supplier_code":  "70001",
    "date":           "2026-05-17",
    "due_date":       "2026-05-31",
    "po_reference":   "PO-2026-130",
    "description":    "KPN zakelijk mobiel mei",
    "lines": [
        {"description": "Mobiel abonnement 6x",  "qty": 6, "amount": 282.00, "gl_account": "4500", "vat_code": "1"},
        {"description": "Data overschrijding",   "qty": 1, "amount":  60.00, "gl_account": "4500", "vat_code": "1"},
    ],
})
print(f"  transport={r['transport']}  bytes={r['bytes']}")
