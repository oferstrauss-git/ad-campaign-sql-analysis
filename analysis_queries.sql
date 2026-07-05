-- Which campaigns and sellers drive the most revenue? 
-- Pareto Summary

WITH seller_revenue AS (
    SELECT 
        seller_id,
        ROUND(SUM(revenue), 0)  AS total_revenue
    FROM  `adtech`.ad_campaigns  
    GROUP BY seller_id
),
total_revenue_by_seller AS (
    SELECT
        seller_id,
        total_revenue,
        ROUND(SUM(total_revenue) OVER (ORDER BY total_revenue DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) * 100.0 
				/ SUM(total_revenue) OVER (), 2)                      AS running_ttl
    FROM seller_revenue
),
totals AS (
    SELECT COUNT(*) AS total_sellers FROM seller_revenue
)
SELECT
    COUNT(*)                                AS sellers_in_Pareto,
    t.total_sellers                         AS total_sellers,
    ROUND(COUNT(*) * 100.0 / t.total_sellers, 1) AS pct_of_all_sellers
FROM total_revenue_by_seller
CROSS JOIN totals t
WHERE running_ttl <= 80
GROUP BY t.total_sellers;


-- How does CTR and ConvRate vary by campaign type and country?

SELECT 
    campaign_type,
    country,
    ROUND((SUM(clicks) / SUM(impressions)) * 100,2) CTR,
    ROUND((SUM(conversions) / SUM(clicks)) * 100,2) ConvRate
FROM   `adtech`.ad_campaigns
GROUP BY country, campaign_type
ORDER BY country, campaign_type;

-- What does the conversion funnel look like across all campaigns?
-- Impression → click → conversion drop-off per campaign type by country

SELECT 
    stages.country,
    stages.campaign_type,
    stages.funnel_stage,
    stages.metric_total,
    ROUND(100.0 - (stages.metric_total / baselines.total_impressions * 100), 2) AS cumulative_drop_off_pct
FROM (
    -- Subquery 1: Calculate total impressions per campaign
    SELECT 
        country, 
        campaign_type, 
        SUM(impressions) AS total_impressions
    FROM `adtech`.ad_campaigns
    GROUP BY country, campaign_type
) AS baselines
JOIN (
    -- Subquery 2: Unpivot and stack into rows
    SELECT country, campaign_type, '1_impression' AS funnel_stage, SUM(impressions) AS metric_total 
		FROM `adtech`.ad_campaigns 
        GROUP BY country, campaign_type
UNION ALL
    SELECT country, campaign_type, '2_click', SUM(clicks) 
		FROM `adtech`.ad_campaigns 
		GROUP BY country, campaign_type
UNION ALL
    SELECT country, campaign_type, '3_conversion', SUM(conversions) 
		FROM `adtech`.ad_campaigns 
        GROUP BY country, campaign_type
) AS stages on stages.country = baselines.country and stages.campaign_type = baselines.campaign_type
ORDER BY country, campaign_type, funnel_stage;

-- Campaigns cost vs ConvRate?

WITH campaign_kpis AS (
    SELECT
        campaign_id,
        ROUND(SUM(conversions) / NULLIF(SUM(clicks), 0) * 100, 2)      AS ConvRate,
        ROUND(SUM(revenue) / NULLIF(SUM(clicks), 0), 2)                AS cpc
    FROM  `adtech`.ad_campaigns
    GROUP BY campaign_id
   -- HAVING SUM(clicks) >= 100   -- Add a minimum Clicks count to eliminate poor-performing campaigns
),
averages AS (
    SELECT AVG(cpc) AS avg_cpc, 
		   AVG(ConvRate) AS avg_ConvRate
    FROM campaign_kpis
)
SELECT
    CASE
        WHEN k.cpc > a.avg_cpc AND k.ConvRate < a.avg_ConvRate THEN 'High Cost Low ConvRate'
        WHEN k.cpc > a.avg_cpc AND k.ConvRate >= a.avg_ConvRate THEN 'High Cost High ConvRate'
        WHEN k.cpc <= a.avg_cpc AND k.ConvRate < a.avg_ConvRate THEN 'Low Cost Low ConvRate'
        WHEN k.cpc <= a.avg_cpc AND k.ConvRate >= a.avg_ConvRate THEN 'Low Cost High ConvRate'
    END                         AS performance_quadrant,
    COUNT(*)                    AS num_campaigns,
    ROUND(AVG(k.cpc), 2)        AS avg_cpc_in_group,
    ROUND(AVG(k.ConvRate), 2)        AS avg_cvr_in_group
FROM campaign_kpis k
CROSS JOIN averages a
GROUP BY performance_quadrant
ORDER BY num_campaigns DESC;

-- Which Sellers are improving their revenue the most?

WITH aggregated_totals as (
					SELECT DATE_FORMAT(date, '%Y-%m') date,
					campaign_id, 
					seller_id, 
					campaign_type,
					country, 
					sum(impressions)impressions, 
					sum(clicks)clicks,
					sum(conversions)conversions,
					round(sum(revenue),2) revenue,
					round(sum(gmv),2) spend
					FROM `adtech`.ad_campaigns 
					GROUP BY DATE_FORMAT(date, '%Y-%m'),
					campaign_id, 
					seller_id, 
					campaign_type, 
					country
                    ),
seller_monthly_totals as 
					(
					SELECT date,
							seller_id, 
							round(sum(revenue),2) seller_monthly_revenue
					FROM aggregated_totals
					GROUP BY date,
							seller_id
                    )
SELECT date,
		seller_id,
        seller_monthly_revenue,
        round((seller_monthly_revenue - lag(seller_monthly_revenue)over(partition by seller_id order by date)) /  lag(seller_monthly_revenue)over(partition by seller_id order by date) *100,2) pct_change_month_over_month
FROM seller_monthly_totals;

-- Which sellers are staying Active the longest? 12 Month Activity

WITH seller_months as 
			(
			SELECT  DISTINCT seller_id,
					country,
                    campaign_type,
					DATE_FORMAT(date, '%Y-%m-01') active_month
			FROM  `adtech`.ad_campaigns 
			)
            ,
seller_first_month AS 
			(
			SELECT
				seller_id,
				country,
				campaign_type,
				MIN(active_month) AS first_month
			FROM seller_months
			GROUP BY
				seller_id,
				country,
				campaign_type
			)
SELECT
    sf.country,
    sf.campaign_type,
    COUNT(*) AS total_sellers,
    COUNT(sm.seller_id) AS sellers_active_after_12_months,
    ROUND(COUNT(sm.seller_id) / COUNT(*)*100,2) AS pct_active_after_12_months
FROM seller_first_month sf
LEFT JOIN seller_months sm ON sf.seller_id = sm.seller_id AND sf.country = sm.country AND sf.campaign_type = sm.campaign_type
		AND sm.active_month = DATE_FORMAT(DATE_ADD(STR_TO_DATE(sf.first_month, '%Y-%m-%d'), INTERVAL 12 MONTH),'%Y-%m-01')
WHERE STR_TO_DATE(sf.first_month, '%Y-%m-%d') <= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
GROUP BY
    sf.country,
    sf.campaign_type
ORDER BY
    sf.country,
    sf.campaign_type;