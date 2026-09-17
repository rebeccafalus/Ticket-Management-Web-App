variable "subscription_id" {
  description = "Azure subscription ID used for all resources."
  type        = string
}

variable "location" {
  description = "Azure region for the deployment. West Central US is enabled for this subscription's AKS and PostgreSQL services."
  type        = string
  default     = "West Central US"
}

variable "project_name" {
  description = "Short name used in Azure resource names."
  type        = string
  default     = "ticket-management"
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "staging"
}

variable "kubernetes_version" {
  description = "Optional AKS Kubernetes version. Leave null for the default supported version."
  type        = string
  default     = null
}

variable "node_count" {
  description = "Initial number of AKS system nodes."
  type        = number
  default     = 2
}

variable "node_vm_size" {
  description = "VM size for the AKS node pool. This size is available in West Central US for this subscription."
  type        = string
  default     = "Standard_D2as_v5"
}

variable "postgres_admin_password" {
  description = "Password for the PostgreSQL administrator. Store this in a secret tfvars file or environment variable."
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.postgres_admin_password) >= 12
    error_message = "postgres_admin_password must be at least 12 characters."
  }
}

variable "postgres_sku_name" {
  description = "Azure PostgreSQL Flexible Server SKU."
  type        = string
  default     = "B_Standard_B1ms"
}

variable "postgres_storage_mb" {
  description = "PostgreSQL storage in megabytes."
  type        = number
  default     = 32768
}