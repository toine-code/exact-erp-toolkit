"""
Exact ERP on-prem Python client.

Targets Exact's old-school products that DON'T have a public REST API:

    - ExactGlobeClient       -> Exact Globe (Windows + MS SQL Server)
    - ExactFinancialsClient  -> Exact Financials (on-prem accounting)

Both clients use:
    - direct MS SQL Server access for reads (via pyodbc / ODBC),
    - Exact-XML (published XSD schema) for writes.

This is exactly how the proprietary middleware platforms work under the
hood. There is no proprietary API — there is a SQL Server and an XML
import folder. With credentials, anyone can speak to it.

Mock mode is built in. Set EXACT_MOCK=1 (or pass mock=True) and you get
deterministic fake data so the MCP servers and the demos work without
an Exact installation.
"""

from __future__ import annotations

import os
import time
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Any

log = logging.getLogger("exact_client")


# ---------------------------------------------------------------------------
# Shared data model
# ---------------------------------------------------------------------------

@dataclass
class Customer:
    code: str
    name: str
    email: str | None = None
    phone: str | None = None
    country: str = "NL"
    vat_number: str | None = None
    credit_limit: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Supplier:
    code: str
    name: str
    email: str | None = None
    vat_number: str | None = None
    iban: str | None = None
    payment_terms_days: int = 30


@dataclass
class Invoice:
    invoice_number: str
    customer_code: str
    customer_name: str
    date: str
    due_date: str
    amount_excl_vat: float
    amount_incl_vat: float
    status: str            # 'open' | 'paid' | 'overdue'
    days_overdue: int = 0
    lines: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class PurchaseInvoice:
    """Incoming supplier invoice (creditor side)."""
    invoice_number: str
    supplier_code: str
    supplier_name: str
    date: str
    due_date: str
    amount_excl_vat: float
    amount_incl_vat: float
    vat_amount: float
    status: str            # 'open' | 'paid' | 'overdue'
    days_outstanding: int = 0
    lines: list[dict[str, Any]] = field(default_factory=list)
    po_reference: str | None = None


@dataclass
class FinancialSummary:
    period: str
    revenue: float
    costs: float
    gross_margin: float
    open_receivables: float
    open_payables: float
    cash_position: float


# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

_MOCK_CUSTOMERS = [
    Customer("60001", "Bakker Bouwmaterialen B.V.", "info@bakkerbouw.nl",  "+31 50 1234567", "NL", "NL001234567B01", 25000),
    Customer("60002", "De Vries Logistiek",          "p.devries@vrieslog.nl", "+31 20 7654321", "NL", "NL009876543B01", 50000),
    Customer("60003", "Janssen Installatietechniek", "office@janssenit.nl",   "+31 40 5550100", "NL", "NL004567890B01", 15000),
    Customer("60004", "Pietersen Groothandel",       "verkoop@pietersen.nl",  "+31 70 9988776", "NL", "NL007788990B01", 100000),
    Customer("60005", "Tjellens Personeelsdiensten", "info@tjellens.nl",      "+31 50 3030300", "NL", "NL006677889B01", 75000),
]

_MOCK_SUPPLIERS = [
    Supplier("70001", "KPN Zakelijk",               "facturen@kpn.com",       "NL001212121B01", "NL11RABO0123456789", 14),
    Supplier("70002", "Office Centre",              "ar@officecentre.nl",     "NL003434343B01", "NL22INGB0987654321", 30),
    Supplier("70003", "TransSmart Koeriers",        "billing@transsmart.nl",  "NL005656565B01", "NL33ABNA0456789012", 30),
    Supplier("70004", "Energiedirect",              "rekening@energiedirect.nl","NL007878787B01", "NL44BUNQ0123450000", 30),
    Supplier("70005", "Boomgaard Accountants",      "facturen@boomgaard.nl",  "NL009090909B01", "NL55KNAB0111222333", 14),
]

