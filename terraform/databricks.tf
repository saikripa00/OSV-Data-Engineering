terraform {
  required_providers {
    databricks = {
      source  = "databricks/databricks"
      version = "~> 0.5.0"
    }
  }
}

# Configure the Databricks provider using the workspace URL and token.
provider "databricks" {
  host  = azurerm_databricks_workspace.databricks.workspace_url
  token = var.databricks_token
}

# Create a Databricks cluster with your Spark configuration settings.
resource "databricks_cluster" "osv_spark_cluster" {
  cluster_name            = "osv-spark-cluster"
  spark_version           = var.databricks_spark_version
  node_type_id            = var.databricks_node_type_id
  autotermination_minutes = var.databricks_autotermination_minutes
  num_workers             = var.databricks_num_workers

  spark_conf = {
    "spark.sql.shuffle.partitions"              = "200"
    "spark.sql.execution.arrow.pyspark.enabled"   = "true"
    "spark.executor.memory"                       = "6g"
    "spark.driver.memory"                         = "4g"
    "spark.sql.execution.broadcastTimeout"        = "600"
    "spark.databricks.delta.optimizeWrite.enabled"  = "true"
    "spark.databricks.delta.autoCompact.enabled"    = "true"
  }
}
