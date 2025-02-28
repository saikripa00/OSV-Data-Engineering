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
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/home/saikripa/kai/sa-key.json"

# Constants
RAW_DIR = "/home/saikripa/kai/data/raw_files"
INTERMEDIATE_DIR = "/home/saikripa/kai/data/intermediary_files"
VALIDATED_DIR = "/home/saikripa/kai/data/validated_files"
LOG_FILE = "/home/saikripa/kai/data/validation_log.txt"
GCS_BUCKET = "osv-vulnerabilities"
OSV_SOURCES = {
    "Bitnami": "Bitnami",
    "Hex": "Hex",
    "Go": "Go",
    "GIT": "GIT"
}

# Get yesterday’s date
YESTERDAY = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")

def download_all_zip():
    """Download all.zip from OSV sources in Google Cloud Storage and extract the files."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(GCS_BUCKET)

    for source_name, prefix in OSV_SOURCES.items():
        raw_folder = os.path.join(RAW_DIR, source_name)
        os.makedirs(raw_folder, exist_ok=True)

        zip_filename = "all.zip"
        zip_blob_name = f"{prefix}/{zip_filename}"
        zip_filepath = os.path.join(raw_folder, zip_filename)

        retries = 3  # Number of retries for handling transient failures

        for attempt in range(1, retries + 1):
            try:
                # Check if the file exists before attempting download
                if not file_exists(bucket, zip_blob_name):
                    logging.warning(f" {zip_blob_name} not found. Skipping...")
                    break  # Move to the next OSV source

                blob = bucket.blob(zip_blob_name)
                blob.download_to_filename(zip_filepath)
                logging.info(f" Downloaded {zip_blob_name} -> {zip_filepath}")

                # Extract the ZIP file
                extract_zip(zip_filepath, raw_folder)

                # Cleanup the ZIP file after extraction
                os.remove(zip_filepath)

                break  # Exit retry loop if successful

            except NotFound:
                logging.warning(f" {zip_blob_name} not found (404). Skipping...")
                break  # Move on to the next source

            except Forbidden:
                logging.error(f" Permission error (403) for {zip_blob_name}. Check GCS permissions.")
                break  # No need to retry if it's a permission issue

            except TooManyRequests:
                wait_time = 2**attempt  # Exponential backoff
                logging.warning(f" API rate limit hit (429). Retrying in {wait_time} seconds...")
                time.sleep(wait_time)

            except (ConnectionError, Timeout):
                logging.warning(f" Network issue. Retrying {zip_blob_name} (Attempt {attempt}/{retries})...")
                time.sleep(5)

            except Exception as e:
                logging.error(f" Unexpected error with {zip_blob_name}: {e}. Skipping...")
                break  # Move on to the next file

def extract_zip(zip_filepath, destination_folder):
    """Extract the ZIP file and handle errors."""
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
    """Filter JSON files based on 'modified' field and move to partitioned directory."""
    try:
        for source_name in OSV_SOURCES.keys():
            raw_folder = os.path.join(RAW_DIR, source_name)

            if not os.path.exists(raw_folder):
                continue  # Skip if the directory does not exist

            for file in os.listdir(raw_folder):
                if file.endswith(".json"):
                    file_path = os.path.join(raw_folder, file)

                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            data = json.load(f)

                        modified_date = data.get("modified", "").split("T")[0]  # Extract YYYY-MM-DD
                        if modified_date == YESTERDAY:
                            # Create partitioned directory structure
                            year, month, day = YESTERDAY.split("-")
                            target_dir = os.path.join(INTERMEDIATE_DIR, year, month, day, source_name)
                            os.makedirs(target_dir, exist_ok=True)

                            # Move the file to the partitioned directory
                            shutil.copy(file_path, os.path.join(target_dir, file))
                            logging.info(f"Copied {file} to {target_dir}")
                    except json.JSONDecodeError:
                        logging.error(f"Invalid JSON file: {file_path}")
                    except Exception as e:
                        logging.error(f"Error processing {file}: {e}")

        logging.info("Filtering and partitioning complete.")
    except Exception as e:
        logging.error(f"Error in filtering process: {e}")
        raise

def validate_json_files():
    """Validate JSON files against schema and move valid ones to a partitioned validated directory."""
    required_fields = {"id", "aliases", "affected", "modified"}
    
    os.makedirs(VALIDATED_DIR, exist_ok=True)

    with open(LOG_FILE, "w") as log:
        for source_name in OSV_SOURCES.keys():
            # Navigate to partitioned intermediate directory
            year, month, day = YESTERDAY.split("-")
            partitioned_folder = os.path.join(INTERMEDIATE_DIR, year, month, day, source_name)

            if not os.path.exists(partitioned_folder):
                continue  # Skip if the directory does not exist

            for file in os.listdir(partitioned_folder):
                if file.endswith(".json"):
                    file_path = os.path.join(partitioned_folder, file)

                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            data = json.load(f)

                        # Validate required fields exist and contain expected data types
                        if not required_fields.issubset(data.keys()):
                            log.write(f"{file} is missing required fields and was removed\n")
                            os.remove(file_path)
                            continue

                        if not isinstance(data["id"], str) or not data["id"].strip():
                            log.write(f"{file} has an invalid 'id' field and was removed\n")
                            os.remove(file_path)
                            continue

                        if not isinstance(data["aliases"], list) or not all(isinstance(alias, str) for alias in data["aliases"]):
                            log.write(f"{file} has an invalid 'aliases' field and was removed\n")
                            os.remove(file_path)
                            continue

                        if not isinstance(data["modified"], str) or "T" not in data["modified"]:
                            log.write(f"{file} has an invalid 'modified' field and was removed\n")
                            os.remove(file_path)
                            continue

                        if not isinstance(data["affected"], list) or not all(isinstance(entry, dict) for entry in data["affected"]):
                            log.write(f"{file} has an invalid 'affected' field and was removed\n")
                            os.remove(file_path)
                            continue

                        # Maintain partitioned structure in VALIDATED_DIR
                        validated_partition_dir = os.path.join(VALIDATED_DIR, year, month, day, source_name)
                        os.makedirs(validated_partition_dir, exist_ok=True)

                        validated_target_path = os.path.join(validated_partition_dir, file)
                        shutil.move(file_path, validated_target_path)

                        log.write(f"{file} is valid and was moved to {validated_target_path}\n")

                    except json.JSONDecodeError:
                        log.write(f"{file} is corrupted and was removed\n")
                        os.remove(file_path)

                    except Exception as e:
                        log.write(f"Error validating {file}: {e}\n")

    logging.info("Validation complete. Check log file for details.")



# Define default DAG arguments
default_args = {
    'owner': 'airflow',
    'start_date': datetime(2025, 1, 1),
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
}

# Define the DAG
with DAG(
    'osv_ingestion_pipeline',
    default_args=default_args,
    schedule_interval='@daily',
    catchup=False,
    description="Download, extract, filter, validate OSV vulnerability data."
) as dag:

    download_task = PythonOperator(
        task_id='download_osv_data',
        python_callable=download_all_zip
    )

    filter_task = PythonOperator(
        task_id='filter_and_partition_json',
        python_callable=filter_and_move_json
    )

    validate_task = PythonOperator(
        task_id='validate_json_files',
        python_callable=validate_json_files
    )

    download_task >> filter_task >> validate_task  # Ensure tasks run in sequence
