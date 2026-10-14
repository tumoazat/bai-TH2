-- ====================================================================
-- SCHEMA: analytics
-- AI scoring, forecasts, clusters, sentiments, and business views
-- ====================================================================

-- 1. AI Forecast Results
DROP TABLE IF EXISTS analytics.revenue_forecast CASCADE;
CREATE TABLE analytics.revenue_forecast (
    ds DATE PRIMARY KEY,
    yhat NUMERIC(14, 2),
    yhat_lower NUMERIC(14, 2),
    yhat_upper NUMERIC(14, 2),
    trend NUMERIC(14, 2),
    model_name VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. AI Customer Segmentation (RFM + K-Means)
DROP TABLE IF EXISTS analytics.customer_segments CASCADE;
CREATE TABLE analytics.customer_segments (
    customer_id VARCHAR(50) PRIMARY KEY,
    customer_name VARCHAR(100),
    recency INT,
    frequency INT,
    monetary NUMERIC(14, 2),
    r_score INT,
    f_score INT,
    m_score INT,
    rfm_score INT,
    cluster_id INT,
    segment_name VARCHAR(100),
    segment_priority INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. AI Sentiment Analysis (NLP on Customer Reviews)
DROP TABLE IF EXISTS analytics.review_sentiment CASCADE;
CREATE TABLE analytics.review_sentiment (
    review_id VARCHAR(50) PRIMARY KEY,
    order_id VARCHAR(50),
    customer_id VARCHAR(50),
    rating INT,
    review_text TEXT,
    sentiment_label VARCHAR(50), -- Positive, Neutral, Negative
    polarity_score NUMERIC(6, 4),
    subjectivity_score NUMERIC(6, 4),
    primary_topic VARCHAR(100),  -- Delivery, Product Quality, Customer Service, Price
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. AI Churn Prediction (Creative Feature)
DROP TABLE IF EXISTS analytics.customer_churn_risk CASCADE;
CREATE TABLE analytics.customer_churn_risk (
    customer_id VARCHAR(50) PRIMARY KEY,
    recency_days INT,
    total_orders INT,
    total_spend NUMERIC(14, 2),
    avg_rating NUMERIC(4, 2),
    churn_probability NUMERIC(6, 4),
    churn_risk_level VARCHAR(50), -- Low, Medium, High Risk
    suggested_action VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. Business KPI Mart View (Aggregated for Superset Dashboard)
DROP VIEW IF EXISTS analytics.vw_daily_sales_performance CASCADE;
CREATE OR REPLACE VIEW analytics.vw_daily_sales_performance AS
SELECT 
    f.purchase_date,
    COUNT(DISTINCT f.order_id) AS total_orders,
    COUNT(DISTINCT f.customer_id) AS active_customers,
    SUM(f.total_amount) AS total_revenue,
    ROUND(AVG(f.total_amount), 2) AS average_order_value,
    SUM(foi.item_profit) AS total_profit
FROM staging.fact_orders f
LEFT JOIN staging.fact_order_items foi ON f.order_id = foi.order_id
GROUP BY f.purchase_date;

-- 6. Customer 360 View combining CRM, Segmentation & Churn
DROP VIEW IF EXISTS analytics.vw_customer_360 CASCADE;
CREATE OR REPLACE VIEW analytics.vw_customer_360 AS
SELECT 
    c.customer_id,
    c.customer_name,
    c.city,
    c.state,
    s.recency,
    s.frequency,
    s.monetary,
    s.segment_name,
    r.churn_probability,
    r.churn_risk_level,
    r.suggested_action
FROM staging.dim_customers c
LEFT JOIN analytics.customer_segments s ON c.customer_id = s.customer_id
LEFT JOIN analytics.customer_churn_risk r ON c.customer_id = r.customer_id;

-- 7. Sentiment & Quality View
DROP VIEW IF EXISTS analytics.vw_sentiment_overview CASCADE;
CREATE OR REPLACE VIEW analytics.vw_sentiment_overview AS
SELECT 
    rs.review_id,
    rs.rating,
    rs.sentiment_label,
    rs.polarity_score,
    rs.primary_topic,
    p.category,
    p.product_name,
    fo.purchase_date
FROM analytics.review_sentiment rs
JOIN staging.fact_orders fo ON rs.order_id = fo.order_id
JOIN staging.fact_order_items foi ON fo.order_id = foi.order_id
JOIN staging.dim_products p ON foi.product_id = p.product_id;