def _mock_invoices() -> list[Invoice]:
    t = date.today()
    return [
        Invoice("F2026-0001", "60001", "Bakker Bouwmaterialen B.V.",
                (t - timedelta(days=45)).isoformat(),
                (t - timedelta(days=15)).isoformat(),
                4200.00, 5082.00, "overdue", 15),
        Invoice("F2026-0002", "60002", "De Vries Logistiek",
                (t - timedelta(days=20)).isoformat(),
                (t + timedelta(days=10)).isoformat(),
                12500.00, 15125.00, "open", 0),
        Invoice("F2026-0003", "60003", "Janssen Installatietechniek",
                (t - timedelta(days=75)).isoformat(),
                (t - timedelta(days=45)).isoformat(),
                800.00, 968.00, "overdue", 45),
        Invoice("F2026-0004", "60004", "Pietersen Groothandel",
                (t - timedelta(days=5)).isoformat(),
                (t + timedelta(days=25)).isoformat(),
                34000.00, 41140.00, "open", 0),
        Invoice("F2026-0005", "60005", "Tjellens Personeelsdiensten",
                (t - timedelta(days=120)).isoformat(),
                (t - timedelta(days=90)).isoformat(),
                2200.00, 2662.00, "overdue", 90),
        Invoice("F2026-0006", "60001", "Bakker Bouwmaterialen B.V.",
                (t - timedelta(days=10)).isoformat(),
                (t + timedelta(days=20)).isoformat(),
                1800.00, 2178.00, "open", 0),
    ]

def _mock_purchase_invoices() -> list[PurchaseInvoice]:
    t = date.today()
    return [
        PurchaseInvoice("KPN-2026-0451", "70001", "KPN Zakelijk",
                        (t - timedelta(days=8)).isoformat(),
                        (t + timedelta(days=6)).isoformat(),
                        342.00, 413.82, 71.82, "open", 8,
                        po_reference="PO-2026-118"),
        PurchaseInvoice("OC-99812",      "70002", "Office Centre",
                        (t - timedelta(days=22)).isoformat(),
                        (t + timedelta(days=8)).isoformat(),
                        128.50, 155.49, 26.99, "open", 22),
        PurchaseInvoice("TS-26-0772",    "70003", "TransSmart Koeriers",
                        (t - timedelta(days=35)).isoformat(),
                        (t - timedelta(days=5)).isoformat(),
                        1840.00, 2226.40, 386.40, "overdue", 35,
                        po_reference="PO-2026-122"),
        PurchaseInvoice("ED-2604-NL",    "70004", "Energiedirect",
                        (t - timedelta(days=3)).isoformat(),
                        (t + timedelta(days=27)).isoformat(),
                        2750.00, 3327.50, 577.50, "open", 3),
        PurchaseInvoice("BG-2026-Q1",    "70005", "Boomgaard Accountants",
                        (t - timedelta(days=18)).isoformat(),
                        (t - timedelta(days=4)).isoformat(),
                        4500.00, 5445.00, 945.00, "overdue", 18),
    ]

def _mock_summary() -> FinancialSummary:
    return FinancialSummary(
        period=datetime.now().strftime("%Y-%m"),
        revenue=185_400.00, costs=121_300.00, gross_margin=64_100.00,
        open_receivables=67_155.00, open_payables=28_900.00, cash_position=142_300.00,
    )


# ---------------------------------------------------------------------------
# Base for on-prem (Globe + Financials)
# ---------------------------------------------------------------------------

