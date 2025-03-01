variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
  default     = "osv-data-lake-rg"
}

variable "location" {
  description = "Azure region to deploy resources"
  type        = string
  default     = "eastus"
}

variable "environment" {
  description = "Environment tag (e.g., dev, prod)"
  type        = string
  default     = "dev"
}

variable "storage_account_name" {
  description = "Name of the storage account (must be globally unique)"
  type        = string
  default     = "osvdatastorageacct"
}

variable "storage_container_name" {
  description = "Name of the storage container for the data lake"
  type        = string
  default     = "osv-datalake"
}

variable "databricks_workspace_name" {
  description = "Name of the Azure Databricks workspace"
  type        = string
  default     = "osv-databricks-ws"
}

variable "aks_cluster_name" {
  description = "Name of the AKS cluster for Apache Airflow"
  type        = string
  default     = "osv-aks-airflow"
}

variable "aks_dns_prefix" {
  description = "DNS prefix for the AKS cluster"
  type        = string
  default     = "osvaks"
}

variable "aks_node_count" {
  description = "Number of nodes for the AKS cluster"
  type        = number
  default     = 3
}

variable "aks_vm_size" {
  description = "VM size for the AKS nodes"
  type        = string
  default     = "Standard_DS2_v2"
}

# Databricks-related variables

variable "databricks_token" {
  description = "Authentication token for the Databricks provider"
  type        = string
  sensitive   = true
}

variable "databricks_spark_version" {
  description = "Spark version for Databricks cluster"
  type        = string
  default     = "11.3.x-scala2.12"
}

variable "databricks_node_type_id" {
  description = "Node type id for Databricks cluster"
  type        = string
  default     = "Standard_DS3_v2"
}

variable "databricks_autotermination_minutes" {
  description = "Autotermination in minutes for Databricks cluster"
  type        = number
  default     = 20
}

variable "databricks_num_workers" {
  description = "Number of workers for Databricks cluster"
  type        = number
  default     = 2
}
