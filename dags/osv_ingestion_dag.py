from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import os
import json
import shutil
import logging
import time
import zipfile
from google.cloud import storage
from google.api_core.exceptions import NotFound, Forbidden, TooManyRequests
from requests.exceptions import ConnectionError, Timeout

# Set Google Cloud authentication
GCP_CREDENTIALS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sa-key.json"))
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GCP_CREDENTIALS_PATH
#os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "../sa-key.json"

# Constants
#BASE_DIR = "../data"
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
RAW_DIR = os.path.join(BASE_DIR, "raw_files")
INTERMEDIATE_DIR = os.path.join(BASE_DIR, "intermediary_files")
VALIDATED_DIR = os.path.join(BASE_DIR, "validated_files")
LOG_FILE = os.path.join(BASE_DIR, "validation_log.txt")
GCS_BUCKET = "osv-vulnerabilities"
OSV_SOURCES = {"Bitnami": "Bitnami", "Hex": "Hex", "Go": "Go", "GIT": "GIT"}

# Get yesterday’s date
YESTERDAY = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
year, month, day = YESTERDAY.split("-")

def download_all_zip():
    """Download all.zip from OSV sources in Google Cloud Storage and extract the files."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(GCS_BUCKET)

    for ecosystem, prefix in OSV_SOURCES.items():
        partitioned_folder = os.path.join(RAW_DIR, ecosystem, year, month, day)
        os.makedirs(partitioned_folder, exist_ok=True)

        zip_filename = "all.zip"
        zip_blob_name = f"{prefix}/{zip_filename}"
        zip_filepath = os.path.join(partitioned_folder, zip_filename)

        retries = 3
        for attempt in range(1, retries + 1):
            try:
                if not file_exists(bucket, zip_blob_name):
                    logging.warning(f" {zip_blob_name} not found. Skipping...")
                    break

                blob = bucket.blob(zip_blob_name)
                blob.download_to_filename(zip_filepath)
                logging.info(f" Downloaded {zip_blob_name} -> {zip_filepath}")

                extract_zip(zip_filepath, partitioned_folder)
                os.remove(zip_filepath)
                break

            except NotFound:
                logging.warning(f" {zip_blob_name} not found (404). Skipping...")
                break
            except Forbidden:
                logging.error(f" Permission error (403) for {zip_blob_name}. Check GCS permissions.")
                break
            except TooManyRequests:
                wait_time = 2**attempt
                logging.warning(f" API rate limit hit (429). Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            except (ConnectionError, Timeout):
                logging.warning(f" Network issue. Retrying {zip_blob_name} (Attempt {attempt}/{retries})...")
                time.sleep(5)
            except Exception as e:
                logging.error(f" Unexpected error with {zip_blob_name}: {e}. Skipping...")
                break

def extract_zip(zip_filepath, destination_folder):
    """Extract the ZIP file."""
    try:
        with zipfile.ZipFile(zip_filepath, 'r') as zip_ref:
            zip_ref.extractall(destination_folder)
        logging.info(f" Extracted {zip_filepath} -> {destination_folder}")
    except zipfile.BadZipFile:
        logging.error(f" Corrupt ZIP file: {zip_filepath}. Skipping...")
    except Exception as e:
        logging.error(f" Error extracting {zip_filepath}: {e}")

def file_exists(bucket, blob_name):
    """Check if a file exists in GCS before attempting to download."""
    return any(blob.name == blob_name for blob in bucket.list_blobs())

def filter_and_move_json():
    """Filter JSON files based on 'modified' field and move to partitioned intermediate directory."""
    for ecosystem in OSV_SOURCES.keys():
        raw_folder = os.path.join(RAW_DIR, ecosystem, year, month, day)
        partitioned_folder = os.path.join(INTERMEDIATE_DIR, ecosystem, year, month, day)
        os.makedirs(partitioned_folder, exist_ok=True)

        if not os.path.exists(raw_folder):
            continue

        for file in os.listdir(raw_folder):
            if file.endswith(".json"):
                file_path = os.path.join(raw_folder, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    modified_date = data.get("modified", "").split("T")[0]
                    if modified_date == YESTERDAY:
                        shutil.copy(file_path, os.path.join(partitioned_folder, file))
                        logging.info(f"Copied {file} to {partitioned_folder}")
                    else:
                        logging.info(f"Skipped {file} because modified date {modified_date} is not {YESTERDAY}")
                except json.JSONDecodeError:
                    logging.error(f"Invalid JSON file: {file_path}")
                except Exception as e:
                    logging.error(f"Error processing {file}: {e}")

def validate_json_files():
    """Validate JSON files and move valid ones to validated directory."""
    required_fields = {"id", "aliases", "affected", "modified"}
    os.makedirs(VALIDATED_DIR, exist_ok=True)

    with open(LOG_FILE, "w") as log:
        for ecosystem in OSV_SOURCES.keys():
            partitioned_intermediate = os.path.join(INTERMEDIATE_DIR, ecosystem, year, month, day)
            partitioned_validated = os.path.join(VALIDATED_DIR, ecosystem, year, month, day)
            os.makedirs(partitioned_validated, exist_ok=True)

            if not os.path.exists(partitioned_intermediate):
                continue

            for file in os.listdir(partitioned_intermediate):
                file_path = os.path.join(partitioned_intermediate, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    if not required_fields.issubset(data.keys()):
                        log.write(f"{file} is missing required fields and was removed\n")
                        os.remove(file_path)
                        continue

                    shutil.move(file_path, os.path.join(partitioned_validated, file))
                    log.write(f"{file} is valid and moved to {partitioned_validated}\n")
                except json.JSONDecodeError:
                    log.write(f"{file} is corrupted and was removed\n")
                    os.remove(file_path)
                except Exception as e:
                    log.write(f"Error validating {file}: {e}\n")

# Define DAG
default_args = {'owner': 'airflow', 'start_date': datetime(2025, 1, 1), 'retries': 1, 'retry_delay': timedelta(minutes=1)}
with DAG('osv_ingestion_pipeline', default_args=default_args, schedule_interval='@daily', catchup=False) as dag:
    download_task = PythonOperator(task_id='download_osv_data', python_callable=download_all_zip)
    filter_task = PythonOperator(task_id='filter_and_partition_json', python_callable=filter_and_move_json)
    validate_task = PythonOperator(task_id='validate_json_files', python_callable=validate_json_files)
    download_task >> filter_task >> validate_task
