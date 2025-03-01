from pyspark.sql import SparkSession
from pyspark.sql.functions import col, explode, lit
import os
import sys
from datetime import datetime, timedelta
from osv_schema import osv_schema  # Import schema
from spark_config import SPARK_CONFIG  # Import Spark settings

# Get the absolute path of the current script's directory
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data"))

# Set up directories using BASE_DIR
VALIDATED_DIR = os.path.join(BASE_DIR, "validated_files")
DELTA_VULN_DIR = os.path.join(BASE_DIR, "delta_tables", "vulnerabilities")
DELTA_FIXED_DIR = os.path.join(BASE_DIR, "delta_tables", "fixed_versions")
LOG_FILE = os.path.join(BASE_DIR, "spark_process.log")

def log_message(message):
    """Log messages to a file and print them."""
    with open(LOG_FILE, "a") as log_file:
        log_file.write(message + "\n")
    print(message)

def get_yesterday_date():
    """Get yesterday's date in the format YYYY MM DD."""
    yesterday = datetime.utcnow() - timedelta(days=1)
    return yesterday.strftime("%Y"), yesterday.strftime("%m"), yesterday.strftime("%d")

def initialize_spark():
    """Initialize Spark session with optimized configurations."""
    builder = SparkSession.builder.appName("OSV Data Processing") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .config("spark.jars.packages", "io.delta:delta-core_2.12:2.2.0") \
        .config("spark.databricks.delta.schema.autoMerge.enabled", "true")

    # Apply optimizations from external Spark config file
    for key, value in SPARK_CONFIG.items():
        builder = builder.config(key, value)

    return builder.getOrCreate()

def process_osv_data(year, month, day):
    try:
        log_message(f" Starting OSV Data Processing for {year}/{month}/{day}")

        # Build the full path to yesterday's data
        input_path = os.path.join(VALIDATED_DIR, f"*/{year}/{month}/{day}")  # Wildcard for ecosystems

        # Validate directory existence
        if not os.path.exists(VALIDATED_DIR):
            log_message(f" ERROR: Validated files directory does not exist: {VALIDATED_DIR}")
            sys.exit(1)

        # Initialize optimized Spark session
        spark = initialize_spark()

        # Read all validated JSON files using the imported schema
        df = spark.read.schema(osv_schema) \
             .option("recursiveFileLookup", "true") \
             .option("mode", "PERMISSIVE") \
             .json(input_path)

        log_message(f" Loaded {df.count()} records from {input_path}")

        # Estimate partitions dynamically based on data size
        num_partitions = max(10, df.rdd.getNumPartitions())

        # --------------------------
        # Create Vulnerabilities Table (Partitioned by year, month, day)
        # --------------------------
        vuln_df = df.select(
            col("id").alias("vulnerability_id"),
            "summary",
            "details",
            "aliases",
            "modified",
            "published",
            "schema_version"
        ).withColumn("year", lit(year)) \
         .withColumn("month", lit(month)) \
         .withColumn("day", lit(day))  # Add partition columns

        # Repartition before writing to avoid memory spikes
        vuln_df = vuln_df.repartition(num_partitions, "year", "month", "day")

        vuln_df.write.format("delta") \
            .mode("append") \
            .option("mergeSchema", "true") \
            .partitionBy("year", "month", "day") \
            .save(DELTA_VULN_DIR)

        log_message(f" Wrote vulnerabilities Delta table at {DELTA_VULN_DIR}, partition: {year}/{month}/{day}")

        # --------------------------
        # Create Fixed Versions Table (Partitioned by year, month, day)
        # --------------------------
        affected_df = df.select("id", explode("affected").alias("affected_entry"))
        ranges_df = affected_df.withColumn("range", explode("affected_entry.ranges"))
        events_df = ranges_df.withColumn("event", explode("range.events"))

        fixed_df = events_df.select(
            col("id").alias("vulnerability_id"),
            col("affected_entry.package.name").alias("package_name"),
            col("affected_entry.package.ecosystem").alias("ecosystem"),
            col("event")["fixed"].alias("fixed_version"),
            col("event")["introduced"].alias("introduced_version")
        ).filter(col("fixed_version").isNotNull()) \
         .withColumn("year", lit(year)) \
         .withColumn("month", lit(month)) \
         .withColumn("day", lit(day))  # Add partition columns

        # Repartition before writing
        fixed_df = fixed_df.repartition(num_partitions, "year", "month", "day")

        fixed_df.write.format("delta") \
            .mode("append") \
            .option("mergeSchema", "true") \
            .partitionBy("year", "month", "day") \
            .save(DELTA_FIXED_DIR)

        log_message(f" Wrote fixed_versions Delta table at {DELTA_FIXED_DIR}, partition: {year}/{month}/{day}")

        spark.stop()
        log_message(" OSV Data Processing Completed Successfully.")

    except Exception as e:
        log_message(f" ERROR: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    # Get yesterday’s date from arguments (or fallback)
    if len(sys.argv) > 3:
        year, month, day = sys.argv[1], sys.argv[2], sys.argv[3]  # Date from Airflow
    else:
        year, month, day = get_yesterday_date()  # Default to yesterday

    process_osv_data(year, month, day)
