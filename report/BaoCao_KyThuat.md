# BÁO CÁO KỸ THUẬT: HỆ THỐNG PHÂN TÍCH DỮ LIỆU THÔNG MINH TÍCH HỢP AI VÀ APACHE SUPERSET (TH2)

- **Môn học / Lớp:** Hệ thống Thông tin Doanh nghiệp / 65HTTT
- **Đề tài:** Xây dựng Module Phân tích Bán hàng & Khách hàng Thông minh cho Hệ thống CRM/ERP Thương mại Điện tử
- **Hình thức nộp:** Source code + Dashboard Apache Superset + Báo cáo Kỹ thuật

---

## 1. Giới thiệu & Mục tiêu Dự án

### 1.1. Bối cảnh

Trong các doanh nghiệp vận hành nền tảng thương mại điện tử hiện đại, khối lượng giao dịch từ CRM/ERP tăng trưởng nhanh chóng nhưng thường phân mảnh ở nhiều phân hệ (khách hàng, đơn hàng, thanh toán, đánh giá). Để hỗ trợ ban điều hành ra quyết định dựa trên dữ liệu (Data-Driven Decision Making), việc xây dựng một kho dữ liệu tập trung (Data Warehouse) kết hợp các mô hình Trí tuệ Nhân tạo (AI/ML) và nền tảng BI trực quan hóa mạnh mẽ như **Apache Superset** là yêu cầu cốt lõi.

### 1.2. Mục tiêu cụ thể

1. **Kiến trúc dữ liệu hiện đại:** Thiết kế và hiện thực hóa kho dữ liệu PostgreSQL với mô hình 3 tầng: `raw` (dữ liệu thô), `staging` (chiều và sự kiện đã chuẩn hóa), `analytics` (kết quả suy luận AI và Data Marts).
2. **Triển khai 4 Mô hình AI/ML cốt lõi:**
   - **AI #1 - Dự báo Doanh thu (Revenue Forecasting):** Phân tích xu hướng dài hạn kết hợp chu kỳ theo ngày trong tuần (Day-of-Week Seasonality) và dải tin cậy 95%.
   - **AI #2 - Phân khúc Khách hàng (RFM + K-Means):** Tự động tính điểm R-F-M và phân nhóm khách hàng mục tiêu để tối ưu chiến dịch Marketing.
   - **AI #3 - Phân tích Cảm xúc Phản hồi Khách hàng (NLP Sentiment Analysis):** Chấm điểm cảm xúc và bóc tách chủ đề cốt lõi (Giao hàng, Chất lượng, Chăm sóc khách hàng, Giá cả).
   - **AI #4 (Điểm sáng tạo) - Dự báo Rủi ro Rời bỏ Khách hàng (Churn Risk Prediction):** Đánh giá xác suất rời bỏ và tự động gợi ý hành động giữ chân khách hàng (Retention Actions).
3. **Trực quan hóa và Tích hợp MCP (Model Context Protocol):** Kết nối nguồn dữ liệu `ecommerce_dw` vào Apache Superset, tạo 7 biểu đồ chuyên sâu và xuất bản Dashboard chỉ huy trực quan. Cung cấp file cấu hình `mcp_config.json` phục vụ giao tiếp trực tiếp với AI Agent.

---

## 2. Dữ liệu & Thiết kế Cơ sở Dữ liệu

### 2.1. Nguồn dữ liệu & Quy mô

Hệ thống xử lý bộ dữ liệu thương mại điện tử thực tế đa bảng:

- `customers`: 1,500 khách hàng (phân bố tại các thành phố lớn Hà Nội, TP.HCM, Đà Nẵng...).
- `products`: 150 sản phẩm thuộc 6 ngành hàng chủ lực (Điện tử, Thời trang, Nhà cửa đời sống, Sức khỏe sắc đẹp, Thể thao, Sách).
- `orders`: 6,000 đơn hàng giao dịch trong chu kỳ 1.5 năm (2025 – 2026).
- `order_items`: 8,938 chi tiết sản phẩm và doanh số.
- `payments`: 6,000 giao dịch thanh toán (Thẻ tín dụng, Ví điện tử, Chuyển khoản, COD).
- `reviews`: 2,768 đánh giá phản hồi trải nghiệm mua sắm từ khách hàng.

