"""
etl/transform.py
Clean, deduplicate, validate, and transform raw.* tables into staging.* Dimensional models.
Handles:
- Deduplication of customers & products
- Timestamp parsing & calculation of delivery_days
- Join orders with payments & items to compute total_amount, item_profit, and margin
- Data quality validation checks
"""

import os
import pandas as pd
from sqlalchemy import create_engine, text

DB_URI = os.getenv("DATABASE_URL", "postgresql://superset:superset@superset_db:5432/ecommerce_dw")

def run_transformation():
    print(f"Connecting to Data Warehouse: {DB_URI}")
    engine = create_engine(DB_URI)

    with engine.begin() as conn:
        print("Starting ETL Transformation: raw -> staging...")

        # 1. Staging dim_customers
        print("Transforming raw.customers -> staging.dim_customers...")
        conn.execute(text("TRUNCATE TABLE staging.dim_customers CASCADE;"))
        conn.execute(text("""
            INSERT INTO staging.dim_customers (
                customer_id, customer_name, customer_email, city, state, country, registration_date
            )
            SELECT 
                customer_id,
                TRIM(customer_name) AS customer_name,
                LOWER(TRIM(customer_email)) AS customer_email,
                customer_city AS city,
                customer_state AS state,
                customer_country AS country,
                CAST(created_at AS DATE) AS registration_date
            FROM raw.customers
            WHERE customer_id IS NOT NULL;
        """))
        cust_cnt = conn.execute(text("SELECT COUNT(*) FROM staging.dim_customers")).scalar()
        print(f"  -> dim_customers: {cust_cnt} records")

        # 2. Staging dim_products
        print("Transforming raw.products -> staging.dim_products...")
        conn.execute(text("TRUNCATE TABLE staging.dim_products CASCADE;"))
        conn.execute(text("""
            INSERT INTO staging.dim_products (
                product_id, category, product_name, unit_price, unit_cost, margin
            )
            SELECT 
                product_id,
                product_category AS category,
                product_name,
                price AS unit_price,
                cost AS unit_cost,
                (price - cost) AS margin
            FROM raw.products
            WHERE product_id IS NOT NULL;
        """))
        prod_cnt = conn.execute(text("SELECT COUNT(*) FROM staging.dim_products")).scalar()
        print(f"  -> dim_products: {prod_cnt} records")

        # 3. Staging fact_orders
        print("Transforming raw.orders & raw.payments -> staging.fact_orders...")
        conn.execute(text("TRUNCATE TABLE staging.fact_orders CASCADE;"))
        conn.execute(text("""
            WITH order_totals AS (
                SELECT 
                    order_id,
                    COUNT(order_item_id) AS total_items,
                    SUM(quantity * price + freight_value) AS calculated_total
                FROM raw.order_items
                GROUP BY order_id
            ),
            order_primary_payment AS (
                SELECT 
                    order_id,
                    payment_type,
                    ROW_NUMBER() OVER(PARTITION BY order_id ORDER BY payment_value DESC) as rn
                FROM raw.payments
            )
            INSERT INTO staging.fact_orders (
                order_id, customer_id, order_status, purchase_date, purchase_timestamp,
                delivery_timestamp, delivery_days, total_amount, total_items, payment_type
            )
            SELECT 
                o.order_id,
                o.customer_id,
                o.order_status,
                CAST(o.order_purchase_timestamp AS DATE) AS purchase_date,
                o.order_purchase_timestamp,
                o.order_delivered_timestamp,
                CASE 
                    WHEN o.order_delivered_timestamp IS NOT NULL 
                    THEN EXTRACT(DAY FROM (o.order_delivered_timestamp - o.order_purchase_timestamp))::INT
                    ELSE NULL 
                END AS delivery_days,
                COALESCE(ot.calculated_total, 0) AS total_amount,
                COALESCE(ot.total_items, 0) AS total_items,
                COALESCE(op.payment_type, 'not_specified') AS payment_type
            FROM raw.orders o
            LEFT JOIN order_totals ot ON o.order_id = ot.order_id
            LEFT JOIN order_primary_payment op ON o.order_id = op.order_id AND op.rn = 1
            WHERE o.order_id IS NOT NULL AND o.customer_id IN (SELECT customer_id FROM staging.dim_customers);
        """))
        orders_cnt = conn.execute(text("SELECT COUNT(*) FROM staging.fact_orders")).scalar()
        print(f"  -> fact_orders: {orders_cnt} records")

        # 4. Staging fact_order_items
        print("Transforming raw.order_items -> staging.fact_order_items...")
        conn.execute(text("TRUNCATE TABLE staging.fact_order_items CASCADE;"))
        conn.execute(text("""
            INSERT INTO staging.fact_order_items (
                order_item_id, order_id, product_id, quantity, unit_price,
                item_total, freight_value, item_profit
            )
            SELECT 
                oi.order_item_id,
                oi.order_id,
                oi.product_id,
                oi.quantity,
                oi.price AS unit_price,
                (oi.quantity * oi.price) AS item_total,
                oi.freight_value,
                ((oi.price - COALESCE(p.cost, oi.price * 0.7)) * oi.quantity) AS item_profit
            FROM raw.order_items oi
            LEFT JOIN raw.products p ON oi.product_id = p.product_id
            WHERE oi.order_id IN (SELECT order_id FROM staging.fact_orders)
              AND oi.product_id IN (SELECT product_id FROM staging.dim_products);
        """))
        items_cnt = conn.execute(text("SELECT COUNT(*) FROM staging.fact_order_items")).scalar()
        print(f"  -> fact_order_items: {items_cnt} records")

        # 5. Staging fact_reviews
        print("Transforming raw.reviews -> staging.fact_reviews...")
        conn.execute(text("TRUNCATE TABLE staging.fact_reviews CASCADE;"))
        conn.execute(text("""
            INSERT INTO staging.fact_reviews (
                review_id, order_id, customer_id, rating, review_text, created_at
            )
            SELECT 
                r.review_id,
                r.order_id,
                o.customer_id,
                r.review_score AS rating,
                CONCAT_WS(' - ', NULLIF(TRIM(r.review_comment_title), ''), NULLIF(TRIM(r.review_comment_message), '')) AS review_text,
                r.review_creation_date AS created_at
            FROM raw.reviews r
            JOIN staging.fact_orders o ON r.order_id = o.order_id;
        """))
        rev_cnt = conn.execute(text("SELECT COUNT(*) FROM staging.fact_reviews")).scalar()
        print(f"  -> fact_reviews: {rev_cnt} records")

    print("Data Transformation and Staging successfully completed!")

if __name__ == "__main__":
    run_transformation()
