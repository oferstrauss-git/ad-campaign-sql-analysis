"""
Ad-Tech Retail Dataset Generator
=================================
Generates a realistic daily-level advertising dataset for an online retail platform.
Columns: country, campaign_id, campaign_type, seller_id, date,
         impressions, clicks, conversions, revenue, GMV

KPIs are modeled on realistic online retail benchmarks:
  - CTR (Click-Through Rate):     0.5% – 4%
  - CVR (Conversion Rate):        1% – 8% of clicks
  - AOV (Average Order Value):    $20 – $300 depending on country/seller tier
  - ROAS (Revenue / Ad Spend):    implicitly embedded in revenue
  - GMV = units_sold * AOV       (revenue is the ad-attributed portion)

Usage:
  Run in Google Colab or locally:
      python generate_adtech_dataset.py

Output:
  ad_campaign_data.csv  (~50,000–70,000 rows)
"""

import pandas as pd
import numpy as np
from datetime import date, timedelta
import random

# ── Reproducibility ──────────────────────────────────────────────────────────
SEED = 42
np.random.seed(SEED)
random.seed(SEED)

# ── Configuration ─────────────────────────────────────────────────────────────

COUNTRIES = [
    "United States", "United Kingdom", "Germany", "France", "Israel",
    "Netherlands", "Canada", "Australia", "Spain", "Italy"
]

CAMPAIGN_TYPES = ["Automatic", "Manual", "Hybrid", "Store_Run"]

# Date range: 18 months of data — enough for cohort, trend, and seasonality analysis
START_DATE = date(2023, 1, 1)
END_DATE   = date(2024, 6, 30)

NUM_SELLERS   = 120   # sellers across all countries
NUM_CAMPAIGNS = 400   # campaigns (sellers can have multiple)

# ── Country-level traits ──────────────────────────────────────────────────────
# Each country gets a modifier affecting impression volume and AOV
COUNTRY_TRAITS = {
    "United States":  {"impression_scale": 1.8, "aov_scale": 1.4},
    "United Kingdom": {"impression_scale": 1.3, "aov_scale": 1.1},
    "Germany":        {"impression_scale": 1.2, "aov_scale": 1.2},
    "France":         {"impression_scale": 1.0, "aov_scale": 1.0},
    "Israel":         {"impression_scale": 0.7, "aov_scale": 0.95},
    "Netherlands":    {"impression_scale": 0.8, "aov_scale": 1.05},
    "Canada":         {"impression_scale": 1.0, "aov_scale": 1.1},
    "Australia":      {"impression_scale": 0.9, "aov_scale": 1.15},
    "Spain":          {"impression_scale": 0.85, "aov_scale": 0.9},
    "Italy":          {"impression_scale": 0.8, "aov_scale": 0.95},
}

# Campaign type traits: Automatic gets broader reach, Manual gets better CVR
CAMPAIGN_TYPE_TRAITS = {
    "Automatic":  {"ctr_mult": 0.85, "cvr_mult": 0.90, "impression_mult": 1.3},
    "Manual":     {"ctr_mult": 1.15, "cvr_mult": 1.20, "impression_mult": 0.85},
    "Hybrid":     {"ctr_mult": 1.05, "cvr_mult": 1.05, "impression_mult": 1.0},
    "Store_Run":  {"ctr_mult": 0.75, "cvr_mult": 0.80, "impression_mult": 1.5},
}

# ── Seller tier: affects budget/scale ────────────────────────────────────────
SELLER_TIERS = ["small", "medium", "large"]
TIER_WEIGHTS  = [0.5, 0.35, 0.15]   # most sellers are small

TIER_TRAITS = {
    "small":  {"base_impressions": 800,   "aov_base": 35,  "campaign_count_range": (1, 3)},
    "medium": {"base_impressions": 4000,  "aov_base": 80,  "campaign_count_range": (2, 6)},
    "large":  {"base_impressions": 18000, "aov_base": 150, "campaign_count_range": (4, 12)},
}