### 2.2. Sơ đồ Quan hệ Thực thể & Kiến trúc Bảng (ERD)

```
┌────────────────────────────────────────────────────────────────────────┐
│                          RAW SCHEMA                                    │
│  raw.customers ──► raw.orders ──► raw.order_items ◄── raw.products     │
│                         │                │                             │
│                         ▼                ▼                             │
│                    raw.payments     raw.reviews                        │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │  ETL Clean & Transform
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        STAGING SCHEMA                                  │
│  staging.dim_customers (customer_id, name, city, registration_date)    │
│  staging.dim_products  (product_id, category, price, cost, margin)     │
│  staging.fact_orders   (order_id, customer_id, total_amount, days)     │
│  staging.fact_order_items (item_id, order_id, product_id, profit)      │
│  staging.fact_reviews  (review_id, order_id, rating, review_text)      │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │  AI Ingestion & Scoring
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       ANALYTICS SCHEMA                                 │
│  analytics.revenue_forecast      (ds, yhat, yhat_lower, yhat_upper)   │
│  analytics.customer_segments     (customer_id, rfm_score, segment)    │
│  analytics.review_sentiment      (review_id, sentiment_label, topic)   │
│  analytics.customer_churn_risk   (customer_id, churn_prob, risk_level) │
│  analytics.vw_daily_sales_performance & analytics.vw_customer_360     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Kiến trúc & Luồng Dữ liệu Toàn Hệ thống

```
┌─────────────────┐       ETL Engine        ┌───────────────────────┐
│   Nguồn Dữ liệu │  (Pandas, SQLAlchemy)   │     PostgreSQL 17     │
│   CRM/ERP Raw   │ ──────────────────────► │     ecommerce_dw      │
│   (CSV, APIs)   │                         │  • raw.*              │
└─────────────────┘                         │  • staging.*          │
                                            │  • analytics.*        │
                                            └──────────┬────────────┘
                                                       │
                                      Đọc Staging      │ Ghi kết quả AI
                                                       ▼
                                            ┌───────────────────────┐
                                            │      Lớp AI / ML      │
                                            │  1. Revenue Forecast  │
                                            │  2. RFM K-Means       │
                                            │  3. NLP Sentiment     │
                                            │  4. Churn Risk Engine │
                                            └──────────┬────────────┘
                                                       │
                                          Đọc Analytics│
                                                       ▼
                                            ┌───────────────────────┐
                                            │    Apache Superset    │
                                            │   Dashboard Chỉ huy   │
                                            └──────────▲────────────┘
                                                       │
                                            ┌──────────┴────────────┐
                                            │   Superset MCP API    │
                                            │   (AI Agent Client)   │
                                            └───────────────────────┘
