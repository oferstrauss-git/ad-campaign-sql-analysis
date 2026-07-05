# ad-campaign-sql-analysis
# Ad Campaign Performance — SQL Analysis

## Business Context
A simulated ad-tech retail platform running campaigns across 10 countries,
400 campaigns, and 115 sellers. The goal is to understand campaign efficiency,
seller performance distribution, and conversion funnel health.

## Dataset
- 110,000+ daily rows generated in Python
- Columns: date, country, campaign_id, campaign_type, seller_id,
  impressions, clicks, conversions, revenue, gmv
- Date range: Jan 2023 – Jun 2024

## Key Questions Answered
- Which campaigns and sellers drive the most revenue? (Pareto/80-20 analysis)
- How does CTR and ConvRate vary by campaign type and country?
- What does the conversion funnel look like across all campaigns?
- Which campaigns are low-cost and high-converting?
- Which Sellers are improving their revenue the most?
- Which sellers are staying Active the longest?
- Rolling 3 month ROAS per seller

## Tools
MySQL · Advanced SQL (CTEs, Window Functions, Subqueries, Aggregations)

## Files

| File | Description |
|---|---|
| [generate_dataset.py](generate_dataset.py) | Python script that generates the synthetic dataset |
| [analysis_queries.sql](analysis_queries.sql) | All analytical SQL queries with comments |
| [data_sample.csv](data_sample.csv) | First 500 rows of the dataset |

## Query Results

### Pareto — Top Sellers by Revenue
![Pareto Campaigns](results/Pareto_campaigns.png)

### CTR and ConvRate by campaign type and country
![CTR_ConvRate Summary](results/CTR_vs_ConvRate.png)

### Conversion Funnel
![Conversion_Funnel](results/Conversion_Funnel.png)

### Campaign Cost vs Conversion Rate
![Campaign_cost_vs_ConvRate](results/Campaign_cost_vs_ConvRate.png)

### Changes in Seller's Revenue
![Sellers_revenue_change](results/Sellers_revenue_change.png)

### Seller's Active over 12 months
![Seller_Activity](results/Seller_Activity.png)

### Rolling 3-month Seller ROAS
![ROAS_rolling_average](results/ROAS_rolling_average.png)

