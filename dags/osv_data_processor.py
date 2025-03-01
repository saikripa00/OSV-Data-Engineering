from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta
import os

# Default DAG arguments
default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "start_date": datetime(2025, 1, 1),  # Start date for DAG
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# Dynamically determine the base project directory (parent of 'dags' folder)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Construct dynamic paths
PYSPARK_SCRIPT = os.path.join(BASE_DIR, "data-processing", "data_processor.py")
PYTHON_BIN = os.path.join(BASE_DIR, "osv_env", "bin", "python")  # Adjust for virtual env

# Get yesterday’s date dynamically
yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y/%m/%d")

# Define the DAG
with DAG(
    "osv_data_processor",
    default_args=default_args,
    schedule_interval="@daily",
    catchup=False,
) as dag:

    run_spark_job = BashOperator(
        task_id="run_pyspark_processing",
        bash_command=f"{PYTHON_BIN} {PYSPARK_SCRIPT} {yesterday}",
        dag=dag,
    )

    run_spark_job
