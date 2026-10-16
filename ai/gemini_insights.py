"""
ai/gemini_insights.py
Advanced Gemini AI module for BI:
1) Multi-level executive insights (CEO/Manager/Analyst)
2) Anomaly detection + AI root-cause narrative
3) Action playbook and churn intervention templates
4) Forecast scenario explanation (best/base/worst)
5) Safe Text-to-SQL generation (optional SQL execution)
"""

import argparse
import json
import os
import re
import urllib.error
import urllib.request
from datetime import date

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text


def load_env():
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    env = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    env[key.strip()] = val.strip()
    return env


_ENV = load_env()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or _ENV.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL") or _ENV.get("GEMINI_MODEL", "gemini-3.8-flash")
DB_URI = (
    os.getenv("DATABASE_URL")
    or _ENV.get("DATABASE_URL")
    or "postgresql+psycopg2://superset:superset@superset_db:5432/ecommerce_dw"
)
GEMINI_FALLBACK_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
    "gemini-flash-latest",
]

FORBIDDEN_SQL_PATTERNS = [
    r"\bINSERT\b",
    r"\bUPDATE\b",
    r"\bDELETE\b",
    r"\bDROP\b",
    r"\bTRUNCATE\b",
    r"\bALTER\b",
    r"\bCREATE\b",
    r"\bGRANT\b",
    r"\bREVOKE\b",
]