# ── Seasonality weights by month ─────────────────────────────────────────────
# Peaks: Nov (Black Friday), Dec (Christmas), Jan (sales), Q2 moderate
MONTHLY_SEASONALITY = {
    1: 1.20, 2: 0.85, 3: 0.90, 4: 0.95,
    5: 1.00, 6: 1.05, 7: 0.90, 8: 0.92,
    9: 1.00, 10: 1.10, 11: 1.45, 12: 1.55,
}

# Weekday weights: weekends slightly lower for B2C retail
WEEKDAY_WEIGHTS = {0: 1.05, 1: 1.00, 2: 1.00, 3: 1.02, 4: 1.08, 5: 0.88, 6: 0.85}

# ── Pareto (80/20) configuration ─────────────────────────────────────────────
# ~80% of total sales come from ~20% of sellers.
# Within each seller, ~80% of that seller's sales come from ~20% of their campaigns.
PARETO_TOP_SELLER_SHARE   = 0.20   # top 20% of sellers...
PARETO_TOP_SELLER_POWER   = 0.20   # ...drive this share of total seller-level weight
PARETO_TOP_CAMPAIGN_SHARE = 0.20   # top 20% of a seller's campaigns...
PARETO_TOP_CAMPAIGN_POWER = 0.20   # ...drive this share of that seller's weight
# NOTE: seller-level and campaign-level Pareto effects compound multiplicatively
# (a top campaign at a top seller gets boosted twice). Using ~0.55 at each layer
# combines to land the OVERALL top-20%-of-sellers and top-20%-of-campaigns
# revenue shares close to the classic ~80% mark — see the "PARETO CHECK" printed
# at the end of the script, and tune these two constants up/down if you want a
# stronger or weaker effect for your portfolio story.

def assign_pareto_weights(n_items, top_share=0.20, top_power=0.80, jitter=0.15):
    """
    Returns an array of `n_items` positive weights (sums to n_items, i.e. average weight = 1.0)
    such that the top `top_share` fraction of items collectively hold `top_power` of total weight,
    and the remaining items split the rest. Adds light jitter so it isn't perfectly uniform within
    each group (more realistic).
    """
    n_top = max(1, int(round(n_items * top_share)))
    n_rest = n_items - n_top

    total_weight = n_items  # so average weight stays 1.0 (keeps overall scale unchanged)
    top_total    = total_weight * top_power
    rest_total   = total_weight - top_total

    # Within each group, distribute weight with some random variation (not perfectly equal)
    def split_weight(group_total, group_n):
        if group_n == 0:
            return np.array([])
        raw = np.random.uniform(1 - jitter, 1 + jitter, size=group_n)
        raw = raw / raw.sum()           # normalize to sum to 1
        return raw * group_total

    top_weights  = split_weight(top_total, n_top)
    rest_weights = split_weight(rest_total, n_rest)

    weights = np.concatenate([top_weights, rest_weights])
    order   = np.random.permutation(n_items)   # shuffle so "top" isn't always index 0..n_top
    final   = np.empty(n_items)
    final[order] = weights
    return final

# ── Build seller universe ─────────────────────────────────────────────────────
def build_sellers(n=NUM_SELLERS):
    sellers = []
    seller_pareto_weights = assign_pareto_weights(
        n, PARETO_TOP_SELLER_SHARE, PARETO_TOP_SELLER_POWER
    )

    for i in range(1, n + 1):
        tier    = np.random.choice(SELLER_TIERS, p=TIER_WEIGHTS)
        country = random.choice(COUNTRIES)
        sellers.append({
            "seller_id":      f"S{i:04d}",
            "country":        country,
            "tier":           tier,
            "pareto_weight":  seller_pareto_weights[i - 1],   # drives overall seller "power"
        })
    return sellers

