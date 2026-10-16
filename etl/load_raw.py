"""
etl/load_raw.py
Ingest CSV files from data/raw into PostgreSQL schema raw.*
Using pandas chunking and SQLAlchemy copy/insert for maximum throughput.
"""

import os
import pandas as pd
from sqlalchemy import create_engine, text

DB_URI = os.getenv("DATABASE_URL", "postgresql://superset:superset@superset_db:5432/ecommerce_dw")

def load_raw_data(data_dir=None):
    if data_dir is None:
        data_dir = os.getenv("RAW_DATA_DIR", "/app/th2/data/raw")

    print(f"Connecting to Data Warehouse: {DB_URI}")
    engine = create_engine(DB_URI)
    
    table_files = [
        ("customers", os.path.join(data_dir, "customers.csv")),
        ("products", os.path.join(data_dir, "products.csv")),
        ("orders", os.path.join(data_dir, "orders.csv")),
        ("order_items", os.path.join(data_dir, "order_items.csv")),
        ("payments", os.path.join(data_dir, "payments.csv")),
        ("reviews", os.path.join(data_dir, "reviews.csv"))
    ]

    with engine.begin() as conn:
        for table_name, file_path in table_files:
            if not os.path.exists(file_path):
                print(f"[WARN] File not found: {file_path}, skipping.")
                continue

            print(f"Loading {file_path} into raw.{table_name}...")
            df = pd.read_csv(file_path)
            
            # Truncate existing raw table
            conn.execute(text(f"TRUNCATE TABLE raw.{table_name} CASCADE;"))
            
            # Write to SQL
            df.to_sql(table_name, con=conn, schema="raw", if_exists="append", index=False, chunksize=2000)
            
            # Verify count
            res = conn.execute(text(f"SELECT COUNT(*) FROM raw.{table_name}")).scalar()
            print(f"  -> Successfully loaded {res} records into raw.{table_name}")

    print("Raw ingestion complete!")

if __name__ == "__main__":
    load_raw_data()
