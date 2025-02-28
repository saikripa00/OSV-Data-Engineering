from pyspark.sql import SparkSession
from pyspark.sql.functions import col, explode
from pyspark.sql.types import StructType, StructField, StringType, ArrayType, MapType
import os

# Initialize Spark Session with Delta Lake support
spark = SparkSession.builder \
    .appName("OSV Data Processing - Fixed Schema") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
    .config("spark.jars.packages", "io.delta:delta-core_2.12:2.2.0") \
    .getOrCreate()

# Updated schema: Allow "package" to be null in the "affected" array
osv_schema = StructType([
    StructField("id", StringType(), False),
    StructField("summary", StringType(), True),
    StructField("details", StringType(), True),
    StructField("aliases", ArrayType(StringType()), False),
    StructField("modified", StringType(), False),
    StructField("published", StringType(), True),
    StructField("database_specific", MapType(StringType(), StringType()), True),
    StructField("references", ArrayType(
        StructType([
            StructField("type", StringType(), True),
            StructField("url", StringType(), True)
        ])
    ), True),
    StructField("affected", ArrayType(
        StructType([
            # Set package to nullable=True so that records without it are accepted
            StructField("package", StructType([
                StructField("name", StringType(), False),
                StructField("ecosystem", StringType(), False),
                StructField("purl", StringType(), True)
            ]), True),
            StructField("ranges", ArrayType(
                StructType([
                    StructField("type", StringType(), False),
                    StructField("events", ArrayType(MapType(StringType(), StringType())), False)
                ])
            ), True),
            StructField("versions", ArrayType(StringType()), True),
            StructField("database_specific", MapType(StringType(), StringType()), True)
        ])
    ), False),
    StructField("schema_version", StringType(), False),
    StructField("severity", ArrayType(
        StructType([
            StructField("type", StringType(), True),
            StructField("score", StringType(), True)
        ])
    ), True)
])

# Directories for input and output
VALIDATED_DIR = "/home/saikripa/kai/data/validated_files"
DELTA_VULN_DIR = "/home/saikripa/kai/data/delta_tables/vulnerabilities"
DELTA_FIXED_DIR = "/home/saikripa/kai/data/delta_tables/fixed_versions"
LOG_FILE = "/home/saikripa/kai/data/spark_extended_log.txt"

def process_osv_data():
    if not os.path.exists(VALIDATED_DIR):
        print(f"Directory does not exist: {VALIDATED_DIR}")
        spark.stop()
        return

    # Read all validated JSON files recursively using the updated schema
    df = spark.read.schema(osv_schema) \
         .option("recursiveFileLookup", "true") \
         .option("mode", "PERMISSIVE") \
         .json(VALIDATED_DIR)

    print(f"Loaded {df.count()} records from validated files.")

    # --------------------------
    # Create Vulnerabilities Table
    # --------------------------
    vuln_df = df.select(
        col("id").alias("vulnerability_id"),
        "summary",
        "details",
        "aliases",
        "modified",
        "published",
        "schema_version"
    )
    vuln_df.write.format("delta").mode("overwrite").save(DELTA_VULN_DIR)
    print("Wrote vulnerabilities Delta table.")

    # --------------------------
    # Create Fixed Versions Table
    # --------------------------
    # Explode the "affected" array to extract package and version info.
    # For records missing the "package" field, the resulting package columns will be null.
    affected_df = df.select("id", explode("affected").alias("affected_entry"))
    ranges_df = affected_df.withColumn("range", explode("affected_entry.ranges"))
    events_df = ranges_df.withColumn("event", explode("range.events"))
    fixed_df = events_df.select(
        col("id").alias("vulnerability_id"),
        col("affected_entry.package.name").alias("package_name"),
        col("affected_entry.package.ecosystem").alias("ecosystem"),
        col("event")["fixed"].alias("fixed_version"),
        col("event")["introduced"].alias("introduced_version")
    ).filter(col("fixed_version").isNotNull())

    fixed_df.write.format("delta").mode("overwrite").save(DELTA_FIXED_DIR)
    print("Wrote fixed_versions Delta table.")

    spark.stop()

if __name__ == "__main__":
    process_osv_data()
