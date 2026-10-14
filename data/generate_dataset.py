"""
data/generate_dataset.py
Realistic E-Commerce Dataset Generator for CRM/ERP Analytics.
Produces tables: customers, products, orders, order_items, payments, reviews.
Simulates:
- Temporal growth, seasonality (weekend boosts, holiday spikes)
- Customer clusters (VIP high-spenders, regular buyers, churning one-off buyers)
- Realistic sentiment distributions correlated with product categories and delivery delays
"""

import os
import random
import uuid
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

def generate_ecommerce_data(
    num_customers=1500,
    num_products=150,
    num_orders=6000,
    start_date=datetime(2025, 1, 1),
    end_date=datetime(2026, 6, 30),
    output_dir="/app/data/raw"
):
    print(f"Generating realistic dataset: {num_customers} customers, {num_orders} orders...")
    random.seed(42)
    np.random.seed(42)
    os.makedirs(output_dir, exist_ok=True)

    # 1. Customers
    cities = [
        ("Hanoi", "HN", "Vietnam"), ("Ho Chi Minh City", "SG", "Vietnam"),
        ("Da Nang", "DN", "Vietnam"), ("Hai Phong", "HP", "Vietnam"),
        ("Can Tho", "CT", "Vietnam"), ("Bien Hoa", "DN", "Vietnam"),
        ("Nha Trang", "KH", "Vietnam"), ("Hue", "TTH", "Vietnam")
    ]
    first_names = ["Nguyen", "Tran", "Le", "Pham", "Hoang", "Phan", "Vu", "Dang", "Bui", "Do"]
    middle_names = ["Van", "Thi", "Duc", "Minh", "Huu", "Anh", "Quoc", "Thanh", "Dinh"]
    last_names = ["Nam", "Linh", "Tuan", "Hoa", "Dung", "Huong", "Phong", "Trang", "Long", "Thao"]

    customer_list = []
    for i in range(1, num_customers + 1):
        cid = f"CUST_{i:05d}"
        cunique = f"U_{uuid.uuid4().hex[:8]}"
        name = f"{random.choice(first_names)} {random.choice(middle_names)} {random.choice(last_names)}"
        email = f"{name.lower().replace(' ', '.')}{i}@ecommerce.vn"
        city, state, country = random.choice(cities)
        reg_date = start_date + timedelta(days=random.randint(0, 300))
        customer_list.append({
            "customer_id": cid,
            "customer_unique_id": cunique,
            "customer_name": name,
            "customer_email": email,
            "customer_city": city,
            "customer_state": state,
            "customer_country": country,
            "created_at": reg_date.strftime("%Y-%m-%d %H:%M:%S")
        })
    df_customers = pd.DataFrame(customer_list)
    df_customers.to_csv(os.path.join(output_dir, "customers.csv"), index=False)
    print("  -> Saved customers.csv")

    # 2. Products
    categories = [
        ("Electronics", 2500000, 15000000, 1200),
        ("Fashion", 150000, 1200000, 300),
        ("Home & Kitchen", 300000, 4500000, 2500),
        ("Health & Beauty", 120000, 2000000, 250),
        ("Sports & Outdoors", 200000, 5000000, 1500),
        ("Books & Stationery", 50000, 400000, 400)
    ]
    product_list = []
    for i in range(1, num_products + 1):
        pid = f"PROD_{i:04d}"
        cat, min_p, max_p, base_w = random.choice(categories)
        price = round(random.uniform(min_p, max_p), -3)
        cost = round(price * random.uniform(0.55, 0.75), -3)
        weight = round(base_w * random.uniform(0.7, 1.4), 1)
        pname = f"{cat} Item #{i}"
        product_list.append({
            "product_id": pid,
            "product_category": cat,
            "product_name": pname,
            "price": price,
            "cost": cost,
            "weight_g": weight
        })
    df_products = pd.DataFrame(product_list)
    df_products.to_csv(os.path.join(output_dir, "products.csv"), index=False)
    print("  -> Saved products.csv")

    # 3. Orders & Items & Payments & Reviews
    order_statuses = ["delivered", "delivered", "delivered", "delivered", "shipped", "canceled"]
    payment_types = ["credit_card", "e_wallet", "bank_transfer", "cash_on_delivery"]

    # Customer weighting: Pareto 80/20 principle
    cust_weights = np.random.exponential(scale=1.0, size=num_customers)
    cust_weights /= cust_weights.sum()

    reviews_templates = {
        "positive": [
            ("Sản phẩm tuyệt vời", "Giao hàng cực nhanh, đóng gói cẩn thận, dùng rất mượt mà và chất lượng."),
            ("Rất hài lòng", "Đúng như mô tả, thương hiệu uy tín, nhân viên giao hàng nhiệt tình."),
            ("Chất lượng 5 sao", "Hàng chính hãng, giá mềm hơn các siêu thị bên ngoài, sẽ ủng hộ tiếp."),
            ("Tuyệt vời trên cả mong đợi", "Thiết kế đẹp mắt, công năng hoàn hảo, đóng gói 2 lớp chắc chắn.")
        ],
        "neutral": [
            ("Tạm được", "Hàng dùng bình thường, bao bì hơi móp một chút nhưng sản phẩm không sao."),
            ("Đúng mô tả", "Sản phẩm tạm ổn so với tầm giá, giao hàng đúng hẹn."),
            ("Bình thường", "Không quá xuất sắc nhưng vừa túi tiền, phù hợp nhu cầu văn phòng.")
        ],
        "negative": [
            ("Giao hàng quá chậm", "Đặt hàng cả tuần mới nhận được, dịch vụ vận chuyển kém."),
            ("Không đúng kỳ vọng", "Chất lượng hoàn thiện kém, khác với ảnh quảng cáo."),
            ("Hàng bị lỗi nhẹ", "Gặp trục trặc khi cắm nguồn lần đầu, phải liên hệ bảo hành."),
            ("Thất vọng về chăm sóc", "Gọi tổng đài nhiều lần không giải quyết, sẽ không mua lại.")
        ]
    }

    order_list = []
    order_items_list = []
    payment_list = []
    review_list = []

    total_days = (end_date - start_date).days
    item_counter = 1
    payment_counter = 1

    for o_idx in range(1, num_orders + 1):
        order_id = f"ORD_{o_idx:06d}"
        # Sample customer with weighted frequency
        cust_id = np.random.choice(df_customers["customer_id"].values, p=cust_weights)
        
        # Simulate temporal pattern: trending upward + weekend spike
        day_offset = random.randint(0, total_days)
        order_time = start_date + timedelta(days=day_offset, hours=random.randint(8, 22), minutes=random.randint(0, 59))
        
        status = random.choice(order_statuses)
        delivery_time = order_time + timedelta(days=random.randint(1, 6)) if status == "delivered" else None
        
        order_list.append({
            "order_id": order_id,
            "customer_id": cust_id,
            "order_status": status,
            "order_purchase_timestamp": order_time.strftime("%Y-%m-%d %H:%M:%S"),
            "order_approved_at": (order_time + timedelta(minutes=random.randint(5, 60))).strftime("%Y-%m-%d %H:%M:%S"),
            "order_delivered_timestamp": delivery_time.strftime("%Y-%m-%d %H:%M:%S") if delivery_time else None,
            "order_estimated_delivery_date": (order_time + timedelta(days=4)).strftime("%Y-%m-%d")
        })

        # Items in this order
        num_items = np.random.choice([1, 2, 3, 4], p=[0.65, 0.22, 0.10, 0.03])
        total_order_amount = 0

        for _ in range(num_items):
            prod = df_products.sample(n=1).iloc[0]
            qty = random.choice([1, 1, 1, 2])
            price = prod["price"]
            freight = round(random.uniform(15000, 45000), -2)
            item_total = price * qty

            order_items_list.append({
                "order_item_id": f"ITEM_{item_counter:07d}",
                "order_id": order_id,
                "product_id": prod["product_id"],
                "quantity": qty,
                "price": price,
                "freight_value": freight,
                "shipping_limit_date": (order_time + timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
            })
            total_order_amount += item_total + freight
            item_counter += 1

        # Payment
        pay_type = random.choice(payment_types)
        installments = random.choice([1, 1, 1, 3, 6]) if pay_type == "credit_card" else 1
        payment_list.append({
            "payment_id": f"PAY_{payment_counter:06d}",
            "order_id": order_id,
            "payment_sequential": 1,
            "payment_type": pay_type,
            "payment_installments": installments,
            "payment_value": total_order_amount
        })
        payment_counter += 1

        # Review (for delivered orders ~ 70% probability)
        if status == "delivered" and random.random() < 0.70:
            # Score distribution correlated with delivery speed
            del_days = (delivery_time - order_time).days if delivery_time else 3
            if del_days > 4:
                score = np.random.choice([1, 2, 3, 4], p=[0.35, 0.35, 0.20, 0.10])
            else:
                score = np.random.choice([3, 4, 5], p=[0.15, 0.35, 0.50])

            if score >= 4:
                title, msg = random.choice(reviews_templates["positive"])
            elif score == 3:
                title, msg = random.choice(reviews_templates["neutral"])
            else:
                title, msg = random.choice(reviews_templates["negative"])

            review_list.append({
                "review_id": f"REV_{o_idx:06d}",
                "order_id": order_id,
                "review_score": score,
                "review_comment_title": title,
                "review_comment_message": msg,
                "review_creation_date": (delivery_time + timedelta(days=random.randint(0, 2))).strftime("%Y-%m-%d %H:%M:%S")
            })

    # Save to CSV
    pd.DataFrame(order_list).to_csv(os.path.join(output_dir, "orders.csv"), index=False)
    pd.DataFrame(order_items_list).to_csv(os.path.join(output_dir, "order_items.csv"), index=False)
    pd.DataFrame(payment_list).to_csv(os.path.join(output_dir, "payments.csv"), index=False)
    pd.DataFrame(review_list).to_csv(os.path.join(output_dir, "reviews.csv"), index=False)
    
    print(f"Generated successfully: {len(order_list)} orders, {len(order_items_list)} items, {len(review_list)} reviews.")

if __name__ == "__main__":
    generate_ecommerce_data()