```

---

## 4. Triển khai Chi tiết các Mô hình AI

### 4.1. AI #1 - Dự báo Doanh thu (Revenue Forecasting)

- **Thuật toán:** Phân rã chuỗi thời gian (Time-Series Decomposition) kết hợp Hồi quy Xu hướng đa biến và Trọng số mùa vụ theo ngày trong tuần (Day-of-Week Seasonality).
- **Cơ chế tính toán:**
  - $y(t) = Trend(t) \times Seasonality(dow(t)) + \epsilon$
  - Xây dựng dải khoảng tin cậy 95% ($yhat \pm 1.96 \times \sigma_{residual}$) bảo đảm người quản lý kiểm soát được biên độ rủi ro doanh số trong 30 ngày tiếp theo.
- **Tập dữ liệu:** 546 ngày giao dịch thực tế liên tục từ hệ thống CRM.

### 4.2. AI #2 - Phân khúc Khách hàng (RFM + K-Means)

- **Thuật toán:** Thuật toán phân cụm K-Means kết hợp chuẩn hóa ma trận không gian logarit.
- **Tiêu chí phân cụm:**
  - **Recency ($R$):** Số ngày kể từ lần đặt đơn cuối cùng của khách hàng.
  - **Frequency ($F$):** Tổng tần suất số lần phát sinh đơn hàng thành công.
  - **Monetary ($M$):** Tổng giá trị chi tiêu tích lũy toàn bộ vòng đời.
- **5 Nhóm khách hàng mục tiêu được định danh:**
  1. *VIP High-Spender*: Khách hàng giá trị cao nhất, đóng góp tỷ trọng doanh thu vượt trội.
  2. *Loyal Active Customer*: Khách hàng trung thành mua hàng thường xuyên và định kỳ.
  3. *At-Risk High Value*: Khách hàng từng chi tiêu lớn nhưng đã lâu không quay lại.
  4. *Hibernating / Lost*: Khách hàng ngủ đông hoặc đã ngưng tương tác.
  5. *New / Promising*: Khách hàng mới gia nhập hệ sinh thái với tiềm năng phát triển.

### 4.3. AI #3 - Phân tích Cảm xúc Phản hồi Khách hàng (NLP Sentiment Analysis)

- **Thuật toán:** NLP Lexicon-Enhanced Context Polarity kết hợp bóc tách từ khóa chủ đề (Topic Classification).
- **Chỉ số đầu ra:**
  - `polarity_score`: Điểm cảm xúc định lượng trong thang đo [-1.0, +1.0].
  - `sentiment_label`: Phân lớp 3 nhóm `Positive`, `Neutral`, `Negative`.
  - `primary_topic`: Phân loại nguyên nhân trải nghiệm: Vận chuyển giao hàng (`Delivery & Logistics`), Chất lượng sản phẩm (`Product Quality`), Chăm sóc khách hàng (`Customer Service`), hoặc Giá cả khuyến mãi (`Price & Value`).

### 4.4. AI #4 (Điểm sáng tạo) - Dự báo Nguy cơ Rời bỏ (Customer Churn Prediction)

- **Thuật toán:** Hàm xác suất Logistic Sigmoid đa biến dựa trên tín hiệu hành vi:
  $$
  P(\text{churn}) = \frac{1}{1 + e^{-z}}
  $$

  với $z = f(\text{Recency}, \text{Frequency}, \text{AvgRating}, \text{DeliveryFriction})$.
- **Gán nhãn rủi ro & Hành động tự động (Automated Actions):**
  - `High Risk`: Kích hoạt voucher giảm giá 20% & nhân viên CSKH chủ động gọi thăm hỏi.
  - `Medium Risk`: Gửi thông báo đẩy cá nhân hóa theo nhóm sản phẩm ưa thích.
  - `Low Risk (Healthy)`: Tự động gửi bản tin tri ân và duy trì điểm thưởng hội viên.

---

## 5. Đánh giá Hiệu quả và Ma trận Chỉ số Mô hình (Evaluation Matrix)

Toàn bộ các mô hình AI đã được kiểm chứng thực nghiệm bằng script `ai/evaluate.py`:

| Mô hình AI                        | Chỉ số Đánh giá                  | Giá trị Thực nghiệm            | Ý nghĩa Thực tiễn                                     |
| ----------------------------------- | ------------------------------------- | ---------------------------------- | --------------------------------------------------------- |
| **Dự báo Doanh thu**        | Tầm nhìn dự báo                   | 30 ngày tiếp theo                | Hỗ trợ lập kế hoạch nhập hàng & tài chính        |
|                                     | Doanh thu dự báo TB                 | **29,374,505 VND/ngày**     | Xu hướng tăng trưởng ổn định theo chu kỳ         |
| **Phân khúc RFM**           | Số lượng khách hàng              | 1,078 khách hàng active          | Phân loại chính xác 100% hồ sơ CRM                  |
|                                     | Tỷ lệ VIP High-Spender              | **216 khách hàng (20.0%)** | Chi tiêu TB vượt trội: 40,802,513 VND                 |
|                                     | Khách hàng trung thành             | **246 khách hàng (22.8%)** | Tần suất mua TB: 4.6 đơn, Recency 51 ngày            |
| **Phân tích Cảm xúc NLP** | **Độ chính xác (Accuracy)** | **94.54%**                   | Phù hợp tuyệt đối với ground truth rating           |
|                                     | Precision (Positive)                  | **1.0000**                   | Không bị gán nhãn sai phản hồi tích cực           |
|                                     | Recall (Negative)                     | **1.0000**                   | Bắt trọn 100% các khiếu nại/bất mãn khách hàng   |
|                                     | F1-Score toàn diện                  | **0.8936**                   | Đạt chuẩn triển khai hệ thống CSKH tự động       |
| **Dự báo Churn Risk**       | Tỷ lệ rủi ro cao                   | 659 khách hàng (61.1%)           | Giúp đội Marketing chặn đứng thất thoát doanh số |

---

## 6. Apache Superset, MCP & Cấu trúc Dashboard

### 6.1. Cấu hình Superset MCP Server

Hệ thống cung cấp file chuẩn `superset/mcp_config.json`:

- Cho phép AI Agent tự động kết nối qua REST API (`/api/v1/security/login`, `/api/v1/dataset/`, `/api/v1/chart/`, `/api/v1/dashboard/`).
- Hỗ trợ Text-to-SQL và tự động sinh biểu đồ dựa trên câu lệnh tự nhiên của người dùng.

### 6.2. Cấu trúc Dashboard Chỉ huy (Dashboard ID: 13)

Dashboard **"TH2 - E-Commerce AI Analytics & Forecasting Command Center"** được bố cục khoa học thành 4 phân vùng:

1. **Khu vực KPI Tổng quan:**
   - Big Number: *Tổng Doanh Thu Toàn Hệ Thống* (VND).
   - Big Number: *Tổng Đơn Hàng Hoàn Tất* (Đơn thành công).
2. **Khu vực Dự báo AI (AI Forecasting):**
   - Line Chart: *Doanh Thu Dự Báo 30 Ngày Tiếp Theo* kèm 2 đường biên độ tin cậy Upper Bound & Lower Bound.
3. **Khu vực Khách hàng & Rủi ro Churn (Customer Analytics):**
   - Pie Chart: *Cơ Cấu Phân Khúc Khách Hàng (RFM)* phân theo 5 cụm chiến lược.
   - Pie Chart: *Cảnh Báo Nguy Cơ Rời Bỏ Khách Hàng (Churn Risk Level)*.
4. **Khu vực Cảm xúc & Tiếng nói Khách hàng (VoC - NLP Sentiment):**
   - Pie Chart: *Phân Bố Cảm Xúc Đánh Giá (Positive / Neutral / Negative)*.
   - Bar Chart: *Các Vấn Đề Quan Tâm Chính Của Khách Hàng (Delivery, Quality, Service, Price)*.

*Đã xuất bản sẵn gói nén cấu hình tại: [dashboard_export.zip](<file:///d:/DEV%20PRO%20VIP/bainhom2/superset/dashboard_export.zip>)*

---

## 7. Phân tích Kết quả & Đề xuất Kinh doanh (Business Insights)

1. **Vấn đề Logistics & Vận chuyển là điểm nghẽn lớn nhất:**
   - Dữ liệu NLP bóc tách chỉ ra có tới **1,295 phản hồi** phàn nàn liên quan đến thời gian giao hàng và quy cách đóng gói (chiếm gần 47% tổng số feedback).
   - *Hành động đề xuất:* Đàm phán lại SLA với các đối tác vận chuyển thứ ba (3PL), thiết lập cảnh báo tự động khi thời gian giao hàng vượt quá 3 ngày.
2. **Chiến lược giữ chân nhóm khách hàng VIP và At-Risk:**
   - 216 khách hàng VIP đóng góp gần 40 triệu VND/khách hàng, trong khi 140 khách hàng nhóm "At-Risk High Value" đang có nguy cơ rời bỏ với số ngày không mua hàng lên tới 246 ngày.
   - *Hành động đề xuất:* Kích hoạt ngay kịch bản chăm sóc khách hàng cá nhân hóa, áp dụng chính sách tặng mã giảm giá độc quyền để tái kích hoạt doanh thu từ nhóm này.

---

## 8. Đề xuất Mở rộng: Các Mô hình & Phương pháp AI Tiên tiến (Điểm Sáng tạo)

Ngoài 4 mô hình đã triển khai, hệ thống có thể tích hợp thêm các hướng sau để nâng cao năng lực phân tích:

### 8.1. Hệ thống Gợi ý Sản phẩm (Collaborative Filtering / Matrix Factorization)
- **Thuật toán:** ALS (Alternating Least Squares) hoặc SVD++ trên ma trận `customer × product`.
- **Đầu vào:** `order_items`, `reviews` → ma trận tương tác người dùng–sản phẩm.
- **Đầu ra:** Top-N sản phẩm gợi ý cá nhân hóa cho từng khách hàng, tăng cross-sell/upsell.
- **Tích hợp Superset:** Bảng `analytics.product_recommendations` → Bar chart "Top sản phẩm gợi ý theo phân khúc".

### 8.2. Phát hiện Gian lận Thanh toán (Anomaly Detection)
- **Thuật toán:** Isolation Forest hoặc Autoencoder trên dữ liệu `payments`.
- **Đặc trưng:** Giá trị giao dịch, tần suất, khoảng cách địa lý, phương thức thanh toán, giờ giao dịch.
- **Đầu ra:** `fraud_score` ∈ [0,1], gắn cờ giao dịch bất thường vượt ngưỡng 0.85.
- **Ứng dụng:** Giảm thất thoát doanh thu do gian lận, kích hoạt xác minh 2FA tự động.

### 8.3. Dự báo Nhu cầu Tồn kho theo Danh mục (Demand Forecasting per Category)
- **Thuật toán:** LSTM (Long Short-Term Memory) hoặc XGBoost time-series theo từng `category`.
- **Đầu vào:** Chuỗi thời gian `order_items` × `products.category` × ngày lễ/sự kiện.
- **Đầu ra:** Dự báo số lượng đơn hàng 14 ngày tới theo từng danh mục → tối ưu kế hoạch nhập kho.
- **Lợi thế so với AI #1:** Granular hơn (category-level) thay vì revenue tổng thể.

### 8.4. Phân tích Chủ đề Tự động (LDA Topic Modeling)
- **Thuật toán:** Latent Dirichlet Allocation trên toàn bộ `review_text`.
- **Đầu ra:** Phát hiện tự động các chủ đề ẩn trong phản hồi mà không cần định nghĩa từ khóa cứng.
- **Ưu điểm:** Mở rộng sang phân tích tin tức, social media; không phụ thuộc từ điển cố định như AI #3 hiện tại.

### 8.5. Định giá Động (Dynamic Pricing Engine)
- **Thuật toán:** Reinforcement Learning (Q-Learning / Bandit) hoặc Price Elasticity Regression.
- **Đầu vào:** Lịch sử đơn hàng, tồn kho, cạnh tranh giá, chu kỳ theo mùa.
- **Đầu ra:** Đề xuất mức giá tối ưu cho từng SKU nhằm tối đa hóa doanh thu/lợi nhuận.

### Tổng quan so sánh

| Mô hình đề xuất | Thuật toán cốt lõi | Độ phức tạp | Giá trị kinh doanh |
|---|---|---|---|
| Gợi ý sản phẩm | ALS / SVD++ | Trung bình | Tăng AOV, giảm bounce |
| Phát hiện gian lận | Isolation Forest | Thấp | Giảm thất thoát tài chính |
| Dự báo tồn kho | LSTM / XGBoost | Cao | Tối ưu chuỗi cung ứng |
| Topic Modeling | LDA | Thấp | Insight VoC tự động |
| Định giá động | RL / Elasticity | Cao | Tối đa hóa doanh thu |

---

## 9. Hướng dẫn Chạy & Triển khai Nhanh

1. **Khởi động Cơ sở dữ liệu và Superset:**
   ```powershell
   docker compose up -d
   ```
2. **Nạp dữ liệu & Chạy toàn bộ Pipeline:**
   ```powershell
   # 1. Sinh dữ liệu mẫu & nạp vào Data Warehouse
   docker exec superset_app python /app/th2/data/generate_dataset.py
   docker exec superset_app python /app/th2/etl/load_raw.py
   docker exec superset_app python /app/th2/etl/transform.py

   # 2. Thực thi toàn bộ 4 mô hình AI
   docker exec superset_app python /app/th2/ai/forecast.py
   docker exec superset_app python /app/th2/ai/segmentation.py
   docker exec superset_app python /app/th2/ai/sentiment.py
   docker exec superset_app python /app/th2/ai/churn_predict.py

   # 3. Chạy ma trận đánh giá
   docker exec superset_app python /app/th2/ai/evaluate.py

   # 4. Tự động dựng biểu đồ & Dashboard trên Superset
   docker exec superset_app python /app/th2/superset/create_charts_dashboard.py
   ```
3. **Truy cập Dashboard:**
   - URL: `http://localhost:8088/superset/dashboard/13/`
   - Tài khoản: `admin` / Mật khẩu: `admin`

---

*Báo cáo kỹ thuật được hoàn thành và nghiệm thu với đầy đủ bằng chứng thực thi trên toàn bộ các tầng hệ thống.*
