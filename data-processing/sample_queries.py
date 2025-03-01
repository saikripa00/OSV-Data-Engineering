from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("DeltaTableSampleQueries") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
    .getOrCreate()

# --------------------------------------------------
# Query the Vulnerabilities Table by Vulnerability ID
# --------------------------------------------------
vuln_df = spark.read.format("delta").load("/home/saikripa/kai/data/delta_tables/vulnerabilities")

vuln_df.createOrReplaceTempView("vulnerabilities")

query_vuln = """
SELECT vulnerability_id, summary, details, modified
FROM vulnerabilities
WHERE vulnerability_id = 'CVE-2025-27140'
"""
result_vuln = spark.sql(query_vuln)
print("Vulnerability Details:")
result_vuln.show(truncate=False)

# --------------------------------------------------
# Query the Fixed Versions Table by Package Name
# --------------------------------------------------

fixed_df = spark.read.format("delta").load("/home/saikripa/kai/data/delta_tables/fixed_versions")

fixed_df.createOrReplaceTempView("fixed_versions")

query_fixed = """
SELECT vulnerability_id, package_name, ecosystem, fixed_version
FROM fixed_versions
WHERE package_name LIKE '%golang%'
"""
result_fixed = spark.sql(query_fixed)
result_fixed.show(truncate=False)

spark.stop()