# ── Build campaign universe ───────────────────────────────────────────────────
def build_campaigns(sellers, n=NUM_CAMPAIGNS):
    campaigns = []

    # First, decide how many campaigns each seller gets, weighted so high-pareto
    # ("whale") sellers tend to run more campaigns too.
    seller_weights = np.array([s["pareto_weight"] for s in sellers])
    seller_probs   = seller_weights / seller_weights.sum()

    seller_choices = np.random.choice(len(sellers), size=n, p=seller_probs)

    # Group campaign indices by seller so we can assign within-seller Pareto weights
    from collections import defaultdict
    campaigns_by_seller = defaultdict(list)
    for camp_idx, seller_idx in enumerate(seller_choices):
        campaigns_by_seller[seller_idx].append(camp_idx)

    # Pre-compute each campaign's within-seller pareto weight
    campaign_within_seller_weight = {}
    for seller_idx, camp_indices in campaigns_by_seller.items():
        weights = assign_pareto_weights(
            len(camp_indices), PARETO_TOP_CAMPAIGN_SHARE, PARETO_TOP_CAMPAIGN_POWER
        )
        for camp_idx, w in zip(camp_indices, weights):
            campaign_within_seller_weight[camp_idx] = w

    max_days = (END_DATE - START_DATE).days

    for i in range(n):
        seller_idx = seller_choices[i]
        seller     = sellers[seller_idx]
        c_type     = random.choice(CAMPAIGN_TYPES)

        # Campaign runs for a random number of days (min 14, max full range)
        duration = random.randint(14, max_days)
        start_offset = random.randint(0, max_days - duration)
        c_start = START_DATE + timedelta(days=start_offset)
        c_end   = c_start + timedelta(days=duration)

        # Combined Pareto multiplier: seller-level power × within-seller campaign power.
        # Both are centered around 1.0 on average, so this scales volume up for "hero"
        # campaigns of "whale" sellers, and down for long-tail campaigns of small sellers.
        pareto_multiplier = seller["pareto_weight"] * campaign_within_seller_weight[i]

        campaigns.append({
            "campaign_id":        f"C{i+1:05d}",
            "seller_id":          seller["seller_id"],
            "country":            seller["country"],
            "campaign_type":      c_type,
            "tier":               seller["tier"],
            "start_date":         c_start,
            "end_date":           c_end,
            "pareto_multiplier":  pareto_multiplier,
        })
    return campaigns

