-- ====================================================================
-- TH2: Data Warehouse Architecture - Database Schemas
-- System: E-Commerce CRM/ERP Analytics & AI
-- ====================================================================

-- 1. Create Schemas
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS analytics;

-- ====================================================================
-- SCHEMA: raw
-- Raw ingestion tables (CSV / API load directly)
-- ====================================================================

DROP TABLE IF EXISTS raw.customers CASCADE;
CREATE TABLE raw.customers (
    customer_id VARCHAR(50) PRIMARY KEY,
    customer_unique_id VARCHAR(50),
    customer_name VARCHAR(100),
    customer_email VARCHAR(100),
    customer_city VARCHAR(100),
    customer_state VARCHAR(50),
    customer_country VARCHAR(50),
    created_at TIMESTAMP
);

DROP TABLE IF EXISTS raw.products CASCADE;
CREATE TABLE raw.products (
    product_id VARCHAR(50) PRIMARY KEY,
    product_category VARCHAR(100),
    product_name VARCHAR(200),
    price NUMERIC(12, 2),
    cost NUMERIC(12, 2),
    weight_g NUMERIC(10, 2)
);

DROP TABLE IF EXISTS raw.orders CASCADE;
CREATE TABLE raw.orders (
    order_id VARCHAR(50) PRIMARY KEY,
    customer_id VARCHAR(50),
    order_status VARCHAR(50),
    order_purchase_timestamp TIMESTAMP,
    order_approved_at TIMESTAMP,
    order_delivered_timestamp TIMESTAMP,
    order_estimated_delivery_date TIMESTAMP
);

DROP TABLE IF EXISTS raw.order_items CASCADE;
CREATE TABLE raw.order_items (
    order_item_id VARCHAR(50) PRIMARY KEY,
    order_id VARCHAR(50),
    product_id VARCHAR(50),
    quantity INT,
    price NUMERIC(12, 2),
    freight_value NUMERIC(12, 2),
    shipping_limit_date TIMESTAMP
);

DROP TABLE IF EXISTS raw.payments CASCADE;
CREATE TABLE raw.payments (
    payment_id VARCHAR(50) PRIMARY KEY,
    order_id VARCHAR(50),
    payment_sequential INT,
    payment_type VARCHAR(50),
    payment_installments INT,
    payment_value NUMERIC(12, 2)
);

DROP TABLE IF EXISTS raw.reviews CASCADE;
CREATE TABLE raw.reviews (
    review_id VARCHAR(50) PRIMARY KEY,
    order_id VARCHAR(50),
    review_score INT,
    review_comment_title TEXT,
    review_comment_message TEXT,
    review_creation_date TIMESTAMP
);

-- ====================================================================
-- SCHEMA: staging
-- Cleaned, deduplicated, standardized relational tables
-- ====================================================================

DROP TABLE IF EXISTS staging.dim_customers CASCADE;
CREATE TABLE staging.dim_customers (
    customer_id VARCHAR(50) PRIMARY KEY,
    customer_name VARCHAR(100),
    customer_email VARCHAR(100),
    city VARCHAR(100),
    state VARCHAR(50),
    country VARCHAR(50),
    registration_date DATE
);

DROP TABLE IF EXISTS staging.dim_products CASCADE;
CREATE TABLE staging.dim_products (
    product_id VARCHAR(50) PRIMARY KEY,
    category VARCHAR(100),
    product_name VARCHAR(200),
    unit_price NUMERIC(12, 2),
    unit_cost NUMERIC(12, 2),
    margin NUMERIC(12, 2)
);

DROP TABLE IF EXISTS staging.fact_orders CASCADE;
CREATE TABLE staging.fact_orders (
    order_id VARCHAR(50) PRIMARY KEY,
    customer_id VARCHAR(50) REFERENCES staging.dim_customers(customer_id),
    order_status VARCHAR(50),
    purchase_date DATE,
    purchase_timestamp TIMESTAMP,
    delivery_timestamp TIMESTAMP,
    delivery_days INT,
    total_amount NUMERIC(12, 2),
    total_items INT,
    payment_type VARCHAR(50)
);

DROP TABLE IF EXISTS staging.fact_order_items CASCADE;
CREATE TABLE staging.fact_order_items (
    order_item_id VARCHAR(50) PRIMARY KEY,
    order_id VARCHAR(50) REFERENCES staging.fact_orders(order_id),
    product_id VARCHAR(50) REFERENCES staging.dim_products(product_id),
    quantity INT,
    unit_price NUMERIC(12, 2),
    item_total NUMERIC(12, 2),
    freight_value NUMERIC(12, 2),
    item_profit NUMERIC(12, 2)
);

DROP TABLE IF EXISTS staging.fact_reviews CASCADE;
CREATE TABLE staging.fact_reviews (
    review_id VARCHAR(50) PRIMARY KEY,
    order_id VARCHAR(50),
    customer_id VARCHAR(50),
    rating INT,
    review_text TEXT,
    created_at TIMESTAMP
);

-- Indexes for Staging
CREATE INDEX IF NOT EXISTS idx_fact_orders_customer ON staging.fact_orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_fact_orders_date ON staging.fact_orders(purchase_date);
CREATE INDEX IF NOT EXISTS idx_fact_order_items_product ON staging.fact_order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_fact_reviews_rating ON staging.fact_reviews(rating);
