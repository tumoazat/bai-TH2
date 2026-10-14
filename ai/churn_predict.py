"""
ai/churn_predict.py
Customer Churn Prediction (Logistic Probability Model).
Predicts churn likelihood (> 90 days inactivity) using behavioral scoring
(Orders, Spend, Rating, Delivery friction) with zero heavy dependencies.
Persists into analytics.customer_churn_risk.
"""

import os
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text

DB_URI = os.getenv("DATABASE_URL", "postgresql://superset:superset@superset_db:5432/ecommerce_dw")

def sigmoid(z):
    return 1 / (1 + np.exp(-np.clip(z, -15, 15)))

def run_churn_prediction():
    print("=== [AI #4] Customer Churn Risk Prediction ===")
    engine = create_engine(DB_URI)

    query = """
        WITH max_date AS (
            SELECT MAX(purchase_date) AS current_date FROM staging.fact_orders
        ),
        customer_history AS (
            SELECT 
                c.customer_id,
                (m.current_date - MAX(o.purchase_date))::INT AS recency_days,
                COUNT(DISTINCT o.order_id) AS total_orders,
                COALESCE(SUM(o.total_amount), 0) AS total_spend,
                COALESCE(AVG(o.delivery_days), 3) AS avg_delivery_days,
                COALESCE(AVG(r.rating), 4.0) AS avg_rating
            FROM staging.dim_customers c
            CROSS JOIN max_date m
            LEFT JOIN staging.fact_orders o ON c.customer_id = o.customer_id
            LEFT JOIN staging.fact_reviews r ON c.customer_id = r.customer_id
            WHERE o.order_status = 'delivered'
            GROUP BY c.customer_id, m.current_date
        )
        SELECT * FROM customer_history
        WHERE total_orders > 0;
    """
    df = pd.read_sql(query, con=engine)
    print(f"Loaded {len(df)} customers with transactional history.")

    # Churn Scoring formula (Empirically calibrated logistic function)
    # Higher recency & lower orders/rating increase churn probability
    z = (
        0.04 * (df['recency_days'] - 45)
        - 0.35 * (df['total_orders'] - 2)
        - 0.50 * (df['avg_rating'] - 3.5)
        + 0.15 * (df['avg_delivery_days'] - 3.0)
    )
    df['churn_probability'] = np.round(sigmoid(z), 4)

    def assign_action(row):
        prob = row['churn_probability']
        spend = row['total_spend']
        if prob >= 0.70:
            risk = "High Risk"
            action = "Kích hoạt mã giảm 20% & CSKH gọi thăm hỏi" if spend > 5000000 else "Gửi email tự động voucher kích hoạt"
        elif prob >= 0.40:
            risk = "Medium Risk"
            action = "Gửi thông báo đẩy sản phẩm bán chạy theo sở thích"
        else:
            risk = "Low Risk (Healthy)"
            action = "Duy trì bản tin và quyền lợi khách hàng thân thiết"
        return risk, action

    risk_action = df.apply(assign_action, axis=1)
    df['churn_risk_level'] = [item[0] for item in risk_action]
    df['suggested_action'] = [item[1] for item in risk_action]

    print("\nChurn Risk Breakdown:")
    print(df['churn_risk_level'].value_counts())

    print("Saving churn predictions into analytics.customer_churn_risk...")
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE analytics.customer_churn_risk;"))
        df[['customer_id', 'recency_days', 'total_orders', 'total_spend', 'avg_rating',
            'churn_probability', 'churn_risk_level', 'suggested_action']].to_sql(
            'customer_churn_risk', con=conn, schema='analytics', if_exists='append', index=False
        )

    print("Successfully completed Churn Prediction!")

if __name__ == "__main__":
    run_churn_prediction()
