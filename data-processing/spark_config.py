# spark_config.py

SPARK_CONFIG = {
    "spark.sql.shuffle.partitions": "200",  # Increase parallelism to handle large data
    "spark.sql.execution.arrow.pyspark.enabled": "true",  # Enable Arrow for Pandas UDFs
    "spark.executor.memory": "6g",  # Increase executor memory
    "spark.driver.memory": "4g",  # Increase driver memory
    "spark.sql.execution.broadcastTimeout": "600",  # Increase timeout for large joins
    "spark.databricks.delta.optimizeWrite.enabled": "true",  # Optimize Delta writes
    "spark.databricks.delta.autoCompact.enabled": "true",  # Enable auto compaction
}