class _ExactOnPremBase:
    """
    Shared logic for Globe and Financials.

    Reads happen via direct ODBC against the MS SQL Server hosting the
    administration. Writes happen via Exact-XML (drop folder or
    webservice). Both products use the same XSD with slightly different
    namespaces, so subclasses only override what differs.
    """

    # Subclasses override these
    PRODUCT      = "globe"          # or 'financials'
    SCHEMA       = {                 # table names per product
        "customers":  "Accountants",
        "suppliers":  "Accountants",
        "ar":         "bptran",
        "ap":         "bptran",
        "ar_account": "1300",
        "ap_account": "1600",
    }

    def __init__(
        self,
        connection_string: str | None = None,
        administration: str | None = None,
        drop_folder: str | Path | None = None,
        webservice_url: str | None = None,
        webservice_user: str | None = None,
        webservice_pass: str | None = None,
        mock: bool | None = None,
    ):
        if mock is None:
            mock = os.environ.get("EXACT_MOCK", "0") == "1"
        self.mock = mock
        self.connection_string = connection_string or os.environ.get("EXACT_ODBC")
        self.administration    = administration or os.environ.get("EXACT_ADMIN", "001")
        self.drop_folder       = Path(drop_folder)   if drop_folder   else (Path(os.environ["EXACT_XML_DROP_FOLDER"]) if os.environ.get("EXACT_XML_DROP_FOLDER") else None)
        self.webservice_url    = webservice_url    or os.environ.get("EXACT_XML_WEBSERVICE_URL")
        self.webservice_user   = webservice_user   or os.environ.get("EXACT_XML_USERNAME")
        self.webservice_pass   = webservice_pass   or os.environ.get("EXACT_XML_PASSWORD")

        if not self.mock and not self.connection_string:
            log.warning("%s ODBC not configured; mock mode enabled.", self.PRODUCT)
            self.mock = True

    # ---- low-level SQL ----
    def _conn(self):
        import pyodbc
        return pyodbc.connect(self.connection_string)

    def _q(self, sql: str, *params) -> list[Any]:
        with self._conn() as cn:
            return list(cn.execute(sql, *params).fetchall())

    # ---- reads ----
    def list_customers(self, limit: int = 50) -> list[Customer]:
        if self.mock:
            return _MOCK_CUSTOMERS[:limit]
        sql = f"""
            SELECT TOP {int(limit)}
                ltrim(rtrim(DebtorCode)) code, Name, EMail, Phone,
                CountryCode, VATNumber, CreditLine
            FROM {self.SCHEMA['customers']}
            WHERE IsCustomer = 1
            ORDER BY Name
        """
        return [Customer(
            code=r.code, name=r.Name, email=r.EMail, phone=r.Phone,
            country=(r.CountryCode or "NL"), vat_number=r.VATNumber,
            credit_limit=float(r.CreditLine or 0),
        ) for r in self._q(sql)]

    def get_customer(self, code: str) -> Customer | None:
        if self.mock:
            return next((c for c in _MOCK_CUSTOMERS if c.code == code), None)
        rows = self._q(
            f"SELECT * FROM {self.SCHEMA['customers']} WHERE DebtorCode = ? AND IsCustomer = 1",
            code,
        )
        if not rows: return None
        r = rows[0]
        return Customer(code=r.DebtorCode.strip(), name=r.Name,
                        email=r.EMail, phone=r.Phone,
                        country=(r.CountryCode or "NL"),
                        vat_number=r.VATNumber,
                        credit_limit=float(getattr(r, "CreditLine", 0) or 0))

    def list_suppliers(self, limit: int = 50) -> list[Supplier]:
        if self.mock:
            return _MOCK_SUPPLIERS[:limit]
        sql = f"""
            SELECT TOP {int(limit)}
                ltrim(rtrim(CreditorCode)) code, Name, EMail,
                VATNumber, BankAccount, PaymentTerms
            FROM {self.SCHEMA['suppliers']}
            WHERE IsCreditor = 1
        """
        return [Supplier(
            code=r.code, name=r.Name, email=r.EMail,
            vat_number=r.VATNumber, iban=r.BankAccount,
            payment_terms_days=int(r.PaymentTerms or 30),
        ) for r in self._q(sql)]

    def list_invoices(self, status=None, min_days_overdue=0,
                      customer_code=None, limit=100) -> list[Invoice]:
        if self.mock:
            data = _mock_invoices()
            if status:        data = [i for i in data if i.status == status]
            if min_days_overdue: data = [i for i in data if i.days_overdue >= min_days_overdue]
            if customer_code: data = [i for i in data if i.customer_code == customer_code]
            return data[:limit]
        sql = f"""
            SELECT TOP {int(limit)}
                t.OurRef, t.DebtorCode, d.Name AS customer_name,
                t.Date, t.DueDate, t.AmountDC, t.AmountFC
            FROM {self.SCHEMA['ar']} t
            LEFT JOIN {self.SCHEMA['customers']} d ON d.DebtorCode = t.DebtorCode
            WHERE t.GLAccount = ? AND t.MatchStatus = 0
            {"AND t.DebtorCode = ?" if customer_code else ""}
            ORDER BY t.DueDate ASC
        """
        params = [self.SCHEMA["ar_account"]]
        if customer_code: params.append(customer_code)
        out, t = [], date.today()
        for r in self._q(sql, *params):
            due = r.DueDate.date() if hasattr(r.DueDate, "date") else r.DueDate
            days = (t - due).days if due else 0
            inv_status = "overdue" if days > 0 else "open"
            if status and inv_status != status: continue
            if days < min_days_overdue: continue
            out.append(Invoice(
                invoice_number=str(r.OurRef).strip(),
                customer_code=r.DebtorCode.strip(),
                customer_name=r.customer_name or "",
                date=str(r.Date)[:10], due_date=str(due),
                amount_excl_vat=float(r.AmountDC or 0),
                amount_incl_vat=float(r.AmountFC or 0),
                status=inv_status, days_overdue=max(days, 0),
            ))
        return out

    def list_purchase_invoices(self, status=None, min_days_outstanding=0,
                               supplier_code=None, limit=100) -> list[PurchaseInvoice]:
        if self.mock:
            data = _mock_purchase_invoices()
            if status:        data = [i for i in data if i.status == status]
            if min_days_outstanding: data = [i for i in data if i.days_outstanding >= min_days_outstanding]
            if supplier_code: data = [i for i in data if i.supplier_code == supplier_code]
            return data[:limit]
        sql = f"""
            SELECT TOP {int(limit)}
                t.OurRef, t.CreditorCode, c.Name AS supplier_name,
                t.Date, t.DueDate, t.AmountDC, t.AmountFC, t.VATAmountDC,
                t.PurchaseOrderRef
            FROM {self.SCHEMA['ap']} t
            LEFT JOIN {self.SCHEMA['suppliers']} c ON c.CreditorCode = t.CreditorCode
            WHERE t.GLAccount = ? AND t.MatchStatus = 0
            {"AND t.CreditorCode = ?" if supplier_code else ""}
            ORDER BY t.DueDate ASC
        """
        params = [self.SCHEMA["ap_account"]]
        if supplier_code: params.append(supplier_code)
        out, t = [], date.today()
        for r in self._q(sql, *params):
            doc_date = r.Date.date() if hasattr(r.Date, "date") else r.Date
            due      = r.DueDate.date() if hasattr(r.DueDate, "date") else r.DueDate
            days_out = (t - doc_date).days if doc_date else 0
            inv_status = "overdue" if due and t > due else "open"
            if status and inv_status != status: continue
            if days_out < min_days_outstanding: continue
            out.append(PurchaseInvoice(
                invoice_number=str(r.OurRef).strip(),
                supplier_code=r.CreditorCode.strip(),
                supplier_name=r.supplier_name or "",
                date=str(doc_date), due_date=str(due) if due else "",
                amount_excl_vat=float(r.AmountDC or 0) - float(r.VATAmountDC or 0),
                amount_incl_vat=float(r.AmountDC or 0),
                vat_amount=float(r.VATAmountDC or 0),
                status=inv_status, days_outstanding=max(days_out, 0),
                po_reference=r.PurchaseOrderRef,
            ))
        return out

    def get_financial_summary(self, period: str | None = None) -> FinancialSummary:
        if self.mock: return _mock_summary()
        period = period or datetime.now().strftime("%Y-%m")
        year, month = period.split("-")
        row = self._q("""
            SELECT
                SUM(CASE WHEN GLAccountClass = 'REV' THEN -AmountDC ELSE 0 END) AS revenue,
                SUM(CASE WHEN GLAccountClass = 'COG' THEN  AmountDC ELSE 0 END) AS costs,
                SUM(CASE WHEN GLAccountClass = 'AR'  AND MatchStatus = 0 THEN AmountDC ELSE 0 END) AS ar,
                SUM(CASE WHEN GLAccountClass = 'AP'  AND MatchStatus = 0 THEN AmountDC ELSE 0 END) AS ap,
                SUM(CASE WHEN GLAccountClass = 'CASH' THEN AmountDC ELSE 0 END) AS cash
            FROM bptran
            WHERE YEAR(Date) = ? AND MONTH(Date) = ?
        """, int(year), int(month))
        r = row[0] if row else None
        return FinancialSummary(
            period=period,
            revenue=float(r.revenue or 0) if r else 0.0,
            costs=float(r.costs or 0) if r else 0.0,
            gross_margin=float((r.revenue or 0) - (r.costs or 0)) if r else 0.0,
            open_receivables=float(r.ar or 0) if r else 0.0,
            open_payables=float(r.ap or 0) if r else 0.0,
            cash_position=float(r.cash or 0) if r else 0.0,
        )

    # ---- writes via Exact-XML ----
    @staticmethod
    def _xml_escape(s: Any) -> str:
        return (str(s or "")
                .replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))

    def _xml_root_open(self) -> str:
        """Subclasses can override schema location."""
        return ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<eExact xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                'xsi:noNamespaceSchemaLocation="eExact-Schema.xsd">')

    def build_sales_invoice_xml(self, payload: dict) -> str:
        e = self._xml_escape
        lines = "\n".join(
            f"""      <SalesInvoiceLine line="{i+1}">
        <Description>{e(l['description'])}</Description>
        <Quantity>{l['qty']}</Quantity>
        <PriceFC>{l['unit_price']}</PriceFC>
        <VATCode code="{e(l.get('vat_code','1'))}"/>
      </SalesInvoiceLine>"""
            for i, l in enumerate(payload["lines"])
        )
        return f"""{self._xml_root_open()}
  <SalesInvoices>
    <SalesInvoice>
      <InvoiceTo><Debtor code="{e(payload['customer_code'])}"/></InvoiceTo>
      <Description>{e(payload.get('description','API generated'))}</Description>
      <SalesInvoiceLines>
{lines}
      </SalesInvoiceLines>
    </SalesInvoice>
  </SalesInvoices>
</eExact>"""

    def build_purchase_invoice_xml(self, p: dict) -> str:
        e = self._xml_escape
        lines = "\n".join(
            f"""      <PurchaseInvoiceLine line="{i+1}">
        <Description>{e(l['description'])}</Description>
        <Quantity>{l.get('qty', 1)}</Quantity>
        <AmountFC>{l['amount']}</AmountFC>
        <GLAccount code="{e(l.get('gl_account','4000'))}"/>
        <VATCode code="{e(l.get('vat_code','1'))}"/>
      </PurchaseInvoiceLine>"""
            for i, l in enumerate(p["lines"])
        )
        return f"""{self._xml_root_open()}
  <PurchaseInvoices>
    <PurchaseInvoice>
      <SupplierInvoiceNumber>{e(p['invoice_number'])}</SupplierInvoiceNumber>
      <InvoiceFrom><Creditor code="{e(p['supplier_code'])}"/></InvoiceFrom>
      <Date>{e(p['date'])}</Date>
      <DueDate>{e(p.get('due_date',''))}</DueDate>
      <YourRef>{e(p.get('po_reference',''))}</YourRef>
      <Description>{e(p.get('description', p['invoice_number']))}</Description>
      <PurchaseInvoiceLines>
{lines}
      </PurchaseInvoiceLines>
    </PurchaseInvoice>
  </PurchaseInvoices>
</eExact>"""

    def _send_xml(self, xml: str, filename: str) -> dict:
        if self.mock:
            return {"transport": "mock", "filename": filename, "xml": xml, "bytes": len(xml)}
        if self.drop_folder:
            target = self.drop_folder / filename
            target.write_text(xml, encoding="utf-8")
            return {"transport": "folder", "path": str(target), "bytes": len(xml)}
        if self.webservice_url:
            import requests
            r = requests.post(
                self.webservice_url, data=xml.encode("utf-8"),
                auth=(self.webservice_user, self.webservice_pass) if self.webservice_user else None,
                headers={"Content-Type": "application/xml"}, timeout=60,
            )
            r.raise_for_status()
            return {"transport": "webservice", "status": r.status_code, "response": r.text[:500]}
        raise RuntimeError("No XML transport configured (drop_folder or webservice_url).")

    def create_sales_invoice(self, payload: dict) -> dict:
        xml = self.build_sales_invoice_xml(payload)
        return self._send_xml(xml, f"sales_{payload['customer_code']}_{int(time.time())}.xml")

    def book_purchase_invoice(self, payload: dict) -> dict:
        xml = self.build_purchase_invoice_xml(payload)
        return self._send_xml(xml, f"purchase_{payload['supplier_code']}_{int(time.time())}.xml")