# ── Generate daily rows for one campaign ─────────────────────────────────────
def generate_campaign_rows(campaign):
    rows = []
    c_start = campaign["start_date"]
    c_end   = min(campaign["end_date"], END_DATE)
    current = c_start

    tier        = campaign["tier"]
    country     = campaign["country"]
    c_type      = campaign["campaign_type"]
    tier_info   = TIER_TRAITS[tier]
    country_info = COUNTRY_TRAITS[country]
    type_info   = CAMPAIGN_TYPE_TRAITS[c_type]
    pareto_mult = campaign["pareto_multiplier"]   # Pareto (80/20) volume multiplier

    base_aov = tier_info["aov_base"] * country_info["aov_scale"]

    # Campaign-level random noise (stable across days for the same campaign)
    campaign_noise = np.random.uniform(0.7, 1.3)

    while current <= c_end:
        month   = current.month
        weekday = current.weekday()

        season_mult  = MONTHLY_SEASONALITY[month]
        weekday_mult = WEEKDAY_WEIGHTS[weekday]

        # Daily impressions
        base_imp = tier_info["base_impressions"]
        impressions = int(
            base_imp
            * country_info["impression_scale"]
            * type_info["impression_mult"]
            * season_mult
            * weekday_mult
            * campaign_noise
            * pareto_mult                      # Pareto (80/20) scaling
            * np.random.uniform(0.75, 1.25)   # daily jitter
        )
        impressions = max(impressions, 50)   # floor

        # CTR: 0.5% – 4%
        base_ctr = np.random.uniform(0.008, 0.035)
        ctr = base_ctr * type_info["ctr_mult"]
        ctr = np.clip(ctr, 0.005, 0.06)
        clicks = int(round(impressions * ctr))
        clicks = max(clicks, 0)

        # CVR: 1% – 8% of clicks
        base_cvr = np.random.uniform(0.015, 0.075)
        cvr = base_cvr * type_info["cvr_mult"]
        cvr = np.clip(cvr, 0.01, 0.12)
        conversions = int(round(clicks * cvr))
        conversions = max(conversions, 0)

        # Revenue and GMV
        # AOV varies daily slightly
        aov = base_aov * np.random.uniform(0.85, 1.15)
        # revenue = ad-attributed spend converted (ROAS ~2–6x implied)
        # GMV is broader: includes organic + ad-attributed orders
        gmv_multiplier = np.random.uniform(1.8, 4.5)   # GMV > revenue (halo effect)
        revenue = round(conversions * aov, 2)
        gmv     = round(revenue * gmv_multiplier, 2)

        rows.append({
            "date":          current.strftime("%Y-%m-%d"),
            "country":       country,
            "campaign_id":   campaign["campaign_id"],
            "campaign_type": campaign["campaign_type"],
            "seller_id":     campaign["seller_id"],
            "impressions":   impressions,
            "clicks":        clicks,
            "conversions":   conversions,
            "revenue":       revenue,
            "gmv":           gmv,
        })

        current += timedelta(days=1)

    return rows

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("Building seller universe...")
    sellers   = build_sellers()

    print("Building campaign universe...")
    campaigns = build_campaigns(sellers)

    print(f"Generating daily rows for {len(campaigns)} campaigns...")
    all_rows = []
    for idx, camp in enumerate(campaigns):
        all_rows.extend(generate_campaign_rows(camp))
        if (idx + 1) % 50 == 0:
            print(f"  Processed {idx + 1}/{len(campaigns)} campaigns — {len(all_rows):,} rows so far")

    df = pd.DataFrame(all_rows)

    # ── Derived sanity columns (optional — you can drop these if not needed) ──
    df["ctr"]       = (df["clicks"]      / df["impressions"].replace(0, np.nan)).round(4)
    df["cvr"]       = (df["conversions"] / df["clicks"].replace(0, np.nan)).round(4)
    df["roas"]      = (df["revenue"]     / df["clicks"].replace(0, np.nan)).round(2)   # proxy

    # ── Final column order ────────────────────────────────────────────────────
    df = df[[
        "date", "country", "campaign_id", "campaign_type", "seller_id",
        "impressions", "clicks", "conversions", "revenue", "gmv",
        "ctr", "cvr", "roas"
    ]].sort_values(["campaign_id", "date"]).reset_index(drop=True)

    out_path = "ad_campaign_data.csv"
    df.to_csv(out_path, index=False)

    # ── Summary stats ─────────────────────────────────────────────────────────
    print("\n" + "="*55)
    print("DATASET GENERATED SUCCESSFULLY")
    print("="*55)
    print(f"  Output file   : {out_path}")
    print(f"  Total rows    : {len(df):,}")
    print(f"  Date range    : {df['date'].min()}  →  {df['date'].max()}")
    print(f"  Campaigns     : {df['campaign_id'].nunique():,}")
    print(f"  Sellers       : {df['seller_id'].nunique():,}")
    print(f"  Countries     : {df['country'].nunique()}")
    print(f"  Avg CTR       : {df['ctr'].mean():.2%}")
    print(f"  Avg CVR       : {df['cvr'].mean():.2%}")
    print(f"  Total Revenue : ${df['revenue'].sum():,.0f}")
    print(f"  Total GMV     : ${df['gmv'].sum():,.0f}")
    print(f"  Avg ROAS      : {df['roas'].mean():.2f}x")

    # ── Pareto verification ───────────────────────────────────────────────────
    print("\n" + "="*55)
    print("PARETO (80/20) CHECK")
    print("="*55)

    seller_rev = df.groupby("seller_id")["revenue"].sum().sort_values(ascending=False)
    n_top_sellers = max(1, int(round(len(seller_rev) * 0.20)))
    top_seller_share = seller_rev.head(n_top_sellers).sum() / seller_rev.sum()
    print(f"  Top 20% of sellers ({n_top_sellers}/{len(seller_rev)}) drive "
          f"{top_seller_share:.1%} of total revenue")

    camp_rev = df.groupby("campaign_id")["revenue"].sum().sort_values(ascending=False)
    n_top_camps = max(1, int(round(len(camp_rev) * 0.20)))
    top_camp_share = camp_rev.head(n_top_camps).sum() / camp_rev.sum()
    print(f"  Top 20% of campaigns ({n_top_camps}/{len(camp_rev)}) drive "
          f"{top_camp_share:.1%} of total revenue")

    print("\nSample rows:")
    print(df.head(5).to_string(index=False))

if __name__ == "__main__":
    main()
