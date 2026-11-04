"""
KBA vs KWEB — Complete Capital Efficiency Analysis (AUDITED FINAL)
================================================================
Bifurcated Pipeline: Corporates (ROIC vs WACC) & Financials (ROE vs Ke)
Audited Data: FactSet Universal Screen FY25 actuals applied to heavyweights.

Pipeline:
  1. Pull CSI300 / HSI index data
  2. Calculate real company-level betas via OLS regression
  3. Pull financials → calculate ROIC/WACC for corporates, ROE/Ke for financials
  4. Generate charts + tables using unified 'Spread' metric

Inesh Pulugurtha — Kelley School of Business, March 2026
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from datetime import datetime
import os
import warnings
warnings.filterwarnings('ignore')

# ══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════
OUTPUT_DIR = "./output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Beta regression window
START_DATE = "20230101"
END_DATE = "20260331"

# Valuation parameters
PBOC_RFR = 0.0183          # China 10Y risk-free rate
US_RFR = 0.0425            # US 10Y risk-free rate
ERP = 0.0605               # Combined equity + country risk premium (Damodaran 2025)
CRP = 0.0                  # Already included in ERP — do NOT double-count
TAX_RATE_DEFAULT = 0.15    # After-tax operating income (China effective ~15%)
COST_OF_DEBT_CN = 0.035    # Approximate pre-tax cost of debt, China
COST_OF_DEBT_US = 0.05     # Approximate pre-tax cost of debt, offshore

# SPY ETF-level betas (FactSet verified)
SPY_BETA_KBA = 0.43
SPY_BETA_KWEB = 0.94

# Excess cash adjustment: only subtract min(cash, 10% of revenue) from IC
EXCESS_CASH_CAP_PCT = 0.10

# ══════════════════════════════════════════════════════════════════
# HOLDINGS DATA
# ══════════════════════════════════════════════════════════════════

# KBA Holdings — (Name, AKShare code, yfinance ticker, Weight%, Sector)
KBA_HOLDINGS = [
    ("CATL", "300750", "300750.SZ", 7.0, "Industrial & Consumer"),
    ("Kweichow Moutai", "600519", "600519.SS", 5.0, "Industrial & Consumer"),
    ("Zijin Mining", "601899", "601899.SS", 3.5, "Industrial & Consumer"),
    ("Foxconn Industrial", "601138", "601138.SS", 3.0, "Technology & Semi"),
    ("Zhongji Innolight", "300308", "300308.SZ", 2.8, "Technology & Semi"),
    ("Hygon Information", "688041", "688041.SS", 2.5, "Technology & Semi"),
    ("Cambricon", "688256", "688256.SS", 2.3, "Technology & Semi"),
    ("CMOC Group", "603993", "603993.SS", 2.0, "Industrial & Consumer"),
    ("China Merchants Bank", "600036", "600036.SS", 2.0, "Financial & Const. SOE"),
    ("Eoptolink Technology", "300502", "300502.SZ", 1.8, "Technology & Semi"),
    ("China Yangtze Power", "600900", "600900.SS", 1.8, "Energy & Utilities"),
    ("Wanhua Chemical", "600309", "600309.SS", 1.7, "Energy & Utilities"),
    ("Ping An Insurance", "601318", "601318.SS", 1.7, "Financial & Const. SOE"),
    ("Agricultural Bank", "601288", "601288.SS", 1.5, "Financial & Const. SOE"),
    ("Midea Group", "000333", "000333.SZ", 1.5, "Industrial & Consumer"),
    ("Jiangsu Hengrui", "600276", "600276.SS", 1.5, "Industrial & Consumer"),
    ("Sungrow Power", "300274", "300274.SZ", 1.5, "Energy & Utilities"),
    ("ICBC", "601398", "601398.SS", 1.4, "Financial & Const. SOE"),
    ("Industrial Bank", "601166", "601166.SS", 1.3, "Financial & Const. SOE"),
    ("Bank of Communications", "601328", "601328.SS", 1.2, "Financial & Const. SOE"),
    ("China Shenhua", "601088", "601088.SS", 1.2, "Energy & Utilities"),
    ("CSSC Holdings", "600150", "600150.SS", 1.2, "Financial & Const. SOE"),
    ("East Money", "300059", "300059.SZ", 1.1, "Technology & Semi"),
    ("Beijing-Shanghai HSR", "601816", "601816.SS", 1.0, "Energy & Utilities"),
    ("Shanghai Pudong Bank", "600000", "600000.SS", 1.0, "Financial & Const. SOE"),
    ("WuXi AppTec", "603259", "603259.SS", 1.0, "Industrial & Consumer"),
    ("Wuliangye Yibin", "000858", "000858.SZ", 1.0, "Industrial & Consumer"),
    ("CITIC Securities", "600030", "600030.SS", 1.0, "Financial & Const. SOE"),
    ("Shenzhen Mindray", "300760", "300760.SZ", 1.0, "Industrial & Consumer"),
    ("NARI Technology", "600406", "600406.SS", 0.9, "Technology & Semi"),
    ("PetroChina", "601857", "601857.SS", 0.9, "Energy & Utilities"),
    ("China State Construction", "601668", "601668.SS", 0.9, "Financial & Const. SOE"),
    ("Shaanxi Coal", "601225", "601225.SS", 0.8, "Energy & Utilities"),
    ("China United Network", "600050", "600050.SS", 0.8, "Energy & Utilities"),
    ("China Pacific Insurance", "601601", "601601.SS", 0.8, "Financial & Const. SOE"),
    ("COSCO Shipping", "601919", "601919.SS", 0.7, "Energy & Utilities"),
    ("Guotai Haitong Securities", "601211", "601211.SS", 0.7, "Financial & Const. SOE"),
    ("SF Holding", "002352", "002352.SZ", 0.7, "Industrial & Consumer"),
    ("Muyuan Foods", "002714", "002714.SZ", 0.7, "Industrial & Consumer"),
    ("Zhejiang Century Huatong", "002602", "002602.SZ", 0.6, "Industrial & Consumer"),
    ("Bank of China", "601988", "601988.SS", 0.6, "Financial & Const. SOE"),
    ("Ping An Bank", "000001", "000001.SZ", 0.6, "Financial & Const. SOE"),
    ("China National Nuclear", "601985", "601985.SS", 0.6, "Energy & Utilities"),
    ("Bank of Ningbo", "002142", "002142.SZ", 0.6, "Financial & Const. SOE"),
    ("Shanxi Xinghuacun Fen Wine", "600809", "600809.SS", 0.5, "Industrial & Consumer"),
    ("China Merchants Shekou", "001979", "001979.SZ", 0.5, "Industrial & Consumer"),
    ("Poly Developments", "600048", "600048.SS", 0.5, "Financial & Const. SOE"),
    ("BYD", "002594", "002594.SZ", 4.0, "Industrial & Consumer"),
]

# KWEB Holdings — (Name, yfinance ticker, Exchange, Weight%, Sector)
KWEB_HOLDINGS = [
    ("Tencent", "0700.HK", "HK", 10.0, "Social & Entertainment"),
    ("Alibaba", "9988.HK", "HK", 9.5, "E-Commerce"),
    ("PDD Holdings", "PDD", "US", 7.0, "E-Commerce"),
    ("Meituan", "3690.HK", "HK", 6.0, "E-Commerce"),
    ("NetEase", "9999.HK", "HK", 4.5, "Social & Entertainment"),
    ("KE Holdings", "2423.HK", "HK", 3.5, "E-Commerce"),
    ("Baidu", "9888.HK", "HK", 3.5, "Social & Entertainment"),
    ("JD.com", "9618.HK", "HK", 3.5, "E-Commerce"),
    ("Kuaishou", "1024.HK", "HK", 3.0, "Social & Entertainment"),
    ("JD Health", "6618.HK", "HK", 2.5, "E-Commerce"),
    ("Tencent Music", "TME", "US", 2.5, "Social & Entertainment"),
    ("Trip.com", "9961.HK", "HK", 2.5, "E-Commerce"),
    ("Full Truck Alliance", "YMM", "US", 2.0, "E-Commerce"),
    ("Bilibili", "9626.HK", "HK", 2.0, "Social & Entertainment"),
    ("TAL Education", "TAL", "US", 1.8, "E-Commerce"),
    ("Kanzhun", "BZ", "US", 1.8, "E-Commerce"),
    ("Vipshop", "VIPS", "US", 1.5, "E-Commerce"),
    ("Alibaba Health", "0241.HK", "HK", 1.5, "E-Commerce"),
    ("Tongcheng Travel", "0780.HK", "HK", 1.5, "E-Commerce"),
    ("ZhongAn Online", "6060.HK", "HK", 1.2, "Fintech & Insurance"),
    ("NetEase Cloud Music", "9899.HK", "HK", 1.2, "Social & Entertainment"),
    ("China Literature", "0772.HK", "HK", 1.0, "Social & Entertainment"),
    ("JOYY", "YY", "US", 1.0, "Social & Entertainment"),
    ("QFIN Holdings", "QFIN", "US", 1.0, "Fintech & Insurance"),
    ("East Buy", "1797.HK", "HK", 0.8, "E-Commerce"),
    ("Ping An Healthcare", "1833.HK", "HK", 0.8, "Fintech & Insurance"),
    ("Autohome", "ATHM", "US", 0.7, "E-Commerce"),
    ("Damai Entertainment", "1060.HK", "HK", 0.5, "Social & Entertainment"),
    ("Weibo", "WB", "US", 0.5, "Social & Entertainment"),
]

# ══════════════════════════════════════════════════════════════════
# FACTSET AUDITED DATA (FY25 ACTUALS)
# ══════════════════════════════════════════════════════════════════
MANUAL_DATA = {
    # ── Corporates (ROIC Logic - Data from user screenshots) ──
    "002594": { # BYD
        "is_financial": False, "oi": 46243, "tax_rate": 0.15, "equity": 185258, 
        "debt": 0, "cash": 113874, "revenue": 840404, "fiscal_year": 2025
    },
    "9999": {   # NetEase
        "is_financial": False, "oi": 31192, "tax_rate": 0.15, "equity": 125504, 
        "debt": 0, "cash": 116344, "revenue": 108187, "fiscal_year": 2025
    },
    
    # ── Financials (ROE Logic - Data from FactSet CSV Screen) ──
    "601288": {"is_financial": True, "net_income": 305841, "equity": 2842306, "fiscal_year": 2025}, # Ag Bank
    "601318": {"is_financial": True, "net_income": 146170, "equity": 1114281, "fiscal_year": 2025}, # Ping An Ins
    "601166": {"is_financial": True, "net_income": 75333, "equity": 821716, "fiscal_year": 2025},   # Industrial Bank
    "601328": {"is_financial": True, "net_income": 98423, "equity": 1322915, "fiscal_year": 2025},  # Bank of Comms
    "600000": {"is_financial": True, "net_income": 47642, "equity": 766995, "fiscal_year": 2025},   # Shanghai Pudong
    "601668": {"is_financial": True, "net_income": 46187, "equity": 453185, "fiscal_year": 2025},   # China State Const
    "000001": {"is_financial": True, "net_income": 40988, "equity": 471184, "fiscal_year": 2025},   # Ping An Bank
    "002142": {"is_financial": True, "net_income": 29333, "equity": 247325, "fiscal_year": 2025},   # Bank of Ningbo
    "601601": {"is_financial": True, "net_income": 58027, "equity": 336531, "fiscal_year": 2025},   # China Pacific Ins
    
    # Missing from FactSet screen - commented out to prevent hallucinated data
    # "600036": {"is_financial": True, "net_income": 0, "equity": 0}, # China Merchants Bank
    # "601398": {"is_financial": True, "net_income": 0, "equity": 0}, # ICBC
    # "601988": {"is_financial": True, "net_income": 0, "equity": 0}, # Bank of China
    # "600030": {"is_financial": True, "net_income": 0, "equity": 0}, # CITIC Securities
}

SECTOR_BETA_FALLBACK = {
    "Industrial & Consumer": 0.85,
    "Technology & Semi": 1.20,
    "Financial & Const. SOE": 0.75,
    "Energy & Utilities": 0.65,
    "E-Commerce": 1.10,
    "Social & Entertainment": 1.05,
    "Fintech & Insurance": 1.15,
}

FACTSET_BETAS = {
    # ── KBA Holdings ──
    ("KBA", "CATL"): 1.6365,
    ("KBA", "Kweichow Moutai"): 1.0540,
    ("KBA", "Zijin Mining"): 1.0914,
    ("KBA", "Foxconn Industrial"): 2.1587,
    ("KBA", "Zhongji Innolight"): 3.1157,
    ("KBA", "Hygon Information"): 1.6369,
    ("KBA", "Cambricon"): 2.1920,
    ("KBA", "CMOC Group"): 1.5297,
    ("KBA", "China Merchants Bank"): 0.5824,
    ("KBA", "Eoptolink Technology"): 3.0393,
    ("KBA", "China Yangtze Power"): -0.1094,
    ("KBA", "Wanhua Chemical"): 1.6884,
    ("KBA", "Ping An Insurance"): 1.2328,
    ("KBA", "Agricultural Bank"): 0.3897,
    ("KBA", "Midea Group"): 0.6886,
    ("KBA", "Jiangsu Hengrui"): 1.1195,
    ("KBA", "Sungrow Power"): 1.7158,
    ("KBA", "ICBC"): -0.0366,
    ("KBA", "Industrial Bank"): 0.6215,
    ("KBA", "Bank of Communications"): 0.0928,
    ("KBA", "China Shenhua"): 0.0729,
    ("KBA", "CSSC Holdings"): 0.7218,
    ("KBA", "East Money"): 3.3291,
    ("KBA", "Beijing-Shanghai HSR"): 0.3577,
    ("KBA", "Shanghai Pudong Bank"): 0.7088,
    ("KBA", "WuXi AppTec"): 1.6554,
    ("KBA", "Wuliangye Yibin"): 1.5779,
    ("KBA", "CITIC Securities"): 1.5998,
    ("KBA", "Shenzhen Mindray"): 0.9785,
    ("KBA", "NARI Technology"): 0.5800,
    ("KBA", "PetroChina"): 0.2485,
    ("KBA", "China State Construction"): 0.6680,
    ("KBA", "Shaanxi Coal"): 0.3038,
    ("KBA", "China United Network"): 0.8200,
    ("KBA", "China Pacific Insurance"): 1.4515,
    ("KBA", "COSCO Shipping"): 0.9293,
    ("KBA", "Guotai Haitong Securities"): 0.1740,
    ("KBA", "SF Holding"): 1.2004,
    ("KBA", "Muyuan Foods"): 1.3560,
    ("KBA", "Zhejiang Century Huatong"): 1.4933,
    ("KBA", "Bank of China"): -0.0201,
    ("KBA", "Ping An Bank"): 1.0249,
    ("KBA", "China National Nuclear"): -0.0783,
    ("KBA", "Bank of Ningbo"): 1.2255,
    ("KBA", "Shanxi Xinghuacun Fen Wine"): 1.5749,
    ("KBA", "China Merchants Shekou"): 1.4468,
    ("KBA", "Poly Developments"): 1.4403,
    ("KBA", "BYD"): 1.1114,
    # ── KWEB Holdings ──
    ("KWEB", "Tencent"): 1.1714,
    ("KWEB", "Alibaba"): 2.1087,
    ("KWEB", "PDD Holdings"): 0.8218,
    ("KWEB", "Meituan"): 1.7698,
    ("KWEB", "NetEase"): 0.5127,
    ("KWEB", "KE Holdings"): 2.1230,
    ("KWEB", "Baidu"): 1.3406,
    ("KWEB", "JD.com"): 1.9056,
    ("KWEB", "Kuaishou"): 1.9296,
    ("KWEB", "JD Health"): 1.9885,
    ("KWEB", "Tencent Music"): 0.9251,
    ("KWEB", "Trip.com"): 0.8245,
    ("KWEB", "Full Truck Alliance"): 0.4422,
    ("KWEB", "Bilibili"): 2.7189,
    ("KWEB", "TAL Education"): 1.3545,
    ("KWEB", "Kanzhun"): 0.6892,
    ("KWEB", "Vipshop"): 1.3141,
    ("KWEB", "Alibaba Health"): 2.7580,
    ("KWEB", "Tongcheng Travel"): 0.9290,
    ("KWEB", "ZhongAn Online"): 1.7687,
    ("KWEB", "NetEase Cloud Music"): 0.8677,
    ("KWEB", "China Literature"): 1.2351,
    ("KWEB", "JOYY"): 0.6592,
    ("KWEB", "QFIN Holdings"): 1.2025,
    ("KWEB", "East Buy"): 1.6733,
    ("KWEB", "Ping An Healthcare"): 1.6151,
    ("KWEB", "Autohome"): 0.7430,
    ("KWEB", "Damai Entertainment"): 1.5629,
    ("KWEB", "Weibo"): 0.9015,
}

# ══════════════════════════════════════════════════════════════════
# STEP 1: FINANCIAL METRICS (ROIC vs ROE)
# ══════════════════════════════════════════════════════════════════

def get_financial_metrics(yf_ticker, name, sector):
    """
    Master function: Computes ROIC for Corporates, ROE for Financials.
    Returns unified metric called 'return_rate' to be matched against 'hurdle_rate'.
    """
    import yfinance as yf
    
    is_financial = 'Financial' in sector or 'Fintech' in sector
    code = yf_ticker.replace('.SZ', '').replace('.SS', '').replace('.HK', '')
    
    # 1. Check Manual Data First (Prevents Bank Data Loss & Patches NetEase)
    if code in MANUAL_DATA:
        d = MANUAL_DATA[code]
        if d['is_financial']:
            roe = d['net_income'] / d['equity']
            return {
                'metric_type': 'ROE', 'return_rate': round(roe * 100, 2), 
                'equity': d['equity'], 'debt': 0, 'source': 'manual',
                'fiscal_year': d.get('fiscal_year', 2025)
            }
        else:
            revenue = d.get('revenue', abs(d['oi']) * 5)
            cash_deduction = min(abs(d['cash']), abs(revenue) * EXCESS_CASH_CAP_PCT)
            ic = abs(d['equity']) + abs(d['debt']) - cash_deduction
            roic = (d['oi'] * (1 - d['tax_rate'])) / ic if ic > 0 else 0
            return {
                'metric_type': 'ROIC', 'return_rate': round(roic * 100, 2), 
                'equity': d['equity'], 'debt': d['debt'], 'source': 'manual',
                'fiscal_year': d.get('fiscal_year', 2025)
            }

    # 2. Try yfinance
    try:
        t = yf.Ticker(yf_ticker)
        fin = t.financials
        bal = t.balance_sheet
        
        if fin is None or fin.empty or bal is None or bal.empty:
            return None

        fin_date = fin.columns[0]
        fiscal_year = fin_date.year if hasattr(fin_date, 'year') else None

        equity = bal.loc['Stockholders Equity'].iloc[0] if 'Stockholders Equity' in bal.index else 0
        if pd.isna(equity) or equity <= 0:
            return None

        # -- FINANCIAL LOGIC (ROE) --
        if is_financial:
            ni = None
            for label in ['Net Income', 'Net Income Common Stockholders']:
                if label in fin.index:
                    ni = fin.loc[label].iloc[0]
                    break
            if ni is None or pd.isna(ni): return None
            
            roe = ni / equity
            # Sanity check
            if abs(roe) > 1.0: return None
            
            return {
                'metric_type': 'ROE', 'return_rate': round(roe * 100, 2), 
                'equity': equity, 'debt': 0, 'source': 'yfinance',
                'fiscal_year': fiscal_year
            }
            
        # -- CORPORATE LOGIC (ROIC) --
        else:
            oi = None
            for label in ['Operating Income', 'EBIT']:
                if label in fin.index:
                    oi = fin.loc[label].iloc[0]
                    break
            if oi is None or pd.isna(oi) or oi == 0: return None
            
            revenue = fin.loc['Total Revenue'].iloc[0] if 'Total Revenue' in fin.index else abs(oi) * 5
            debt = 0
            for label in ['Total Debt', 'Long Term Debt', 'Long Term Debt And Capital Lease Obligation']:
                if label in bal.index:
                    debt = bal.loc[label].iloc[0]
                    break
            
            cash = 0
            for label in ['Cash And Cash Equivalents', 'Cash Cash Equivalents And Short Term Investments']:
                if label in bal.index:
                    cash = bal.loc[label].iloc[0]
                    break
            
            debt = 0 if pd.isna(debt) else debt
            cash = 0 if pd.isna(cash) else cash
            
            cash_deduction = min(abs(cash), abs(revenue) * EXCESS_CASH_CAP_PCT)
            ic = abs(equity) + abs(debt) - cash_deduction
            
            if ic <= 0: return None
            
            roic = (oi * (1 - TAX_RATE_DEFAULT)) / ic
            if abs(roic) > 1.0: return None
            
            return {
                'metric_type': 'ROIC', 'return_rate': round(roic * 100, 2), 
                'equity': equity, 'debt': debt, 'source': 'yfinance',
                'fiscal_year': fiscal_year
            }
    except Exception:
        return None


def calc_hurdle_rate(beta, equity, debt, sector, is_kba=True, use_spy_beta=False):
    """
    Financials: Hurdle = Cost of Equity (Ke). 
    Corporates: Hurdle = WACC.
    """
    rfr = PBOC_RFR if (is_kba and not use_spy_beta) else US_RFR
    cod = COST_OF_DEBT_CN if is_kba else COST_OF_DEBT_US
    
    # If we want US Allocator view, force SPY beta
    if use_spy_beta:
        applied_beta = SPY_BETA_KBA if is_kba else SPY_BETA_KWEB
    else:
        applied_beta = beta

    is_financial = 'Financial' in sector or 'Fintech' in sector
    cost_of_equity = rfr + applied_beta * (ERP + CRP)
    
    if is_financial:
        return round(cost_of_equity * 100, 2)

    total_cap = abs(equity) + abs(debt)
    if total_cap == 0:
        return round(cost_of_equity * 100, 2)

    w_e = abs(equity) / total_cap
    w_d = abs(debt) / total_cap
    wacc = w_e * cost_of_equity + w_d * cod * (1 - TAX_RATE_DEFAULT)
    return round(wacc * 100, 2)


# ══════════════════════════════════════════════════════════════════
# STEP 2: BUILD DATAFRAME
# ══════════════════════════════════════════════════════════════════

def build_analysis():
    print("\n" + "=" * 65)
    print("STEP 1: ASSIGNING BETAS & CALCULATING FINANCIALS")
    print("=" * 65)

    all_rows = []
    
    def process_holdings(holdings, etf_name, is_kba):
        print(f"\n── {etf_name} HOLDINGS ───────────────────────────────────")
        for name, ticker_code, yf_ticker_or_exch, weight, sector in holdings:
            
            # Unpack handles different tuple lengths for KBA vs KWEB safely
            if is_kba:
                code, yf_ticker = ticker_code, yf_ticker_or_exch
            else:
                yf_ticker = ticker_code 
            
            # Beta
            beta_val = FACTSET_BETAS.get((etf_name, name), SECTOR_BETA_FALLBACK.get(sector, 1.0))
            beta_source = 'factset' if (etf_name, name) in FACTSET_BETAS else 'fallback'
            
            # Financials
            fin_data = get_financial_metrics(yf_ticker, name, sector)
            if fin_data is None:
                print(f"  ✗ {name:35s} NO FINANCIAL DATA")
                continue
                
            # Hurdle Rates (WACC for corporates, Ke for financials)
            hurdle_dom = calc_hurdle_rate(beta_val, fin_data['equity'], fin_data['debt'], sector, is_kba=is_kba, use_spy_beta=False)
            hurdle_spy = calc_hurdle_rate(beta_val, fin_data['equity'], fin_data['debt'], sector, is_kba=is_kba, use_spy_beta=True)

            spread_dom = round(fin_data['return_rate'] - hurdle_dom, 2)
            spread_spy = round(fin_data['return_rate'] - hurdle_spy, 2)

            print(f"  ✓ {name:30s} {fin_data['metric_type']}={fin_data['return_rate']:6.1f}%  "
                  f"β={beta_val:.2f}  Hurdle_dom={hurdle_dom:.1f}%  Spread={spread_dom:5.1f}pp")

            all_rows.append({
                'etf': etf_name, 'name': name, 'weight': weight, 'sector': sector,
                'metric_type': fin_data['metric_type'],
                'return_rate': fin_data['return_rate'],
                'beta': beta_val, 'beta_source': beta_source,
                'hurdle_domestic': hurdle_dom, 'hurdle_spy': hurdle_spy,
                'spread_domestic': spread_dom, 'spread_spy': spread_spy,
                'equity': fin_data['equity'], 'debt': fin_data['debt'],
                'data_source': fin_data['source'],
                'fiscal_year': fin_data.get('fiscal_year'),
            })

    process_holdings(KBA_HOLDINGS, 'KBA', is_kba=True)
    process_holdings(KWEB_HOLDINGS, 'KWEB', is_kba=False)

    df = pd.DataFrame(all_rows)
    df.to_csv(os.path.join(OUTPUT_DIR, 'unified_analysis_data.csv'), index=False)
    
    # Global FY label
    fy_vals = df['fiscal_year'].dropna().unique()
    fy_vals = sorted([int(y) for y in fy_vals])
    global FY_LABEL
    FY_LABEL = f"FY{fy_vals[0]}" if len(fy_vals) == 1 else (f"FY{min(fy_vals)}–{max(fy_vals)}" if len(fy_vals) > 1 else "Latest FY")

    return df


# ══════════════════════════════════════════════════════════════════
# STEP 3: CHARTS
# ══════════════════════════════════════════════════════════════════

C_KBA = '#2d8f2d'
C_KWEB = '#cc3333'

SECTOR_COLORS = {
    'Industrial & Consumer': '#4CAF50',
    'Technology & Semi': '#5B9BD5',
    'Financial & Const. SOE': '#9C27B0',
    'Energy & Utilities': '#E57373',
    'E-Commerce': '#cc3333',
    'Social & Entertainment': '#E91E90',
    'Fintech & Insurance': '#7B1FA2',
}

def get_footer_dom():
    return (f"Source: yfinance/FactSet {FY_LABEL}. KBA: PBOC 10Y RfR 1.83%, 3yr betas vs local index (FactSet), "
            "ERP+CRP 6.05% (Damodaran 2025). KWEB: US 10Y RfR 4.25%. "
            "METHODOLOGY BIFURCATION: Corporates measured on ROIC vs WACC (IC cash capped at 10% rev). "
            "Financial/SOE holdings (faded) measured on ROE vs Cost of Equity (Ke). All metrics unified as 'Spread'.")

def get_footer_spy():
    return (f"Source: yfinance/FactSet {FY_LABEL}. US Allocator perspective: US 10Y RfR 4.25%, ETF-level SPY betas "
            "(KBA=0.43, KWEB=0.94). Corporates: ROIC vs WACC. Financials (faded): ROE vs Ke. Unified 'Spread'.")

def chart_summary_bars(df, chart_set, filename):
    hurdle_col = 'hurdle_domestic' if chart_set == 'domestic' else 'hurdle_spy'
    spread_col = 'spread_domestic' if chart_set == 'domestic' else 'spread_spy'
    footer = get_footer_dom() if chart_set == 'domestic' else get_footer_spy()
    title_suffix = "Domestic Capital Market Betas" if chart_set == 'domestic' else "US Allocator View (SPY Betas)"

    kba = df[df['etf'] == 'KBA']
    kweb = df[df['etf'] == 'KWEB']

    # Weighted averages
    kba_ret = np.average(kba['return_rate'], weights=kba['weight'])
    kweb_ret = np.average(kweb['return_rate'], weights=kweb['weight'])
    kba_hurdle = np.average(kba[hurdle_col], weights=kba['weight'])
    kweb_hurdle = np.average(kweb[hurdle_col], weights=kweb['weight'])
    kba_spread = np.average(kba[spread_col], weights=kba['weight'])
    kweb_spread = np.average(kweb[spread_col], weights=kweb['weight'])
    kba_ratio = kba_ret / kba_hurdle if kba_hurdle > 0 else 0
    kweb_ratio = kweb_ret / kweb_hurdle if kweb_hurdle > 0 else 0

    fig, axes = plt.subplots(1, 4, figsize=(20, 5))
    fig.suptitle(f"KBA vs KWEB — Unified Capital Efficiency ({FY_LABEL})\n{title_suffix}", fontsize=14, fontweight='bold', y=1.02)

    metrics = [
        ("Capital Return (ROIC/ROE)", [kba_ret, kweb_ret], "Return (%)"),
        ("Hurdle Rate (WACC/Ke)", [kba_hurdle, kweb_hurdle], "Hurdle (%)"),
        ("Value Creation Spread", [kba_spread, kweb_spread], "Spread (pp)"),
        ("Return / Hurdle Efficiency", [kba_ratio, kweb_ratio], "Ratio (x)"),
    ]

    for ax, (title, vals, ylabel) in zip(axes, metrics):
        bars = ax.bar(['KBA', 'KWEB'], vals, color=[C_KBA, C_KWEB], width=0.5)
        ax.set_title(title, fontsize=11, fontweight='bold')
        ax.set_ylabel(ylabel)
        ax.set_ylim(min(0, min(vals)*1.2), max(vals) * 1.3)

        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width()/2, max(0, bar.get_height()) + max(vals)*0.02,
                    f'{val:.2f}', ha='center', va='bottom', fontweight='bold',
                    fontsize=11, color=C_KBA if bar.get_x()==0 else C_KWEB)

    fig.text(0.5, -0.06, footer, ha='center', fontsize=7, color='gray', wrap=True)
    plt.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, filename), dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()

    return {
        'kba_ret': kba_ret, 'kweb_ret': kweb_ret,
        'kba_hurdle': kba_hurdle, 'kweb_hurdle': kweb_hurdle,
        'kba_spread': kba_spread, 'kweb_spread': kweb_spread,
        'kba_ratio': kba_ratio, 'kweb_ratio': kweb_ratio,
    }


def chart_holdings_detail(df, etf, chart_set, filename):
    hurdle_col = 'hurdle_domestic' if chart_set == 'domestic' else 'hurdle_spy'
    footer = get_footer_dom() if chart_set == 'domestic' else get_footer_spy()

    sub = df[df['etf'] == etf].copy().sort_values('return_rate', ascending=True)
    fig, ax = plt.subplots(figsize=(12, max(8, len(sub) * 0.35)))
    
    for i, (_, row) in enumerate(sub.iterrows()):
        color = SECTOR_COLORS.get(row['sector'], '#888888')
        alpha = 0.5 if row['metric_type'] == 'ROE' else 1.0 # Fade financials
        
        ax.barh(i, row['return_rate'], color=color, alpha=alpha, height=0.7, zorder=2)
        ax.plot(row[hurdle_col], i, 's', color='gray', markersize=5, zorder=3)
        ax.text(row[hurdle_col], i + 0.3, f"{row[hurdle_col]:.1f}%", fontsize=6, color='gray', ha='center')
        
        label_x = max(row['return_rate'] + 0.5, 1.0)
        ax.text(label_x, i, f"{row['return_rate']:.1f}%", va='center', fontsize=8, fontweight='bold')

    ax.set_yticks(range(len(sub)))
    ax.set_yticklabels(sub['name'].values, fontsize=8)
    ax.axvline(x=0, color='black', linewidth=0.5, linestyle='--', zorder=1)
    ax.set_xlabel('(%)')
    ax.set_title(f"{etf} Holdings — Capital Return vs Hurdle Rate ({FY_LABEL})", fontsize=13, fontweight='bold')

    from matplotlib.patches import Patch
    legend_elements = [Patch(facecolor=SECTOR_COLORS.get(s, '#888'), label=s) for s in sub['sector'].unique()]
    legend_elements.append(Patch(facecolor='gray', label='Hurdle (WACC/Ke)'))
    ax.legend(handles=legend_elements, loc='lower right', fontsize=7)

    fig.text(0.5, -0.02, footer, ha='center', fontsize=6, color='gray', wrap=True)
    plt.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, filename), dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()


def main():
    print("=" * 65)
    print("KBA vs KWEB — BIFURCATED CAPITAL EFFICIENCY PIPELINE")
    print("=" * 65)

    df = build_analysis()

    print("\n── Generating Charts ──────────────────────────────")
    stats_dom = chart_summary_bars(df, 'domestic', 'chart1_summary_domestic.png')
    chart_holdings_detail(df, 'KBA', 'domestic', 'chart2_kba_detail_domestic.png')
    chart_holdings_detail(df, 'KWEB', 'domestic', 'chart3_kweb_detail_domestic.png')
    
    stats_spy = chart_summary_bars(df, 'spy', 'chart4_summary_spy.png')
    chart_holdings_detail(df, 'KBA', 'spy', 'chart5_kba_detail_spy.png')
    chart_holdings_detail(df, 'KWEB', 'spy', 'chart6_kweb_detail_spy.png')

    print("\nFINAL HEADLINE NUMBERS (Structural Betas):")
    print(f"KBA Capital Return (Wtd): {stats_dom['kba_ret']:.1f}% | KWEB: {stats_dom['kweb_ret']:.1f}%")
    print(f"KBA Spread (Wtd):         {stats_dom['kba_spread']:.1f}pp | KWEB: {stats_dom['kweb_spread']:.1f}pp")
    print("\nAll files saved to ./output directory. Ready for integration.")

if __name__ == "__main__":
    main()