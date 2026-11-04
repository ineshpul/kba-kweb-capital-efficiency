"""
Quick aging check of the March 2026 KBA vs KWEB capital-efficiency snapshot.

Keeps the audited methodology (ROIC vs WACC for corporates, ROE vs Ke for
financials, FactSet betas, 6.05% ERP, 15% tax, cash cap at 10% of revenue).
Refreshes two things:
  - latest annual financials from yfinance (manual FY25 overrides are not frozen)
  - risk-free rates and a parallel shift in the cost of debt, as of 30 Oct 2026

Does not overwrite output/unified_analysis_data.csv.
"""

import os
import numpy as np
import pandas as pd
import yfinance as yf

import kba_kweb_full_analysis_audited as base

OUT = os.path.join("output", "aging_20261030")
os.makedirs(OUT, exist_ok=True)

# 30 Oct 2026 closes. 31 Oct is a Saturday.
# US: Treasury CMT 10-year. China: ChinaBond government curve, 10-year.
US_RFR_NEW = 0.0494
PBOC_RFR_NEW = 0.0165
US_RFR_OLD = base.US_RFR
PBOC_RFR_OLD = base.PBOC_RFR
COD_SHIFT_US = US_RFR_NEW - US_RFR_OLD
COD_SHIFT_CN = PBOC_RFR_NEW - PBOC_RFR_OLD

# Live statements only. The March manual block would freeze the heavyweights.
base.MANUAL_DATA = {}


def apply_rates(us_rfr, pboc_rfr, cod_us, cod_cn):
    base.US_RFR = us_rfr
    base.PBOC_RFR = pboc_rfr
    base.COST_OF_DEBT_US = cod_us
    base.COST_OF_DEBT_CN = cod_cn


def fetch_one(yf_ticker, name, sector):
    try:
        return base.get_financial_metrics(yf_ticker, name, sector)
    except Exception as exc:
        print(f"  ! {name}: {exc}")
        return None


def iter_holdings():
    for name, code, yf_ticker, weight, sector in base.KBA_HOLDINGS:
        yield "KBA", name, yf_ticker, weight, sector, True
    for name, yf_ticker, _exch, weight, sector in base.KWEB_HOLDINGS:
        yield "KWEB", name, yf_ticker, weight, sector, False


def refresh_spy_betas():
    """3-year weekly beta of each ETF vs SPY, through 30 Oct 2026."""
    px = yf.download(
        ["KBA", "KWEB", "SPY"],
        start="2023-10-31",
        end="2026-10-31",
        interval="1wk",
        auto_adjust=True,
        progress=False,
    )
    close = px["Close"] if isinstance(px.columns, pd.MultiIndex) else px
    rets = close.pct_change().dropna()
    out = {}
    var_m = rets["SPY"].var()
    for etf in ("KBA", "KWEB"):
        aligned = rets[[etf, "SPY"]].dropna()
        beta = aligned[etf].cov(aligned["SPY"]) / aligned["SPY"].var()
        out[etf] = round(float(beta), 2)
        out[etf + "_n"] = int(len(aligned))
    out["spy_var"] = float(var_m)
    return out


