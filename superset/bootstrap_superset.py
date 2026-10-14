import os
from superset.app import create_app
app = create_app()

with app.app_context():
    from superset import db
    from superset.models.core import Database
    from superset.connectors.sqla.models import SqlaTable

    # 1. Database
    db_name = 'ecommerce_dw'
    database = db.session.query(Database).filter_by(database_name=db_name).first()
    if not database:
        database = Database(
            database_name=db_name,
            sqlalchemy_uri='postgresql://superset:superset@superset_db:5432/ecommerce_dw',
            expose_in_sqllab=True,
            allow_ctas=True,
            allow_cvas=True,
            allow_dml=False
        )
        db.session.add(database)
        db.session.commit()
        print('Created Database ecommerce_dw successfully!')
    else:
        print('Database ecommerce_dw already exists!')

    # 2. Datasets
    tables = [
        ('analytics', 'vw_daily_sales_performance'),
        ('analytics', 'revenue_forecast'),
        ('analytics', 'customer_segments'),
        ('analytics', 'review_sentiment'),
        ('analytics', 'customer_churn_risk'),
        ('analytics', 'vw_customer_360'),
        ('analytics', 'vw_sentiment_overview'),
        ('staging', 'fact_orders'),
        ('staging', 'dim_customers'),
        ('staging', 'dim_products')
    ]

    for schema, tbl in tables:
        existing_tbl = db.session.query(SqlaTable).filter_by(
            database_id=database.id, schema=schema, table_name=tbl
        ).first()
        if not existing_tbl:
            dataset = SqlaTable(
                database_id=database.id,
                schema=schema,
                table_name=tbl
            )
            db.session.add(dataset)
            try:
                db.session.commit()
                print(f'Created Dataset: {schema}.{tbl}')
            except Exception as e:
                db.session.rollback()
                print(f'Error registering {schema}.{tbl}: {e}')
        else:
            print(f'Dataset already exists: {schema}.{tbl}')
