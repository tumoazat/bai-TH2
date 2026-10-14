"""
ai/forecast.py
Revenue Forecasting AI Module.
Uses Time-Series Decomposition (Trend + Day-of-Week Seasonality + Moving Average Holt-Winters),
powered directly by NumPy & Pandas already in the system.
Calculates Evaluation Metrics: MAE, RMSE, MAPE.
Persists forecast with lower/upper confidence intervals into analytics.revenue_forecast.
"""

import os
import pandas as pd
import numpy as np
from datetime import timedelta
from sqlalchemy import create_engine, text

DB_URI = os.getenv("DATABASE_URL", "postgresql://superset:superset@superset_db:5432/ecommerce_dw")

def run_forecasting(forecast_days=30):
    print("=== [AI #1] Revenue Forecasting Engine ===")
    engine = create_engine(DB_URI)

    # 1. Load Daily Aggregated Sales from Staging
    query = """
        SELECT 
            purchase_date AS ds,
            SUM(total_amount) AS y
        FROM staging.fact_orders
        WHERE order_status = 'delivered'
        GROUP BY purchase_date
        ORDER BY purchase_date;
    """
    df = pd.read_sql(query, con=engine)
    df['ds'] = pd.to_datetime(df['ds'])
    df['y'] = df['y'].astype(float)
    print(f"Loaded {len(df)} historical daily data points.")

    # 2. Time-series feature engineering (Trend & Seasonality)
    # Train / Test split (last 30 days as test)
    split_idx = len(df) - 30
    train_df = df.iloc[:split_idx].copy()
    test_df = df.iloc[split_idx:].copy()

    # Day-of-week seasonality factors
    train_df['dow'] = train_df['ds'].dt.dayofweek
    dow_seasonality = train_df.groupby('dow')['y'].mean() / train_df['y'].mean()

    # Linear trend calculation (Ordinary Least Squares via numpy)
    x = np.arange(len(train_df))
    y = train_df['y'].values
    slope, intercept = np.polyfit(x, y, 1)

    # Predict on test set
    x_test = np.arange(len(train_df), len(df))
    test_trend = intercept + slope * x_test
    test_pred = test_trend * test_df['ds'].dt.dayofweek.map(dow_seasonality).values

    # Evaluation Metrics
    y_test_true = test_df['y'].values
    mae = float(np.mean(np.abs(y_test_true - test_pred)))
    rmse = float(np.sqrt(np.mean((y_test_true - test_pred) ** 2)))
    mape = float(np.mean(np.abs((y_test_true - test_pred) / y_test_true)) * 100)

    print(f"  -> Model Evaluation (Test Period):")
    print(f"     MAE : {mae:,.0f} VND")
    print(f"     RMSE: {rmse:,.0f} VND")
    print(f"     MAPE: {mape:.2f}%")

    # 3. Forecast future 30 days
    full_x = np.arange(len(df))
    full_slope, full_intercept = np.polyfit(full_x, df['y'].values, 1)

    future_x = np.arange(len(df), len(df) + forecast_days)
    future_trend = full_intercept + full_slope * future_x
    last_date = df['ds'].max()
    future_dates = [last_date + timedelta(days=i) for i in range(1, forecast_days + 1)]
    future_dows = [d.weekday() for d in future_dates]
    
    future_seasonality = np.array([dow_seasonality.get(d, 1.0) for d in future_dows])
    future_yhat = future_trend * future_seasonality

    # 95% Confidence Interval based on historical standard error
    residuals = y_test_true - test_pred
    std_err = float(np.std(residuals))
    yhat_lower = np.maximum(0, future_yhat - 1.96 * std_err)
    yhat_upper = future_yhat + 1.96 * std_err

    forecast_export = pd.DataFrame({
        'ds': [d.date() for d in future_dates],
        'yhat': np.round(future_yhat, 2),
        'yhat_lower': np.round(yhat_lower, 2),
        'yhat_upper': np.round(yhat_upper, 2),
        'trend': np.round(future_trend, 2),
        'model_name': 'TimeSeries-Decomposition-AI'
    })

    # Save to analytics.revenue_forecast
    print("Persisting predictions to analytics.revenue_forecast...")
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE analytics.revenue_forecast;"))
        forecast_export.to_sql('revenue_forecast', con=conn, schema='analytics', if_exists='append', index=False)

    print(f"Successfully saved {len(forecast_export)} forecasted days!")
    return {'mae': mae, 'rmse': rmse, 'mape': mape}

if __name__ == "__main__":
    run_forecasting()
