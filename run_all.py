#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_env_file(env_path: Path):
    env = {}
    if not env_path.exists():
        return env
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def in_container():
    return os.path.exists("/.dockerenv")


def docker_stack_ready():
    try:
        proc = subprocess.run(
            ["docker", "compose", "ps", "--services", "--filter", "status=running"],
            cwd=str(ROOT),
            capture_output=True, text=True, check=False,
        )
        return proc.returncode == 0 and "superset_app" in proc.stdout.splitlines()
    except FileNotFoundError:
        return False


def build_database_url_for_local():
    user = "superset"
    password = "superset"
    db_name = "ecommerce_dw"
    return f"postgresql+psycopg2://{user}:{password}@localhost:5432/{db_name}"


def build_database_url_for_container():
    user = "superset"
    password = "superset"
    db_name = "ecommerce_dw"
    return f"postgresql+psycopg2://{user}:{password}@superset_db:5432/{db_name}"


def prepare_local_environment():
    env_values = load_env_file(ROOT / ".env")
    env = os.environ.copy()
    env.update(env_values)
    env["RAW_DATA_DIR"] = str(ROOT / "data" / "raw")
    env["DATABASE_URL"] = build_database_url_for_local()
    env["PYTHONPATH"] = str(ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return env


def split_sql_statements(sql_text: str):
    statements = []
    current = []
    in_single_quote = False
    in_double_quote = False
    i = 0
    while i < len(sql_text):
        ch = sql_text[i]
        if ch == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
        elif ch == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
        elif ch == ";" and not in_single_quote and not in_double_quote:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
            i += 1
            continue
        current.append(ch)
        i += 1
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def build_schema_init_command(database_url: str, sql_files: list[str], executable: str | None = None) -> list[str]:
    script = f"""
from pathlib import Path
from sqlalchemy import create_engine

sql_file_paths = {sql_files!r}
database_url = {database_url!r}
sql_text = '\\n'.join(Path(path).read_text(encoding='utf-8') for path in sql_file_paths)
statements = []
current = []
in_single_quote = False
in_double_quote = False
for ch in sql_text:
    if ch == \"'\" and not in_double_quote:
        in_single_quote = not in_single_quote
    elif ch == '\\"' and not in_single_quote:
        in_double_quote = not in_double_quote
    elif ch == ';' and not in_single_quote and not in_double_quote:
        statement = ''.join(current).strip()
        if statement:
            statements.append(statement)
        current = []
        continue
    current.append(ch)

tail = ''.join(current).strip()
if tail:
    statements.append(tail)

engine = create_engine(database_url)
with engine.begin() as conn:
    for statement in statements:
        conn.exec_driver_sql(statement)
"""
    exec_path = executable or sys.executable
    return [exec_path, "-c", script]


def run_step(step_name: str, command: list[str], env: dict | None = None):
    print(f"\n===== {step_name} =====")
    print("Command:", " ".join(command))
    result = subprocess.run(command, cwd=str(ROOT), env=env)
    if result.returncode != 0:
        raise SystemExit(f"Step failed: {step_name}")


def build_local_steps(skip_gemini: bool):
    sql_files = [str(ROOT / "sql" / "01_schema.sql"), str(ROOT / "sql" / "02_analytics.sql")]
    schema_step = build_schema_init_command(build_database_url_for_local(), sql_files, sys.executable)
    steps = [
        ("Generate dataset", [sys.executable, str(ROOT / "data" / "generate_dataset.py")]),
        ("Initialize database schema", schema_step),
        ("Load raw data", [sys.executable, str(ROOT / "etl" / "load_raw.py")]),
        ("Transform ETL", [sys.executable, str(ROOT / "etl" / "transform.py")]),
        ("Forecast revenue", [sys.executable, str(ROOT / "ai" / "forecast.py")]),
        ("Customer segmentation", [sys.executable, str(ROOT / "ai" / "segmentation.py")]),
        ("Sentiment analysis", [sys.executable, str(ROOT / "ai" / "sentiment.py")]),
        ("Churn prediction", [sys.executable, str(ROOT / "ai" / "churn_predict.py")]),
        ("AI evaluation", [sys.executable, str(ROOT / "ai" / "evaluate.py")]),
    ]
    if not skip_gemini:
        steps.append(("Gemini advanced report", [sys.executable, str(ROOT / "ai" / "gemini_insights.py"), "--mode", "all"]))
    steps.append(("Bootstrap default dashboard", [sys.executable, str(ROOT / "superset" / "create_charts_dashboard.py")]))
    return steps


def build_container_steps(skip_gemini: bool):
    sql_files = ["/app/th2/sql/01_schema.sql", "/app/th2/sql/02_analytics.sql"]
    schema_step = build_schema_init_command(build_database_url_for_container(), sql_files, "python")
    steps = [
        ("Start Docker stack", ["docker", "compose", "up", "-d"]),
        ("Generate dataset", ["docker", "compose", "exec", "-T", "superset_app", "python", "/app/th2/data/generate_dataset.py"]),
        ("Initialize database schema", ["docker", "compose", "exec", "-T", "superset_app", *schema_step]),
        ("Load raw data", ["docker", "compose", "exec", "-T", "superset_app", "python", "/app/th2/etl/load_raw.py"]),
        ("Transform ETL", ["docker", "compose", "exec", "-T", "superset_app", "python", "/app/th2/etl/transform.py"]),
        ("Forecast revenue", ["docker", "compose", "exec", "-T", "superset_app", "python", "/app/th2/ai/forecast.py"]),
        ("Customer segmentation", ["docker", "compose", "exec", "-T", "superset_app", "python", "/app/th2/ai/segmentation.py"]),
        ("Sentiment analysis", ["docker", "compose", "exec", "-T", "superset_app", "python", "/app/th2/ai/sentiment.py"]),
        ("Churn prediction", ["docker", "compose", "exec", "-T", "superset_app", "python", "/app/th2/ai/churn_predict.py"]),
        ("AI evaluation", ["docker", "compose", "exec", "-T", "superset_app", "python", "/app/th2/ai/evaluate.py"]),
    ]
    if not skip_gemini:
        steps.append(("Gemini advanced report", ["docker", "compose", "exec", "-T", "superset_app", "python", "/app/th2/ai/gemini_insights.py", "--mode", "all"]))
    steps.append(("Bootstrap default dashboard", ["docker", "compose", "exec", "-T", "superset_app", "python", "/app/th2/superset/create_charts_dashboard.py"]))
    return steps


def main():
    parser = argparse.ArgumentParser(description="Run the full TH2 data/AI pipeline and optional Gemini report.")
    parser.add_argument("--skip-gemini", action="store_true", help="Skip Gemini advanced report generation.")
    args = parser.parse_args()

    use_container_mode = (not in_container()) and docker_stack_ready()
    print("TH2 - Run All pipeline")
    if use_container_mode:
        print("Execution mode: Docker Compose / superset_app container")
        steps = build_container_steps(args.skip_gemini)
    else:
        env = prepare_local_environment()
        print("Execution mode: Local Python environment")
        print(f"Database URL: {env['DATABASE_URL']}")
        steps = build_local_steps(args.skip_gemini)

    for step_name, command in steps:
        if use_container_mode:
            run_step(step_name, command)
        else:
            run_step(step_name, command, env)

    print("\nAll steps completed successfully.")


if __name__ == "__main__":
    main()