def call_gemini(prompt: str, retries: int = 3, temperature: float = 0.4, max_tokens: int = 1400) -> str:
    import time

    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
        return "[LỖI] Chưa cấu hình GEMINI_API_KEY trong file .env"

    model_candidates = [GEMINI_MODEL] + [m for m in GEMINI_FALLBACK_MODELS if m != GEMINI_MODEL]

    payload = json.dumps(
        {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
        }
    ).encode("utf-8")

    for model_name in model_candidates:
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
        for attempt in range(1, retries + 1):
            req = urllib.request.Request(
                endpoint,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                print(f"  [Attempt {attempt}/{retries}] Calling Gemini API ({model_name})...")
                with urllib.request.urlopen(req, timeout=90) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    return data["candidates"][0]["content"]["parts"][0]["text"].strip()
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8")
                if exc.code == 404:
                    print(f"  [404] Model {model_name} không hỗ trợ, thử model khác...")
                    break
                if exc.code == 503 and attempt < retries:
                    wait_sec = attempt * 5
                    print(f"  [503] Server quá tải, chờ {wait_sec}s rồi thử lại...")
                    time.sleep(wait_sec)
                    continue
                if attempt < retries:
                    print(f"  [HTTP {exc.code}] retry sau 5s...")
                    time.sleep(5)
                    continue
                break
            except Exception as exc:
                if attempt < retries:
                    print(f"  [Timeout] Thử lại sau 5s... ({exc})")
                    time.sleep(5)
                    continue
                break

    return "[FAILED] Gemini API failed after trying fallback models."


def get_engine():
    return create_engine(DB_URI)


def dataframe_to_text(df: pd.DataFrame, max_rows: int = 10) -> str:
    if df.empty:
        return "(không có dữ liệu)"
    show_df = df.head(max_rows).copy()
    return show_df.to_string(index=False)


def collect_bi_context(engine):
    kpi = pd.read_sql(
        """
        SELECT
            SUM(total_revenue) AS total_revenue,
            SUM(total_orders) AS total_orders,
            ROUND(AVG(average_order_value), 0) AS avg_order_value,
            COUNT(DISTINCT purchase_date) AS active_days
        FROM analytics.vw_daily_sales_performance;
    """,
        con=engine,
    ).iloc[0]

    segment = pd.read_sql(
        """
        SELECT segment_name, COUNT(*) as count, ROUND(AVG(monetary),0) as avg_spend
        FROM analytics.customer_segments
        GROUP BY segment_name ORDER BY count DESC;
    """,
        con=engine,
    )

    sentiment = pd.read_sql(
        """
        SELECT sentiment_label, COUNT(*) as count
        FROM analytics.review_sentiment
        GROUP BY sentiment_label;
    """,
        con=engine,
    )

    topics = pd.read_sql(
        """
        SELECT primary_topic, COUNT(*) as count
        FROM analytics.review_sentiment
        GROUP BY primary_topic
        ORDER BY count DESC;
    """,
        con=engine,
    )

    churn = pd.read_sql(
        """
        SELECT churn_risk_level, COUNT(*) as count, ROUND(AVG(churn_probability), 4) as avg_prob
        FROM analytics.customer_churn_risk
        GROUP BY churn_risk_level;
    """,
        con=engine,
    )

    forecast = pd.read_sql(
        """
        SELECT ds, yhat, yhat_lower, yhat_upper
        FROM analytics.revenue_forecast
        ORDER BY ds
        LIMIT 14;
    """,
        con=engine,
    )

    recent_sales = pd.read_sql(
        """
        SELECT purchase_date, total_revenue, total_orders, average_order_value
        FROM analytics.vw_daily_sales_performance
        ORDER BY purchase_date DESC
        LIMIT 60;
    """,
        con=engine,
    ).sort_values("purchase_date")

    return {
        "kpi": kpi,
        "segment": segment,
        "sentiment": sentiment,
        "topics": topics,
        "churn": churn,
        "forecast": forecast,
        "recent_sales": recent_sales,
    }


def detect_revenue_anomalies(recent_sales: pd.DataFrame, z_threshold: float = 2.0) -> pd.DataFrame:
    df = recent_sales.copy()
    if df.empty:
        return pd.DataFrame(columns=["purchase_date", "total_revenue", "z_score", "anomaly_type"])

    revenue = df["total_revenue"].astype(float)
    mean_val = float(revenue.mean())
    std_val = float(revenue.std(ddof=0))
    if std_val == 0:
        df["z_score"] = 0.0
    else:
        df["z_score"] = (revenue - mean_val) / std_val

    df["anomaly_type"] = np.where(df["z_score"] >= z_threshold, "Spike", np.where(df["z_score"] <= -z_threshold, "Drop", "Normal"))
    anomalies = df[df["anomaly_type"] != "Normal"][["purchase_date", "total_revenue", "z_score", "anomaly_type"]].copy()
    anomalies["z_score"] = anomalies["z_score"].round(3)
    return anomalies.sort_values("purchase_date", ascending=False)


def build_multilevel_prompt(context: dict, audience: str) -> str:
    kpi = context["kpi"]
    segment = context["segment"]
    sentiment = context["sentiment"]
    topics = context["topics"]
    churn = context["churn"]
    forecast = context["forecast"]

    audience_rules = {
        "ceo": "Tối đa 180 từ, tập trung tăng trưởng, rủi ro lớn, quyết định cấp chiến lược.",
        "manager": "Khoảng 280-350 từ, nêu nguyên nhân vận hành, đề xuất hành động theo phòng ban.",
        "analyst": "Khoảng 350-450 từ, thiên về dữ liệu, nêu giả thuyết kiểm định tiếp theo.",
    }
    style = audience_rules.get(audience, audience_rules["manager"])

    return f"""
Bạn là chuyên gia phân tích kinh doanh e-commerce. Hãy viết báo cáo tiếng Việt cho cấp {audience.upper()}.
Yêu cầu phong cách: {style}

KPI:
- Tổng doanh thu: {int(kpi['total_revenue']):,} VND
- Tổng đơn hàng: {int(kpi['total_orders']):,}
- AOV: {int(kpi['avg_order_value']):,} VND
- Số ngày hoạt động: {int(kpi['active_days'])}

Phân khúc khách hàng:
{dataframe_to_text(segment, 10)}

Sentiment:
{dataframe_to_text(sentiment, 10)}

Top chủ đề phản hồi:
{dataframe_to_text(topics, 10)}

Churn:
{dataframe_to_text(churn, 10)}

Dự báo 14 ngày:
{dataframe_to_text(forecast, 14)}

Trình bày:
1) Tình hình tổng thể
2) Điểm sáng
3) Rủi ro cần cảnh báo sớm
4) 3 hành động ưu tiên 30 ngày
"""


def generate_multilevel_insights(context: dict, audiences):
    results = {}
    for audience in audiences:
        prompt = build_multilevel_prompt(context, audience)
        results[audience] = call_gemini(prompt, temperature=0.35, max_tokens=1100)
    return results


def build_anomaly_rca_prompt(context: dict, anomalies: pd.DataFrame) -> str:
    return f"""
Bạn là AI Root Cause Analyst cho hệ thống thương mại điện tử.

Các ngày doanh thu bất thường (z-score):
{dataframe_to_text(anomalies, 20)}

Bổ sung ngữ cảnh:
Phân khúc khách hàng:
{dataframe_to_text(context['segment'], 10)}

Sentiment:
{dataframe_to_text(context['sentiment'], 10)}

Top chủ đề:
{dataframe_to_text(context['topics'], 10)}

Churn:
{dataframe_to_text(context['churn'], 10)}

Hãy trả lời ngắn gọn bằng tiếng Việt:
1) 2-4 nguyên nhân gốc rễ khả dĩ nhất theo thứ tự ảnh hưởng
2) Chỉ số nào cần theo dõi hằng ngày để xác thực từng nguyên nhân
3) 3 hành động phản ứng nhanh trong 7 ngày
"""


def generate_anomaly_rca(context: dict, anomalies: pd.DataFrame) -> str:
    if anomalies.empty:
        return "Không phát hiện bất thường doanh thu theo ngưỡng z-score hiện tại."
    prompt = build_anomaly_rca_prompt(context, anomalies)
    return call_gemini(prompt, temperature=0.3, max_tokens=900)


def build_playbook_prompt(context: dict) -> str:
    return f"""
Bạn là chuyên gia growth + CRM.
Dựa trên dữ liệu:
Phân khúc khách hàng:
{dataframe_to_text(context['segment'], 10)}
Churn:
{dataframe_to_text(context['churn'], 10)}
Sentiment:
{dataframe_to_text(context['sentiment'], 10)}
Top chủ đề:
{dataframe_to_text(context['topics'], 10)}

Hãy lập playbook hành động 30 ngày bằng tiếng Việt:
- Tuần 1/2/3/4
- Mỗi tuần có: mục tiêu, hành động chính, KPI theo dõi
- Tách rõ cho 3 nhóm: giữ chân, tăng doanh thu, nâng trải nghiệm
"""


def generate_playbook(context: dict) -> str:
    return call_gemini(build_playbook_prompt(context), temperature=0.45, max_tokens=1200)


def generate_churn_intervention_templates(engine, top_n: int = 5) -> str:
    high_risk = pd.read_sql(
        f"""
        SELECT customer_id, churn_probability, total_spend, suggested_action
        FROM analytics.customer_churn_risk
        WHERE churn_risk_level = 'High Risk'
        ORDER BY churn_probability DESC
        LIMIT {int(top_n)};
    """,
        con=engine,
    )

    if high_risk.empty:
        return "Không có khách hàng High Risk để tạo mẫu can thiệp."

    prompt = f"""
Bạn là CRM retention assistant.
Dữ liệu khách hàng High Risk:
{dataframe_to_text(high_risk, top_n)}

Hãy tạo mẫu tin nhắn chăm sóc cá nhân hóa bằng tiếng Việt, gồm:
1) Mẫu Email
2) Mẫu Zalo/SMS ngắn
3) Mẫu kịch bản gọi điện 4-5 câu
Yêu cầu: lịch sự, thực tế, không hứa quá mức.
"""
    return call_gemini(prompt, temperature=0.55, max_tokens=1200)


def build_scenario_table(forecast_df: pd.DataFrame, best_uplift: float = 0.1, worst_drop: float = 0.12):
    df = forecast_df.copy()
    if df.empty:
        return pd.DataFrame(columns=["ds", "base", "best_case", "worst_case"])
    df["base"] = df["yhat"].astype(float)
    df["best_case"] = (df["base"] * (1 + best_uplift)).round(2)
    df["worst_case"] = (df["base"] * (1 - worst_drop)).round(2)
    return df[["ds", "base", "best_case", "worst_case"]]


def generate_scenario_narrative(context: dict, scenario_df: pd.DataFrame) -> str:
    prompt = f"""
Bạn là chuyên gia planning tài chính thương mại điện tử.
Kịch bản dự báo doanh thu:
{dataframe_to_text(scenario_df, 14)}

Hãy phân tích ngắn gọn:
1) Ý nghĩa 3 kịch bản (best/base/worst)
2) Trigger nào khiến chuyển từ base sang worst
3) 3 đòn bẩy để đạt best-case
"""
    return call_gemini(prompt, temperature=0.35, max_tokens=900)


def build_text_to_sql_prompt(question: str) -> str:
    schema_brief = """
Bạn chỉ được dùng SELECT query, không dùng lệnh ghi dữ liệu.
Schema chính:
- analytics.vw_daily_sales_performance(purchase_date,total_orders,active_customers,total_revenue,average_order_value,total_profit)
- analytics.customer_segments(customer_id,customer_name,recency,frequency,monetary,segment_name,segment_priority,...)
- analytics.review_sentiment(review_id,order_id,customer_id,rating,sentiment_label,polarity_score,subjectivity_score,primary_topic,...)
- analytics.customer_churn_risk(customer_id,recency_days,total_orders,total_spend,avg_rating,churn_probability,churn_risk_level,suggested_action,...)
- analytics.revenue_forecast(ds,yhat,yhat_lower,yhat_upper,trend,model_name,...)
- analytics.vw_customer_360(...)
- analytics.vw_sentiment_overview(...)
"""
    return f"""
{schema_brief}

Câu hỏi nghiệp vụ: {question}

Sinh đúng 1 câu SQL PostgreSQL thuần SELECT để trả lời.
Chỉ trả về SQL, không markdown, không giải thích.
"""


def is_safe_select_sql(sql_query: str) -> bool:
    compact = sql_query.strip().strip(";")
    if not compact:
        return False
    if not re.match(r"(?is)^\s*SELECT\b", compact):
        return False
    for pattern in FORBIDDEN_SQL_PATTERNS:
        if re.search(pattern, compact, flags=re.IGNORECASE):
            return False
    return True


def run_text_to_sql(engine, question: str, execute: bool = False):
    raw_sql = call_gemini(build_text_to_sql_prompt(question), temperature=0.1, max_tokens=500)
    cleaned_sql = raw_sql.replace("```sql", "").replace("```", "").strip()

    if not is_safe_select_sql(cleaned_sql):
        return {"sql": cleaned_sql, "executed": False, "error": "Generated SQL is not a safe SELECT query."}

    result = {"sql": cleaned_sql, "executed": False, "rows": None, "error": None}
    if execute:
        df = pd.read_sql(text(cleaned_sql), con=engine)
        result["executed"] = True
        result["rows"] = df
    return result


def save_markdown_report(content: str, filename: str):
    output_path = os.path.join(os.path.dirname(__file__), "..", "report", filename)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    return output_path


def generate_full_suite(question: str = "", execute_sql: bool = False):
    print("=== Gemini Advanced BI Suite ===")
    engine = get_engine()
    context = collect_bi_context(engine)
    anomalies = detect_revenue_anomalies(context["recent_sales"])

    multilevel = generate_multilevel_insights(context, ["ceo", "manager", "analyst"])
    rca_report = generate_anomaly_rca(context, anomalies)
    playbook = generate_playbook(context)
    interventions = generate_churn_intervention_templates(engine, top_n=5)
    scenarios = build_scenario_table(context["forecast"])
    scenario_narrative = generate_scenario_narrative(context, scenarios)

    text2sql_result = None
    if question:
        text2sql_result = run_text_to_sql(engine, question=question, execute=execute_sql)

    md = []
    md.append("# Gemini Advanced BI Report")
    md.append(f"*Tạo tự động lúc: {date.today()}*\n")
    md.append("## 1) Executive Insights - CEO")
    md.append(multilevel["ceo"])
    md.append("\n## 2) Executive Insights - Manager")
    md.append(multilevel["manager"])
    md.append("\n## 3) Analyst Insights")
    md.append(multilevel["analyst"])
    md.append("\n## 4) Revenue Anomaly + Root Cause")
    md.append(rca_report)
    md.append("\n## 5) 30-Day Playbook")
    md.append(playbook)
    md.append("\n## 6) Churn Intervention Templates")
    md.append(interventions)
    md.append("\n## 7) Forecast Scenario Narrative")
    md.append(scenario_narrative)

    if text2sql_result:
        md.append("\n## 8) Text-to-SQL")
        md.append(f"```sql\n{text2sql_result['sql']}\n```")
        if text2sql_result["error"]:
            md.append(f"\nLỗi: {text2sql_result['error']}")
        elif text2sql_result["executed"]:
            rows_df = text2sql_result["rows"]
            md.append("\nKết quả truy vấn:")
            md.append("```")
            md.append(dataframe_to_text(rows_df, 20))
            md.append("```")

    output = "\n".join(md)
    output_path = save_markdown_report(output, "gemini_advanced_report.md")
    print(f"Đã lưu báo cáo: {output_path}")
    return output


def run_mode(mode: str, audience: str = "manager", question: str = "", execute_sql: bool = False):
    engine = get_engine()
    context = collect_bi_context(engine)
    anomalies = detect_revenue_anomalies(context["recent_sales"])

    if mode == "all":
        return generate_full_suite(question=question, execute_sql=execute_sql)

    if mode == "insight":
        result = generate_multilevel_insights(context, [audience]).get(audience, "")
        path = save_markdown_report(result, f"gemini_insight_{audience}.md")
        print(f"Saved: {path}")
        return result

    if mode == "anomaly":
        result = generate_anomaly_rca(context, anomalies)
        path = save_markdown_report(result, "gemini_anomaly_rca.md")
        print(f"Saved: {path}")
        return result

    if mode == "playbook":
        result = generate_playbook(context)
        path = save_markdown_report(result, "gemini_playbook_30d.md")
        print(f"Saved: {path}")
        return result

    if mode == "intervention":
        result = generate_churn_intervention_templates(engine, top_n=5)
        path = save_markdown_report(result, "gemini_churn_intervention.md")
        print(f"Saved: {path}")
        return result

    if mode == "scenario":
        scenario_df = build_scenario_table(context["forecast"])
        result = generate_scenario_narrative(context, scenario_df)
        path = save_markdown_report(result, "gemini_forecast_scenarios.md")
        print(f"Saved: {path}")
        return result

    if mode == "text2sql":
        if not question:
            raise ValueError("Mode text2sql yêu cầu --question.")
        result = run_text_to_sql(engine, question=question, execute=execute_sql)
        report = [f"Generated SQL:\n{result['sql']}"]
        if result["error"]:
            report.append(f"Error: {result['error']}")
        elif result["executed"]:
            report.append("Result:\n" + dataframe_to_text(result["rows"], 20))
        final_text = "\n\n".join(report)
        path = save_markdown_report(final_text, "gemini_text2sql.md")
        print(f"Saved: {path}")
        return final_text

    raise ValueError(f"Mode không hợp lệ: {mode}")


def parse_args():
    parser = argparse.ArgumentParser(description="Gemini Advanced BI Insights")
    parser.add_argument(
        "--mode",
        default="all",
        choices=["all", "insight", "anomaly", "playbook", "intervention", "scenario", "text2sql"],
        help="Chọn chức năng Gemini.",
    )
    parser.add_argument(
        "--audience",
        default="manager",
        choices=["ceo", "manager", "analyst"],
        help="Audience cho mode=insight",
    )
    parser.add_argument("--question", default="", help="Business question cho mode=text2sql hoặc mode=all")
    parser.add_argument("--execute-sql", action="store_true", help="Thực thi SQL sinh ra (chỉ khi SQL an toàn).")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_mode(mode=args.mode, audience=args.audience, question=args.question, execute_sql=args.execute_sql)
