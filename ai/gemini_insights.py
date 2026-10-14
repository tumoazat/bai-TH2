"""
ai/gemini_insights.py
LLM Insight Generator using Google Gemini API.
Sáng tạo #6 & #7 trong TH2:
  - Đọc số liệu KPI từ analytics schema
  - Gọi Gemini API để sinh nhận xét tự động tiếng Việt
  - Trả về báo cáo AI insight có thể nhúng vào Superset hoặc in ra báo cáo
"""

import os
import json
import urllib.request
import urllib.error
import pandas as pd
from sqlalchemy import create_engine
from datetime import date

# Load key từ .env (không hardcode trong code)
def load_env():
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    env = {}
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    env[k.strip()] = v.strip()
    return env

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or load_env().get("GEMINI_API_KEY", "")
DB_URI = os.getenv("DATABASE_URL", "postgresql://superset:superset@superset_db:5432/ecommerce_dw")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

def call_gemini(prompt: str) -> str:
    """Gọi Gemini API với prompt và trả về nội dung text."""
    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
        return "[LỖI] Chưa cấu hình GEMINI_API_KEY trong file .env"

    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 1024
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        GEMINI_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except urllib.error.HTTPError as e:
        return f"[API ERROR {e.code}] {e.read().decode('utf-8')}"
    except Exception as e:
        return f"[ERROR] {str(e)}"

def generate_dashboard_insights():
    """Đọc dữ liệu thực từ PostgreSQL và gọi Gemini để sinh báo cáo insight tiếng Việt."""
    print("=== [AI Sáng tạo #6 & #7] Gemini LLM Dashboard Insight Generator ===")
    engine = create_engine(DB_URI)

    # 1. Thu thập số liệu KPI tổng hợp
    kpi = pd.read_sql("""
        SELECT
            SUM(total_revenue) AS total_revenue,
            SUM(total_orders) AS total_orders,
            ROUND(AVG(average_order_value), 0) AS avg_order_value,
            COUNT(DISTINCT purchase_date) AS active_days
        FROM analytics.vw_daily_sales_performance;
    """, con=engine).iloc[0]

    segment = pd.read_sql("""
        SELECT segment_name, COUNT(*) as count, ROUND(AVG(monetary),0) as avg_spend
        FROM analytics.customer_segments
        GROUP BY segment_name ORDER BY count DESC;
    """, con=engine)

    sentiment = pd.read_sql("""
        SELECT sentiment_label, COUNT(*) as count
        FROM analytics.review_sentiment
        GROUP BY sentiment_label;
    """, con=engine)

    churn = pd.read_sql("""
        SELECT churn_risk_level, COUNT(*) as count
        FROM analytics.customer_churn_risk
        GROUP BY churn_risk_level;
    """, con=engine)

    forecast = pd.read_sql("""
        SELECT ds, yhat FROM analytics.revenue_forecast
        ORDER BY ds LIMIT 7;
    """, con=engine)

    # 2. Build prompt gọi Gemini
    prompt = f"""
Bạn là chuyên gia phân tích kinh doanh thương mại điện tử. Dưới đây là số liệu thực tế từ hệ thống CRM/ERP:

**KPI Tổng quan:**
- Tổng doanh thu: {int(kpi['total_revenue']):,} VND
- Tổng đơn hàng hoàn tất: {int(kpi['total_orders']):,} đơn
- Giá trị đơn hàng trung bình (AOV): {int(kpi['avg_order_value']):,} VND

**Phân khúc khách hàng (RFM K-Means):**
{segment.to_string(index=False)}

**Phân tích cảm xúc đánh giá (NLP):**
{sentiment.to_string(index=False)}

**Nguy cơ rời bỏ (Churn Risk):**
{churn.to_string(index=False)}

**Dự báo doanh thu 7 ngày tới:**
{forecast.to_string(index=False)}

Hãy viết một báo cáo phân tích ngắn gọn (khoảng 300 từ) bằng tiếng Việt gồm:
1. Đánh giá tổng thể tình hình kinh doanh
2. Điểm mạnh cần phát huy
3. Rủi ro cần chú ý (dựa trên churn risk và sentiment)
4. 3 hành động kinh doanh cụ thể cần làm ngay trong 30 ngày tới
Viết ngắn gọn, súc tích như một báo cáo thực tế cho ban giám đốc.
"""

    print("\nĐang gọi Gemini API để phân tích...")
    insight = call_gemini(prompt)

    print("\n" + "="*60)
    print("📊 BÁO CÁO PHÂN TÍCH TỪ GEMINI AI")
    print("="*60)
    print(insight)
    print("="*60)

    # 3. Lưu kết quả ra file markdown
    output_path = os.path.join(os.path.dirname(__file__), '..', 'report', 'gemini_insight.md')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"# Báo Cáo AI Insight - Gemini LLM\n")
        f.write(f"*Tạo tự động lúc: {date.today()}*\n\n")
        f.write(insight)
    print(f"\nĐã lưu insight ra: report/gemini_insight.md")

    return insight

if __name__ == "__main__":
    generate_dashboard_insights()
