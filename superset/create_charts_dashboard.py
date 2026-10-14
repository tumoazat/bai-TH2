import json
from superset.app import create_app
app = create_app()

with app.app_context():
    from superset import db
    from superset.models.core import Database
    from superset.connectors.sqla.models import SqlaTable, TableColumn, SqlMetric
    from superset.models.dashboard import Dashboard
    from superset.models.slice import Slice

    db_name = 'ecommerce_dw'
    database = db.session.query(Database).filter_by(database_name=db_name).first()
    if not database:
        print("Database ecommerce_dw not found!")
        exit(1)

    print("Populating column metadata and metrics for datasets...")
    # Fetch all registered datasets and sync columns
    datasets = db.session.query(SqlaTable).filter_by(database_id=database.id).all()
    ds_map = {}
    for ds in datasets:
        try:
            ds.fetch_metadata()
            db.session.commit()
            ds_map[f"{ds.schema}.{ds.table_name}"] = ds
            print(f"  -> Synced metadata for: {ds.schema}.{ds.table_name}")
        except Exception as e:
            db.session.rollback()
            print(f"  -> Metadata note for {ds.table_name}: {e}")
            ds_map[f"{ds.schema}.{ds.table_name}"] = ds

    # Find or Create Charts (Slices)
    charts_def = [
        {
            "slice_name": "KPI: Tổng Doanh Thu Thực Tế",
            "viz_type": "big_number_total",
            "datasource": ds_map.get("analytics.vw_daily_sales_performance"),
            "params": {
                "metric": {"expressionType": "SQL", "sqlExpression": "SUM(total_revenue)", "label": "Tổng Doanh Thu (VND)"},
                "subheader": "Doanh thu tích lũy toàn hệ thống CRM/ERP"
            }
        },
        {
            "slice_name": "KPI: Tổng Đơn Hàng Hoàn Tất",
            "viz_type": "big_number_total",
            "datasource": ds_map.get("analytics.vw_daily_sales_performance"),
            "params": {
                "metric": {"expressionType": "SQL", "sqlExpression": "SUM(total_orders)", "label": "Tổng Đơn Hàng"},
                "subheader": "Số lượng đơn hàng giao thành công"
            }
        },
        {
            "slice_name": "AI Forecast: Doanh Thu Dự Báo 30 Ngày Tiếp Theo",
            "viz_type": "echarts_timeseries_line",
            "datasource": ds_map.get("analytics.revenue_forecast"),
            "params": {
                "x_axis": "ds",
                "metrics": [
                    {"expressionType": "SQL", "sqlExpression": "AVG(yhat)", "label": "Doanh Thu Dự Báo (yhat)"},
                    {"expressionType": "SQL", "sqlExpression": "AVG(yhat_upper)", "label": "Ngưỡng Trên (Upper Bound)"},
                    {"expressionType": "SQL", "sqlExpression": "AVG(yhat_lower)", "label": "Ngưỡng Dưới (Lower Bound)"}
                ]
            }
        },
        {
            "slice_name": "AI Segmentation: Cơ Cấu Phân Khúc Khách Hàng (RFM)",
            "viz_type": "pie",
            "datasource": ds_map.get("analytics.customer_segments"),
            "params": {
                "groupby": ["segment_name"],
                "metric": {"expressionType": "SQL", "sqlExpression": "COUNT(*)", "label": "Số Lượng Khách Hàng"}
            }
        },
        {
            "slice_name": "AI Sentiment: Phân Bố Cảm Xúc Đánh Giá Khách Hàng",
            "viz_type": "pie",
            "datasource": ds_map.get("analytics.review_sentiment"),
            "params": {
                "groupby": ["sentiment_label"],
                "metric": {"expressionType": "SQL", "sqlExpression": "COUNT(*)", "label": "Số Lượng Đánh Giá"}
            }
        },
        {
            "slice_name": "AI Sentiment: Vấn Đề Quan Tâm Chính Của Khách Hàng",
            "viz_type": "echarts_timeseries_bar",
            "datasource": ds_map.get("analytics.review_sentiment"),
            "params": {
                "x_axis": "primary_topic",
                "metrics": [{"expressionType": "SQL", "sqlExpression": "COUNT(*)", "label": "Số Lượng Feedback"}]
            }
        },
        {
            "slice_name": "AI Churn Risk: Cảnh Báo Nguy Cơ Rời Bỏ Khách Hàng",
            "viz_type": "pie",
            "datasource": ds_map.get("analytics.customer_churn_risk"),
            "params": {
                "groupby": ["churn_risk_level"],
                "metric": {"expressionType": "SQL", "sqlExpression": "COUNT(*)", "label": "Số Khách Hàng"}
            }
        }
    ]

    slices = []
    for c in charts_def:
        ds = c["datasource"]
        if not ds:
            continue
        existing_slice = db.session.query(Slice).filter_by(slice_name=c["slice_name"]).first()
        if not existing_slice:
            slc = Slice(
                slice_name=c["slice_name"],
                viz_type=c["viz_type"],
                datasource_type="table",
                datasource_id=ds.id,
                params=json.dumps(c["params"])
            )
            db.session.add(slc)
            db.session.commit()
            print(f"Created Chart: {c['slice_name']}")
            slices.append(slc)
        else:
            print(f"Chart already exists: {c['slice_name']}")
            slices.append(existing_slice)

    # Dashboard
    dash_title = "TH2 - E-Commerce AI Analytics & Forecasting Command Center"
    dash = db.session.query(Dashboard).filter_by(dashboard_title=dash_title).first()
    if not dash:
        dash = Dashboard(
            dashboard_title=dash_title,
            published=True,
            slices=slices
        )
        db.session.add(dash)
        db.session.commit()
        print(f"Created Dashboard: '{dash_title}' with {len(slices)} charts!")
    else:
        dash.slices = slices
        dash.published = True
        db.session.commit()
        print(f"Updated Dashboard: '{dash_title}' with {len(slices)} charts!")

    print(f"\nSuccessfully configured Dashboard! ID: {dash.id}")
    print(f"Open Dashboard URL: http://localhost:8088/superset/dashboard/{dash.id}/")
