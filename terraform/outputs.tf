output "resource_group_name" {
  description = "The name of the created resource group"
  value       = azurerm_resource_group.rg.name
}

output "storage_account_name" {
  description = "The name of the ADLS Gen2 storage account"
  value       = azurerm_storage_account.storage.name
}

output "storage_container_name" {
  description = "The name of the storage container in the data lake"
  value       = azurerm_storage_container.data_container.name
}

output "databricks_workspace_url" {
  description = "The URL of the Azure Databricks workspace"
  value       = azurerm_databricks_workspace.databricks.workspace_url
}

output "aks_cluster_name" {
  description = "The name of the AKS cluster for Airflow"
  value       = azurerm_kubernetes_cluster.aks.name
}

output "databricks_cluster_id" {
  description = "The ID of the Databricks cluster"
  value       = databricks_cluster.osv_spark_cluster.id
}
