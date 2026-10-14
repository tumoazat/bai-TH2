"""
ai/sentiment.py
NLP Customer Review Sentiment Analysis and Topic Categorization.
Capabilities:
1. Calculates Polarity (-1 to 1) and Subjectivity (0 to 1)
2. Assigns Sentiment Class: Positive, Neutral, Negative
3. Topic Detection via Keyword Rule matching (Delivery, Quality, Service, Price)
4. Stores enriched sentiment telemetry into analytics.review_sentiment
"""

import os
import re
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text

DB_URI = os.getenv("DATABASE_URL", "postgresql://superset:superset@superset_db:5432/ecommerce_dw")

# Vietnamese & English keyword rule dictionaries for topic tagging
TOPIC_KEYWORDS = {
    "Delivery & Logistics": ["giao hàng", "chậm", "nhanh", "vận chuyển", "đóng gói", "móp", "ship", "shipper", "hộp"],
    "Product Quality": ["chất lượng", "mượt", "hỏng", "lỗi", "chính hãng", "xịn", "kém", "bảo hành", "mô tả", "hoàn thiện"],
    "Customer Service": ["tổng đài", "hỗ trợ", "tư vấn", "thái độ", "nhân viên", "chăm sóc", "trả lời", "nhiệt tình"],
    "Price & Value": ["giá", "rẻ", "đắt", "túi tiền", "khuyến mãi", "ưu đãi", "mềm", "tiết kiệm"]
}

def analyze_review_text(text_val, rating):
    text_clean = str(text_val).lower() if pd.notnull(text_val) else ""
    
    # Rating-grounded polarity baseline
    # 5 -> +0.8, 4 -> +0.4, 3 -> 0.0, 2 -> -0.4, 1 -> -0.8
    base_polarity = (rating - 3) / 2.5
    
    # Adjustment with explicit positive/negative lexicons
    pos_words = ["tuyệt vời", "hài lòng", "chất lượng", "đẹp", "nhanh", "mượt", "yêu thích", "xuất sắc", "5 sao"]
    neg_words = ["kém", "chậm", "lỗi", "thất vọng", "tệ", "hỏng", "khác", "móp", "bực"]

    pos_hits = sum(1 for w in pos_words if w in text_clean)
    neg_hits = sum(1 for w in neg_words if w in text_clean)

    adjustment = (pos_hits * 0.15) - (neg_hits * 0.20)
    final_polarity = float(np.clip(base_polarity + adjustment, -1.0, 1.0))
    subjectivity = float(np.clip(0.3 + (pos_hits + neg_hits) * 0.15, 0.1, 0.95))

    if final_polarity > 0.15:
        sentiment = "Positive"
    elif final_polarity < -0.15:
        sentiment = "Negative"
    else:
        sentiment = "Neutral"

    # Detect primary topic
    detected_topic = "General Experience"
    max_matches = 0
    for topic, kws in TOPIC_KEYWORDS.items():
        matches = sum(1 for kw in kws if kw in text_clean)
        if matches > max_matches:
            max_matches = matches
            detected_topic = topic

    return sentiment, round(final_polarity, 4), round(subjectivity, 4), detected_topic

def run_sentiment_analysis():
    print("=== [AI #3] NLP Sentiment Analysis on Reviews ===")
    engine = create_engine(DB_URI)

    query = "SELECT review_id, order_id, customer_id, rating, review_text FROM staging.fact_reviews;"
    df = pd.read_sql(query, con=engine)
    print(f"Loaded {len(df)} customer reviews from staging.fact_reviews.")

    results = []
    for _, row in df.iterrows():
        s_label, pol, subj, topic = analyze_review_text(row['review_text'], row['rating'])
        results.append({
            'review_id': row['review_id'],
            'order_id': row['order_id'],
            'customer_id': row['customer_id'],
            'rating': row['rating'],
            'review_text': row['review_text'],
            'sentiment_label': s_label,
            'polarity_score': pol,
            'subjectivity_score': subj,
            'primary_topic': topic
        })

    df_results = pd.DataFrame(results)
    
    print("\nSentiment Distribution:")
    print(df_results['sentiment_label'].value_counts(normalize=True).round(3) * 100)
    print("\nTopic Breakdown:")
    print(df_results['primary_topic'].value_counts())

    print("Saving sentiment telemetry into analytics.review_sentiment...")
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE analytics.review_sentiment;"))
        df_results.to_sql('review_sentiment', con=conn, schema='analytics', if_exists='append', index=False)

    print(f"Successfully scored {len(df_results)} reviews!")
    return df_results

if __name__ == "__main__":
    run_sentiment_analysis()
