"""
MCP server: Business Insights on Exact data.

Instead of building dashboards, ask:

    "What's my cash forecast for the next 90 days?"
    "Who are my top 5 overdue customers by amount?"
    "What's the DSO trend? Is it getting worse?"
    "Concentration risk — what % of revenue is in my top 3 customers?"
    "Project an end-of-quarter P&L based on current pipeline + AR."

Every tool returns JSON ready for the LLM to summarise verbally.
"""
from __future__ import annotations

import os
import sys
import statistics
from pathlib import Path
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "exact-client"))
from exact_client import make_client  # noqa: E402

from mcp.server.fastmcp import FastMCP  # noqa: E402

mcp = FastMCP("business-insights")

_client = None
def client():
    global _client
    if _client is None:
        _client = make_client()
    return _client


# ---------------- tools ----------------

@mcp.tool()
def dso_analysis() -> dict:
    """
    Days Sales Outstanding analysis. Returns weighted average DSO, count
    of buckets (0-30, 31-60, 61-90, 90+), and the headline number.
    """
    invs = client().list_invoices()
    open_invs = [i for i in invs if i.status != "paid"]
    if not open_invs:
        return {"open_invoice_count": 0}

    today = date.today()
    weighted_days = 0.0
    total = 0.0
    buckets = {"0-30": 0, "31-60": 0, "61-90": 0, "90+": 0}
    bucket_amount = {"0-30": 0.0, "31-60": 0.0, "61-90": 0.0, "90+": 0.0}

    for i in open_invs:
        # days outstanding = today - invoice date
        try:
            d = (today - date.fromisoformat(i.date)).days
        except Exception:
            d = i.days_overdue or 0
        weighted_days += d * i.amount_incl_vat
        total += i.amount_incl_vat
        if d <= 30:    key = "0-30"
        elif d <= 60:  key = "31-60"
        elif d <= 90:  key = "61-90"
        else:          key = "90+"
        buckets[key] += 1
        bucket_amount[key] += i.amount_incl_vat

    dso = round(weighted_days / total, 1) if total else 0
    return {
        "headline_dso_days":     dso,
        "open_invoice_count":    len(open_invs),
        "ar_total_eur":          round(total, 2),
        "ageing_buckets":        buckets,
        "ageing_buckets_amount": {k: round(v, 2) for k, v in bucket_amount.items()},
        "interpretation":        ("healthy" if dso < 30
                                  else "watch" if dso < 45
                                  else "concerning" if dso < 60
                                  else "critical"),
    }


@mcp.tool()
def top_overdue_customers(top_n: int = 5) -> list[dict]:
    """Rank customers by overdue amount; useful for the chase list."""
    invs = client().list_invoices(min_days_overdue=1)
    per_cust: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "customer_code": "", "customer_name": "",
        "overdue_count": 0, "overdue_eur": 0.0, "worst_days": 0,
    })
    for i in invs:
        b = per_cust[i.customer_code]
        b["customer_code"] = i.customer_code
        b["customer_name"] = i.customer_name
        b["overdue_count"] += 1
        b["overdue_eur"]   += i.amount_incl_vat
        b["worst_days"]    = max(b["worst_days"], i.days_overdue)
    rows = list(per_cust.values())
    for r in rows: r["overdue_eur"] = round(r["overdue_eur"], 2)
    return sorted(rows, key=lambda r: r["overdue_eur"], reverse=True)[:top_n]


@mcp.tool()
def revenue_concentration() -> dict:
    """
    What percentage of revenue is concentrated in the top N customers?
    Single-customer dependency is the silent killer of MKB.
    """
    invs = client().list_invoices()
    per_cust: dict[str, float] = defaultdict(float)
    for i in invs:
        per_cust[i.customer_name] += i.amount_incl_vat
    total = sum(per_cust.values())
    if not total: return {"total_eur": 0}
    ranked = sorted(per_cust.items(), key=lambda kv: kv[1], reverse=True)
    top1 = ranked[0][1] / total * 100 if ranked else 0
    top3 = sum(v for _, v in ranked[:3]) / total * 100
    top5 = sum(v for _, v in ranked[:5]) / total * 100
    return {
        "total_eur":   round(total, 2),
        "customers":   len(per_cust),
        "top_1_share_pct": round(top1, 1),
        "top_3_share_pct": round(top3, 1),
        "top_5_share_pct": round(top5, 1),
        "ranked":      [{"customer": k, "eur": round(v, 2),
                         "share_pct": round(v / total * 100, 1)}
                        for k, v in ranked[:10]],
        "risk_flag":   ("high concentration risk" if top3 > 50 else
                        "moderate concentration" if top3 > 35 else "diversified"),
    }


@mcp.tool()
def cash_forecast_90d() -> dict:
    """
    Naive 90-day cash forecast:
      starting cash + expected AR collections - expected AP payments.
    Collections assume average DSO. Returns weekly buckets.
    """
    summary = client().get_financial_summary()
    invs = [i for i in client().list_invoices() if i.status != "paid"]

    today = date.today()
    weekly_in: dict[str, float] = defaultdict(float)
    for i in invs:
        try:
            d = date.fromisoformat(i.due_date)
        except Exception:
            continue
        # collected when due, but past-due ones land "next week" as a heuristic
        landing = max(d, today + timedelta(days=7))
        week_key = (landing - (today)).days // 7
        if 0 <= week_key < 13:
            weekly_in[f"week_{week_key+1}"] += i.amount_incl_vat

    # Very rough payable schedule: assume payables paid evenly over 8 weeks
    weekly_out = summary.open_payables / 8 if summary.open_payables else 0
    weekly: list[dict] = []
    cash = summary.cash_position
    for w in range(1, 14):
        inflow  = round(weekly_in.get(f"week_{w}", 0), 2)
        outflow = round(weekly_out if w <= 8 else 0, 2)
        cash += inflow - outflow
        weekly.append({"week": w, "inflow_eur": inflow,
                       "outflow_eur": outflow,
                       "projected_cash_eur": round(cash, 2)})
    return {
        "starting_cash_eur": round(summary.cash_position, 2),
        "13_week_forecast":  weekly,
        "ending_cash_eur":   weekly[-1]["projected_cash_eur"],
        "low_point_eur":     min(w["projected_cash_eur"] for w in weekly),
        "assumptions": [
            "Open AR collected on due date; past-due slid to next week",
            "AP paid evenly over the next 8 weeks",
            "No new sales / costs modelled (pure pipeline run-out)",
        ],
    }


@mcp.tool()
def margin_health() -> dict:
    """
    Quick margin pulse: revenue / costs / gross margin / margin %.
    """
    s = client().get_financial_summary()
    pct = (s.gross_margin / s.revenue * 100) if s.revenue else 0
    return {
        "period":            s.period,
        "revenue_eur":       round(s.revenue, 2),
        "costs_eur":         round(s.costs, 2),
        "gross_margin_eur":  round(s.gross_margin, 2),
        "gross_margin_pct":  round(pct, 1),
        "interpretation":    ("strong" if pct >= 40 else
                              "ok"     if pct >= 25 else
                              "thin"   if pct >= 10 else "underwater"),
    }


if __name__ == "__main__":
    mcp.run()
