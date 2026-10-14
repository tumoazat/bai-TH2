"""
ai/segmentation.py
Customer Segmentation using RFM (Recency, Frequency, Monetary) & K-Means Clustering
implemented in pure NumPy & Pandas (standard Lloyd's algorithm).
Calculates RFM quintiles, cluster assignments, and business semantic labels.
Persists into analytics.customer_segments.
"""

import os
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text

DB_URI = os.getenv("DATABASE_URL", "postgresql://superset:superset@superset_db:5432/ecommerce_dw")

def kmeans_numpy(X, k=4, max_iters=100, seed=42):
    np.random.seed(seed)
    # Randomly initialize centroids
    indices = np.random.choice(len(X), size=k, replace=False)
    centroids = X[indices].copy()

    for _ in range(max_iters):
        # Compute distances from all points to centroids
        distances = np.linalg.norm(X[:, np.newaxis] - centroids, axis=2)
        labels = np.argmin(distances, axis=1)

        # Update centroids
        new_centroids = np.array([X[labels == j].mean(axis=0) if np.any(labels == j) else centroids[j] for j in range(k)])
        if np.allclose(centroids, new_centroids, atol=1e-4):
            break
        centroids = new_centroids

    return labels, centroids

def run_customer_segmentation():
    print("=== [AI #2] Customer Segmentation (RFM + K-Means) ===")
    engine = create_engine(DB_URI)

    query = """
        WITH max_date AS (
            SELECT MAX(purchase_date) AS snapshot_date FROM staging.fact_orders
        ),
        customer_rfm AS (
            SELECT 
                c.customer_id,
                c.customer_name,
                (m.snapshot_date - MAX(o.purchase_date))::INT AS recency,
                COUNT(DISTINCT o.order_id) AS frequency,
                COALESCE(SUM(o.total_amount), 0) AS monetary
            FROM staging.dim_customers c
            CROSS JOIN max_date m
            LEFT JOIN staging.fact_orders o ON c.customer_id = o.customer_id
            WHERE o.order_status = 'delivered'
            GROUP BY c.customer_id, c.customer_name, m.snapshot_date
        )
        SELECT * FROM customer_rfm
        WHERE frequency > 0 AND monetary > 0;
    """
    df = pd.read_sql(query, con=engine)
    print(f"Loaded {len(df)} active customers with transactional history.")

    # 1. RFM Scoring (1 to 5)
    df['r_score'] = pd.qcut(df['recency'], q=5, labels=[5, 4, 3, 2, 1]).astype(int)
    df['f_score'] = pd.qcut(df['frequency'].rank(method='first'), q=5, labels=[1, 2, 3, 4, 5]).astype(int)
    df['m_score'] = pd.qcut(df['monetary'], q=5, labels=[1, 2, 3, 4, 5]).astype(int)
    df['rfm_score'] = df['r_score'] * 100 + df['f_score'] * 10 + df['m_score']

    # 2. Standardization & Clustering
    features = np.log1p(df[['recency', 'frequency', 'monetary']].values)
    mean = np.mean(features, axis=0)
    std = np.std(features, axis=0)
    std[std == 0] = 1.0
    scaled_features = (features - mean) / std

    labels, centroids = kmeans_numpy(scaled_features, k=4)
    df['cluster_id'] = labels

    # 3. Assign Semantic Business Segments
    def assign_segment(row):
        m = row['monetary']
        r = row['recency']
        f = row['frequency']
        if m >= df['monetary'].quantile(0.80):
            return "VIP High-Spender", 1
        elif r <= df['recency'].median() and f >= df['frequency'].median():
            return "Loyal Active Customer", 2
        elif r > df['recency'].median() and m >= df['monetary'].median():
            return "At-Risk High Value", 3
        elif r > df['recency'].median():
            return "Hibernating / Lost", 4
        else:
            return "New / Promising", 5

    res = df.apply(assign_segment, axis=1)
    df['segment_name'] = [item[0] for item in res]
    df['segment_priority'] = [item[1] for item in res]

    print("\nSegment Distribution:")
    print(df['segment_name'].value_counts())

    # 4. Save to analytics.customer_segments
    print("Saving segmentation results to analytics.customer_segments...")
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE analytics.customer_segments;"))
        df[['customer_id', 'customer_name', 'recency', 'frequency', 'monetary',
            'r_score', 'f_score', 'm_score', 'rfm_score', 'cluster_id',
            'segment_name', 'segment_priority']].to_sql(
            'customer_segments', con=conn, schema='analytics', if_exists='append', index=False
        )

    print(f"Successfully saved {len(df)} segmented customers!")

if __name__ == "__main__":
    run_customer_segmentation()
