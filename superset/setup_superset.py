"""
superset/setup_superset.py
Automates Apache Superset Configuration via REST API:
1. Authenticates against /api/v1/security/login to retrieve JWT access_token & CSRF token.
2. Checks/Registers PostgreSQL database 'ecommerce_dw'.
3. Creates Datasets:
   - analytics.vw_daily_sales_performance
   - analytics.revenue_forecast
   - analytics.customer_segments
   - analytics.review_sentiment
   - analytics.vw_customer_360
4. Generates Dashboard 'E-Commerce AI & Analytics Command Center'.
"""

import os
import json
import urllib.request
import urllib.error
import http.cookiejar

SUPERSET_URL = os.getenv("SUPERSET_URL", "http://localhost:8088")
USERNAME = os.getenv("SUPERSET_USER", "admin")
PASSWORD = os.getenv("SUPERSET_PASS", "admin")
DB_NAME = "ecommerce_dw"
SQLALCHEMY_URI = "postgresql://superset:superset@superset_db:5432/ecommerce_dw"

class SupersetClient:
    def __init__(self, base_url, username, password):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.access_token = None
        self.csrf_token = None
        self._cookiejar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._cookiejar))

    def _cookie_header(self):
        return "; ".join(f"{c.name}={c.value}" for c in self._cookiejar)

    def authenticate(self):
        print(f"Authenticating with Superset at {self.base_url} as {self.username}...")
        url = f"{self.base_url}/api/v1/security/login"
        payload = json.dumps({"username": self.username, "password": self.password, "provider": "db"}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with self._opener.open(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            self.access_token = data.get("access_token")
            print("  -> JWT Access token acquired successfully!")

        # Fetch CSRF token (session cookie now stored in cookiejar)
        csrf_url = f"{self.base_url}/api/v1/security/csrf_token/"
        req_csrf = urllib.request.Request(csrf_url, headers={
            "Authorization": f"Bearer {self.access_token}",
            "Cookie": self._cookie_header()
        })
        try:
            with self._opener.open(req_csrf) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                self.csrf_token = data.get("result")
                print("  -> CSRF token acquired!")
        except Exception as e:
            print(f"  [Notice] CSRF fetch returned: {e}")

    def _api_request(self, endpoint, method="GET", payload=None):
        url = f"{self.base_url}/api/v1/{endpoint.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Cookie": self._cookie_header()
        }
        if self.csrf_token:
            headers["X-CSRFToken"] = self.csrf_token

        data = json.dumps(payload).encode("utf-8") if payload else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self._opener.open(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            print(f"[API ERROR] {method} {url} -> {e.code}: {err_body}")
            raise

    def get_or_create_database(self):
        print(f"Checking database '{DB_NAME}'...")
        dbs = self._api_request("database/")
        for db in dbs.get("result", []):
            if db.get("database_name") == DB_NAME:
                print(f"  -> Found existing database id: {db['id']}")
                return db["id"]

        print(f"Creating database connection '{DB_NAME}' -> {SQLALCHEMY_URI}...")
        payload = {
            "database_name": DB_NAME,
            "sqlalchemy_uri": SQLALCHEMY_URI,
            "expose_in_sqllab": True,
            "allow_ctas": True,
            "allow_cvas": True,
            "allow_dml": False
        }
        res = self._api_request("database/", method="POST", payload=payload)
        db_id = res.get("id")
        print(f"  -> Created database successfully! ID: {db_id}")
        return db_id

    def get_or_create_dataset(self, db_id, schema, table_name):
        print(f"Checking dataset '{schema}.{table_name}'...")
        datasets = self._api_request("dataset/")
        for ds in datasets.get("result", []):
            if ds.get("table_name") == table_name and ds.get("schema") == schema:
                print(f"  -> Dataset already exists: id {ds['id']}")
                return ds["id"]

        print(f"Creating dataset '{schema}.{table_name}'...")
        payload = {
            "database": db_id,
            "schema": schema,
            "table_name": table_name
        }
        try:
            res = self._api_request("dataset/", method="POST", payload=payload)
            ds_id = res.get("id")
            print(f"  -> Dataset created! ID: {ds_id}")
            return ds_id
        except Exception as e:
            print(f"  -> Creation note: {e}")
            return None

    def get_or_create_dashboard(self, title):
        print(f"Checking dashboard '{title}'...")
        dashboards = self._api_request("dashboard/")
        for d in dashboards.get("result", []):
            if d.get("dashboard_title") == title:
                print(f"  -> Found dashboard id: {d['id']}")
                return d["id"]

        print(f"Creating dashboard '{title}'...")
        payload = {
            "dashboard_title": title,
            "published": True
        }
        res = self._api_request("dashboard/", method="POST", payload=payload)
        dash_id = res.get("id")
        print(f"  -> Dashboard created successfully! ID: {dash_id}")
        return dash_id

def main():
    client = SupersetClient(SUPERSET_URL, USERNAME, PASSWORD)
    client.authenticate()
    db_id = client.get_or_create_database()

    # Datasets across Staging and Analytics schemas
    datasets_to_register = [
        ("analytics", "vw_daily_sales_performance"),
        ("analytics", "revenue_forecast"),
        ("analytics", "customer_segments"),
        ("analytics", "review_sentiment"),
        ("analytics", "customer_churn_risk"),
        ("analytics", "vw_customer_360"),
        ("analytics", "vw_sentiment_overview")
    ]

    for schema, tbl in datasets_to_register:
        client.get_or_create_dataset(db_id, schema, tbl)

    dash_id = client.get_or_create_dashboard("TH2 - E-Commerce AI Analytics & Forecasting Command Center")
    print("\nSuperset Automated Provisioning Completed!")
    print(f"Access Dashboard: {SUPERSET_URL}/superset/dashboard/{dash_id}/")

if __name__ == "__main__":
    main()