def main():
    old = pd.read_csv("output/unified_analysis_data.csv")
    old_key = old.set_index(["etf", "name"])

    print("Refreshing 3-year weekly betas vs SPY...")
    spy = refresh_spy_betas()
    print(f"  KBA beta vs SPY: {spy['KBA']:.2f} (was {base.SPY_BETA_KBA})  n={spy['KBA_n']}")
    print(f"  KWEB beta vs SPY: {spy['KWEB']:.2f} (was {base.SPY_BETA_KWEB})  n={spy['KWEB_n']}")

    # Operating refresh uses new risk-free rates. Betas stay the March FactSet set
    # so the comparison is the financials and the rate move, not a new beta source.
    apply_rates(
        US_RFR_NEW,
        PBOC_RFR_NEW,
        base.COST_OF_DEBT_US + COD_SHIFT_US,
        base.COST_OF_DEBT_CN + COD_SHIFT_CN,
    )

    rows = []
    print("\nPulling latest annuals...")
    for etf, name, ticker, weight, sector, is_kba in iter_holdings():
        beta = base.FACTSET_BETAS.get((etf, name), base.SECTOR_BETA_FALLBACK.get(sector, 1.0))
        fin = fetch_one(ticker, name, sector)
        status = "refreshed"
        if fin is None and (etf, name) in old_key.index:
            prev = old_key.loc[(etf, name)]
            fin = {
                "metric_type": prev["metric_type"],
                "return_rate": float(prev["return_rate"]),
                "equity": float(prev["equity"]),
                "debt": float(prev["debt"]),
                "source": "carried_" + str(prev["data_source"]),
                "fiscal_year": prev["fiscal_year"],
            }
            status = "carried"
        if fin is None:
            print(f"  x {etf:4} {name}: no data")
            continue

        # Hurdles at the new rates, and again at the March rates, same capital structure.
        hurdle_dom = base.calc_hurdle_rate(
            beta, fin["equity"], fin["debt"], sector, is_kba=is_kba, use_spy_beta=False
        )
        hurdle_spy = base.calc_hurdle_rate(
            beta, fin["equity"], fin["debt"], sector, is_kba=is_kba, use_spy_beta=True
        )
        apply_rates(US_RFR_OLD, PBOC_RFR_OLD, 0.05, 0.035)
        hurdle_dom_old_rates = base.calc_hurdle_rate(
            beta, fin["equity"], fin["debt"], sector, is_kba=is_kba, use_spy_beta=False
        )
        apply_rates(
            US_RFR_NEW,
            PBOC_RFR_NEW,
            0.05 + COD_SHIFT_US,
            0.035 + COD_SHIFT_CN,
        )

        old_ret = old_hurdle = old_spread = old_fy = np.nan
        if (etf, name) in old_key.index:
            prev = old_key.loc[(etf, name)]
            old_ret = float(prev["return_rate"])
            old_hurdle = float(prev["hurdle_domestic"])
            old_spread = float(prev["spread_domestic"])
            old_fy = prev["fiscal_year"]

        spread_dom = round(fin["return_rate"] - hurdle_dom, 2)
        tag = "ok" if status == "refreshed" else "CARRY"
        print(
            f"  {tag:5} {etf:4} {name:28} {fin['metric_type']} {fin['return_rate']:6.1f}%"
            f"  (was {old_ret if pd.notna(old_ret) else float('nan'):6.1f})"
            f"  FY {fin.get('fiscal_year')} <- {old_fy}"
            f"  spread {spread_dom:6.1f} vs {old_spread if pd.notna(old_spread) else float('nan'):6.1f}"
        )
        rows.append({
            "etf": etf,
            "name": name,
            "weight": weight,
            "sector": sector,
            "status": status,
            "metric_type": fin["metric_type"],
            "return_new": fin["return_rate"],
            "return_old": old_ret,
            "fy_new": fin.get("fiscal_year"),
            "fy_old": old_fy,
            "hurdle_dom_new": hurdle_dom,
            "hurdle_dom_old": old_hurdle,
            "hurdle_dom_same_rates": hurdle_dom_old_rates,
            "hurdle_spy_new": hurdle_spy,
            "spread_dom_new": spread_dom,
            "spread_dom_old": old_spread,
            "spread_spy_new": round(fin["return_rate"] - hurdle_spy, 2),
            "source": fin["source"],
        })

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "aging_comparison.csv"), index=False)

    print("\n" + "=" * 72)
    print("PORTFOLIO COMPARISON  (weights of names present in BOTH snapshots)")
    print(f"Rates: China 10Y {PBOC_RFR_OLD*100:.2f}% -> {PBOC_RFR_NEW*100:.2f}%   "
          f"US 10Y {US_RFR_OLD*100:.2f}% -> {US_RFR_NEW*100:.2f}%   ERP unchanged at 6.05%")
    print("=" * 72)

    for etf in ("KBA", "KWEB"):
        both = df[(df.etf == etf) & df.return_old.notna() & df.spread_dom_old.notna()].copy()
        w = both.weight
        old_ret = np.average(both.return_old, weights=w)
        new_ret = np.average(both.return_new, weights=w)
        old_sp = np.average(both.spread_dom_old, weights=w)
        # Spread if only the financials moved, hurdles rebuilt at March rates
        spread_ops = both.return_new - both.hurdle_dom_same_rates
        ops_sp = np.average(spread_ops, weights=w)
        new_sp = np.average(both.spread_dom_new, weights=w)
        new_spy = np.average(both.spread_spy_new, weights=w)
        refreshed = (both.status == "refreshed").sum()
        print(
            f"\n{etf}  n={len(both)}  weight={w.sum():.1f}  "
            f"refreshed={refreshed}  carried={len(both) - refreshed}"
        )
        print(f"  Return     {old_ret:6.2f}%  ->  {new_ret:6.2f}%   ({new_ret - old_ret:+.2f} pp)")
        print(f"  Spread, ops only (March rates)     {old_sp:6.2f} -> {ops_sp:6.2f}   ({ops_sp - old_sp:+.2f} pp)")
        print(f"  Spread, domestic (new rates)       {old_sp:6.2f} -> {new_sp:6.2f}   ({new_sp - old_sp:+.2f} pp)")
        print(f"  Spread, US allocator (new rates, old ETF betas)   {new_spy:6.2f} pp")

        moved = both.copy()
        moved["d_ret"] = moved.return_new - moved.return_old
        moved["d_sp"] = moved.spread_dom_new - moved.spread_dom_old
        top = moved.reindex(moved.d_ret.abs().sort_values(ascending=False).index).head(6)
        print("  Largest return moves:")
        for _, r in top.iterrows():
            print(
                f"    {r['name']:28} w={r.weight:4.1f}  "
                f"{r.return_old:6.1f} -> {r.return_new:6.1f}  "
                f"spread {r.spread_dom_old:6.1f} -> {r.spread_dom_new:6.1f}  "
                f"FY {r.fy_old} -> {r.fy_new}  [{r.status}]"
            )

    print(f"\nSaved {os.path.join(OUT, 'aging_comparison.csv')}")
    print(
        "SPY betas above are informational. Portfolio spy spreads still use "
        f"the March ETF betas ({base.SPY_BETA_KBA}, {base.SPY_BETA_KWEB})."
    )


if __name__ == "__main__":
    main()
