# HỆ THỐNG PHÂN TÍCH DỮ LIỆU THÔNG MINH TÍCH HỢP AI & APACHE SUPERSET (TH2)

Hệ thống Data Warehouse và Business Intelligence thông minh dành cho doanh nghiệp E-Commerce CRM/ERP, tích hợp 4 mô hình AI (Dự báo doanh thu, Phân khúc khách hàng RFM K-Means, Phân tích cảm xúc phản hồi NLP, Dự đoán nguy cơ rời bỏ Churn) và trực quan hóa qua Apache Superset Dashboard.

---

## 1. Cấu trúc Thư mục Dự án

```
th2-ai-superset/
├── data/
│   ├── generate_dataset.py       # Bộ sinh dữ liệu CRM/ERP thực tế (1500 khách hàng, 6000 đơn hàng)
│   └── raw/                      # Dữ liệu CSV thô: customers, products, orders, items, payments, reviews
├── sql/
│   ├── 01_schema.sql             # Schemas PostgreSQL: raw và staging
│   └── 02_analytics.sql          # Schemas analytics, tables & view Data Marts
├── etl/
│   ├── load_raw.py               # Ingestion dữ liệu CSV vào raw.*
│   └── transform.py              # Data cleaning, deduplication, đưa vào staging.*
├── ai/
│   ├── forecast.py               # AI #1: Dự báo doanh thu 30 ngày (Trend + Seasonality)
│   ├── segmentation.py           # AI #2: Phân khúc khách hàng RFM + K-Means
│   ├── sentiment.py              # AI #3: NLP Sentiment Analysis & Topic Extraction
│   ├── churn_predict.py          # AI #4 (Sáng tạo): Dự báo nguy cơ khách hàng rời bỏ
│   ├── evaluate.py               # Tổng hợp ma trận đánh giá hiệu quả (Accuracy, F1, RMSE, MAPE)
│   └── gemini_insights.py        # AI #5: Gemini nâng cao (insight, anomaly, playbook, text-to-sql)
├── superset/
│   ├── mcp_config.json           # Cấu hình kết nối Superset MCP Server
│   ├── bootstrap_superset.py     # Tự động đồng bộ Database & 10 Datasets
│   ├── create_charts_dashboard.py# Tự động dựng 7 Biểu đồ và Dashboard hoàn chỉnh
│   └── dashboard_export.zip      # File nén xuất khẩu Dashboard sẵn sàng Import
├── report/
│   └── BaoCao_KyThuat.md         # Báo cáo kỹ thuật chi tiết chuẩn 10 mục
└── README.md
```

---

## 2. Hướng dẫn Chạy Nhanh (Quick Start)

### Bước 1: Khởi động Hạ tầng Docker
Đảm bảo container `superset_app`, `superset_db`, `superset_cache` đang chạy:
```powershell
docker compose ps
```

### Bước 2: Thực thi Toàn bộ Pipeline Bằng 1 Lệnh Duy Nhất
Mọi logic từ nạp dữ liệu, ETL, tính toán AI và dựng Dashboard trên Superset đã được tự động hóa:

```powershell
# 1. Chạy ETL: Sinh dữ liệu & Nạp vào Data Warehouse
docker exec superset_app python /app/th2/data/generate_dataset.py
docker exec superset_app python /app/th2/etl/load_raw.py
docker exec superset_app python /app/th2/etl/transform.py

# 2. Chạy 4 Mô hình AI / Machine Learning
docker exec superset_app python /app/th2/ai/forecast.py
docker exec superset_app python /app/th2/ai/segmentation.py
docker exec superset_app python /app/th2/ai/sentiment.py
docker exec superset_app python /app/th2/ai/churn_predict.py

# 3. Xuất bảng đánh giá độ chính xác
docker exec superset_app python /app/th2/ai/evaluate.py

# 4. Tự động khởi tạo Biểu đồ & Dashboard trên Apache Superset
docker exec superset_app python /app/th2/superset/create_charts_dashboard.py
```

---

## 3. Truy cập Dashboard Apache Superset

- **Đường dẫn Dashboard:** [http://localhost:8088/superset/dashboard/13/](http://localhost:8088/superset/dashboard/13/)
- **Tài khoản đăng nhập:** `admin`
- **Mật khẩu:** `admin`

Dashboard gồm 4 phân vùng chuẩn UX/UI:
1. **KPI Tổng quan:** Tổng doanh thu thực tế, Tổng đơn hàng giao thành công.
2. **Dự báo Doanh số AI:** Doanh thu dự báo 30 ngày tiếp theo kèm dải tin cậy 95% (Upper / Lower Bound).
3. **Phân tích Khách hàng:** Cơ cấu phân khúc RFM (VIP, Trung thành, Nguy cơ, Mới) & Biểu đồ cảnh báo tỷ lệ Churn Risk.
4. **Tiếng nói Khách hàng (VoC):** Tỷ lệ cảm xúc tích cực / tiêu cực và biểu đồ phân bổ các vấn đề khiếu nại (Vận chuyển, Chất lượng, CSKH, Giá cả).

---

## 4. Tích hợp Superset MCP (Model Context Protocol)

File cấu hình MCP được đặt tại `superset/mcp_config.json`, hỗ trợ kết nối trực tiếp với Claude Desktop, Claude Code hoặc các AI Agent khác để:
- Tự động sinh truy vấn SQL bằng ngôn ngữ tự nhiên (Text-to-SQL).
- Tự động tạo biểu đồ và bảng dữ liệu theo yêu cầu thời gian thực.

---

## 5. Gemini AI Nâng cao (đa mô hình & đa phương pháp)

Script `ai/gemini_insights.py` hỗ trợ các chế độ sau:
- `all`: chạy toàn bộ suite (insight đa tầng, anomaly RCA, playbook, churn intervention, forecast scenario, text-to-sql nếu có question)
- `insight`: báo cáo theo audience `ceo|manager|analyst`
- `anomaly`: phát hiện bất thường doanh thu + giải thích nguyên nhân gốc
- `playbook`: kế hoạch hành động 30 ngày
- `intervention`: mẫu chăm sóc nhóm churn risk cao
- `scenario`: diễn giải kịch bản dự báo best/base/worst
- `text2sql`: chuyển câu hỏi nghiệp vụ thành SQL SELECT an toàn (tuỳ chọn thực thi)

Ví dụ chạy:

```powershell
# Chạy full suite và lưu report/gemini_advanced_report.md
docker exec superset_app python /app/th2/ai/gemini_insights.py --mode all

# Insight cho CEO
docker exec superset_app python /app/th2/ai/gemini_insights.py --mode insight --audience ceo

# Text-to-SQL (chỉ sinh SQL)
docker exec superset_app python /app/th2/ai/gemini_insights.py --mode text2sql --question "Top 5 phân khúc có doanh thu cao nhất?"

# Text-to-SQL và thực thi truy vấn an toàn
docker exec superset_app python /app/th2/ai/gemini_insights.py --mode text2sql --question "Doanh thu 7 ngày gần nhất theo ngày" --execute-sql
```
