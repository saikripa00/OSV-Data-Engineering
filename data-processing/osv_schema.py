# osv_schema.py
from pyspark.sql.types import StructType, StructField, StringType, ArrayType, MapType

# Define OSV Schema
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
            StructField("package", StructType([
                StructField("name", StringType(), False),
                StructField("ecosystem", StringType(), False),
                StructField("purl", StringType(), True)
            ]), True),  # Nullable to allow records without package info
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
