"""
MCP server: HubSpot <-> Exact bridge.

The actual gap most MKB suffers from: sales (HubSpot) doesn't know what
finance (Exact) sees, and vice versa. This server stitches them together
on the fly via natural-language tool calls.

Killer prompts:

    "Which won deals from last quarter haven't been invoiced yet?"
    "For HubSpot company 'Bakker Bouwmaterialen', what's their Exact AR?"
    "Show me the top 10 HubSpot customers by Exact revenue this year."
    "Flag every HubSpot deal where the contact's Exact account is on
     credit hold or >60 days overdue."
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from dataclasses import asdict
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "exact-client"))
from exact_client import make_client  # noqa: E402

from mcp.server.fastmcp import FastMCP  # noqa: E402

mcp = FastMCP("hubspot-exact-bridge")

HUBSPOT_TOKEN = os.environ.get("HUBSPOT_TOKEN")  # private app token
HUBSPOT_MOCK  = os.environ.get("HUBSPOT_MOCK", "1") == "1"

_exact = None
def exact():
    global _exact
    if _exact is None:
        _exact = make_client()
    return _exact


# ---------------- HubSpot helpers ----------------

_MOCK_HS_DEALS = [
    {"id": "1001", "name": "Bakker — new ERP integration",   "amount": 18500, "stage": "closedwon",  "close_date": "2026-03-12", "company": "Bakker Bouwmaterialen B.V."},
    {"id": "1002", "name": "De Vries — fleet portal",         "amount": 42000, "stage": "closedwon",  "close_date": "2026-04-05", "company": "De Vries Logistiek"},
    {"id": "1003", "name": "Janssen — service app",           "amount":  9500, "stage": "closedwon",  "close_date": "2026-01-22", "company": "Janssen Installatietechniek"},
    {"id": "1004", "name": "Pietersen — wholesale platform",  "amount": 78000, "stage": "presented",  "close_date": "2026-05-30", "company": "Pietersen Groothandel"},
    {"id": "1005", "name": "Tjellens — recruitment dashboard","amount": 24000, "stage": "closedwon",  "close_date": "2026-02-14", "company": "Tjellens Personeelsdiensten"},
]

_MOCK_HS_COMPANIES = [
    {"id": "C-1", "name": "Bakker Bouwmaterialen B.V.",     "exact_code": "60001"},
    {"id": "C-2", "name": "De Vries Logistiek",              "exact_code": "60002"},
    {"id": "C-3", "name": "Janssen Installatietechniek",     "exact_code": "60003"},
    {"id": "C-4", "name": "Pietersen Groothandel",           "exact_code": "60004"},
    {"id": "C-5", "name": "Tjellens Personeelsdiensten",     "exact_code": "60005"},
]

def hubspot_get(endpoint: str, params: dict | None = None) -> dict:
    if HUBSPOT_MOCK or not HUBSPOT_TOKEN:
        return {"_mock": True}
    import requests
    r = requests.get(
        f"https://api.hubapi.com{endpoint}",
        headers={"Authorization": f"Bearer {HUBSPOT_TOKEN}"},
        params=params or {}, timeout=30,
    )
    r.raise_for_status()
    return r.json()


def hubspot_deals(stage: str | None = None, since: str | None = None) -> list[dict]:
    if HUBSPOT_MOCK or not HUBSPOT_TOKEN:
        data = _MOCK_HS_DEALS
        if stage: data = [d for d in data if d["stage"] == stage]
        if since: data = [d for d in data if d["close_date"] >= since]
        return data
    # Real HubSpot CRM API v3
    params = {"limit": 100, "properties": "dealname,amount,dealstage,closedate,associated_company"}
    if stage: params["filters"] = f'dealstage=={stage}'
    res = hubspot_get("/crm/v3/objects/deals", params)
    return [
        {
            "id": d["id"],
            "name": d["properties"]["dealname"],
            "amount": float(d["properties"].get("amount") or 0),
            "stage": d["properties"]["dealstage"],
            "close_date": d["properties"].get("closedate", "")[:10],
            "company": d["properties"].get("associated_company") or "",
        }
        for d in res.get("results", [])
    ]


def hubspot_company(name_query: str) -> dict | None:
    if HUBSPOT_MOCK or not HUBSPOT_TOKEN:
        return next((c for c in _MOCK_HS_COMPANIES if name_query.lower() in c["name"].lower()), None)
    # search HubSpot
    import requests
    r = requests.post(
        "https://api.hubapi.com/crm/v3/objects/companies/search",
        headers={"Authorization": f"Bearer {HUBSPOT_TOKEN}",
                 "Content-Type": "application/json"},
        json={"query": name_query, "limit": 5,
              "properties": ["name", "exact_customer_code"]},
        timeout=30,
    )
    r.raise_for_status()
    rows = r.json().get("results", [])
    if not rows: return None
    p = rows[0]["properties"]
    return {"id": rows[0]["id"], "name": p.get("name"), "exact_code": p.get("exact_customer_code")}


# ---------------- tools ----------------

@mcp.tool()
def find_uninvoiced_won_deals(since_date: str | None = None) -> list[dict]:
    """
    Find HubSpot deals in stage 'closedwon' that have NO matching invoice
    in Exact since the deal close date. since_date in 'YYYY-MM-DD'.
    """
    won = hubspot_deals(stage="closedwon", since=since_date)
    out = []
    for deal in won:
        company = hubspot_company(deal["company"])
        if not company or not company.get("exact_code"):
            out.append({**deal, "issue": "no exact_code mapped on HubSpot company"})
            continue
        invs = exact().list_invoices(customer_code=company["exact_code"])
        # crude match: any invoice dated on/after close_date
        matched = [i for i in invs if i.date >= deal["close_date"]]
        if not matched:
            out.append({**deal,
                        "exact_code": company["exact_code"],
                        "issue": "won deal but no invoice in Exact since close date"})
    return out


@mcp.tool()
def customer_360(company_name: str) -> dict:
    """
    Combined view of a customer: HubSpot company + deals + Exact financials
    (open invoices, AR total, days outstanding).
    """
    company = hubspot_company(company_name)
    if not company:
        return {"error": f"No HubSpot company matching '{company_name}'"}
    deals = [d for d in hubspot_deals() if company_name.lower() in d["company"].lower()]
    exact_code = company.get("exact_code")
    exact_data: dict[str, Any] = {}
    if exact_code:
        cust = exact().get_customer(exact_code)
        invs = exact().list_invoices(customer_code=exact_code)
        exact_data = {
            "exact_code": exact_code,
            "customer": asdict(cust) if cust else None,
            "open_invoices": len([i for i in invs if i.status != "paid"]),
            "ar_total_eur": round(sum(i.amount_incl_vat for i in invs if i.status != "paid"), 2),
            "worst_days_overdue": max((i.days_overdue for i in invs), default=0),
        }
    return {
        "hubspot": {**company, "deals": deals, "deal_count": len(deals),
                     "pipeline_value_eur": sum(d["amount"] for d in deals if d["stage"] != "closedwon"),
                     "closed_won_eur": sum(d["amount"] for d in deals if d["stage"] == "closedwon")},
        "exact": exact_data,
    }


@mcp.tool()
def top_customers_by_revenue(top_n: int = 10) -> list[dict]:
    """
    Cross-reference HubSpot companies with Exact AR / paid invoices and
    rank by gross billed value. The list sales should be focusing on.
    """
    rows: list[dict] = []
    for hs_company in _MOCK_HS_COMPANIES if HUBSPOT_MOCK else []:
        invs = exact().list_invoices(customer_code=hs_company["exact_code"])
        if not invs: continue
        gross = round(sum(i.amount_incl_vat for i in invs), 2)
        rows.append({
            "hubspot_company": hs_company["name"],
            "exact_code":      hs_company["exact_code"],
            "invoice_count":   len(invs),
            "gross_eur":       gross,
        })
    return sorted(rows, key=lambda x: x["gross_eur"], reverse=True)[:top_n]


@mcp.tool()
def credit_risk_flags() -> list[dict]:
    """
    HubSpot deals/companies that look risky based on Exact data:
    customers with >60 days overdue or AR exceeding credit limit.
    """
    flags: list[dict] = []
    for hs_company in _MOCK_HS_COMPANIES if HUBSPOT_MOCK else []:
        cust = exact().get_customer(hs_company["exact_code"])
        if not cust: continue
        invs = exact().list_invoices(customer_code=hs_company["exact_code"])
        ar = sum(i.amount_incl_vat for i in invs if i.status != "paid")
        worst = max((i.days_overdue for i in invs), default=0)
        reasons = []
        if cust.credit_limit and ar > cust.credit_limit:
            reasons.append(f"AR EUR {ar:,.0f} exceeds credit limit EUR {cust.credit_limit:,.0f}")
        if worst >= 60:
            reasons.append(f"{worst} days past due on at least one invoice")
        if reasons:
            flags.append({
                "company": hs_company["name"],
                "exact_code": hs_company["exact_code"],
                "ar_total_eur": round(ar, 2),
                "credit_limit_eur": cust.credit_limit,
                "worst_days_overdue": worst,
                "reasons": reasons,
            })
    return flags


if __name__ == "__main__":
    mcp.run()