# ---------------------------------------------------------------------------
# Exact Globe — Windows ERP, MS SQL backend
# ---------------------------------------------------------------------------

class ExactGlobeClient(_ExactOnPremBase):
    """
    Exact Globe. Per-administration MS SQL database. Common tables:

        Accountants   relations (customer + supplier merged via IsCustomer/IsCreditor)
        bptran        bookkeeping transactions (AR/AP open items live here)
        cicmpy        company / administration
        sotran        sales orders header
        sotrln        sales order lines

    Schema varies slightly between Globe versions (2003 vs Globe Next).
    Override SCHEMA on subclass if a customer's install uses different
    table names.
    """
    PRODUCT = "globe"
    SCHEMA  = {
        "customers":  "Accountants",
        "suppliers":  "Accountants",
        "ar":         "bptran",
        "ap":         "bptran",
        "ar_account": "1300",
        "ap_account": "1600",
    }


# ---------------------------------------------------------------------------
# Exact Financials — pure accounting, on-prem
# ---------------------------------------------------------------------------

class ExactFinancialsClient(_ExactOnPremBase):
    """
    Exact Financials Enterprise / Premium. Pure accounting product, on-prem
    SQL Server. Tables differ from Globe — typically prefixed and split
    customer/supplier into separate tables.

    Common schema (varies by version):
        DebtorFinancials   customer master
        CreditorFinancials supplier master
        FinTrans           transactions
    """
    PRODUCT = "financials"
    SCHEMA  = {
        "customers":  "DebtorFinancials",
        "suppliers":  "CreditorFinancials",
        "ar":         "FinTrans",
        "ap":         "FinTrans",
        "ar_account": "1300",
        "ap_account": "1600",
    }


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def make_client(variant: str = "auto", **kwargs) -> _ExactOnPremBase:
    """
    variant:
        'globe'      -> ExactGlobeClient
        'financials' -> ExactFinancialsClient
        'auto'       -> EXACT_VARIANT env, default 'globe'
    """
    if variant == "auto":
        variant = os.environ.get("EXACT_VARIANT", "globe")
    if variant == "globe":      return ExactGlobeClient(**kwargs)
    if variant == "financials": return ExactFinancialsClient(**kwargs)
    raise ValueError(f"Unknown variant: {variant} (expected 'globe' or 'financials')")


__all__ = [
    "Customer", "Supplier", "Invoice", "PurchaseInvoice", "FinancialSummary",
    "ExactGlobeClient", "ExactFinancialsClient",
    "make_client",
]
