from delta.tables import DeltaTable
from pyspark.sql import SparkSession

# Initialize Spark
spark = SparkSession.builder \
    .appName("Fix Delta Schema") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
    .getOrCreate()

# Define table paths
DELTA_VULN_DIR = "../data/delta_tables/vulnerabilities"
DELTA_FIXED_DIR = "../data/delta_tables/fixed_versions"

# Remove existing non-partitioned tables (one-time fix)
spark.sql(f"DROP TABLE IF EXISTS delta.`{DELTA_VULN_DIR}`")
spark.sql(f"DROP TABLE IF EXISTS delta.`{DELTA_FIXED_DIR}`")

# Create empty partitioned tables
spark.sql(f"""
    CREATE TABLE delta.`{DELTA_VULN_DIR}`
    (vulnerability_id STRING, summary STRING, details STRING, aliases ARRAY<STRING>, 
    modified STRING, published STRING, schema_version STRING, date STRING)
    USING DELTA
    PARTITIONED BY (date)
""")

spark.sql(f"""
    CREATE TABLE delta.`{DELTA_FIXED_DIR}`
    (vulnerability_id STRING, package_name STRING, ecosystem STRING, 
    fixed_version STRING, introduced_version STRING, date STRING)
    USING DELTA
    PARTITIONED BY (date)
""")

print(" Delta tables recreated with partitions.")
