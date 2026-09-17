output "resource_group_name" {
  description = "Resource group containing the deployment."
  value       = azurerm_resource_group.main.name
}

output "aks_cluster_name" {
  description = "AKS cluster name for az aks get-credentials."
  value       = azurerm_kubernetes_cluster.main.name
}

output "postgres_server_name" {
  description = "Private PostgreSQL Flexible Server name."
  value       = azurerm_postgresql_flexible_server.main.name
}

output "postgres_fqdn" {
  description = "Private PostgreSQL server FQDN."
  value       = azurerm_postgresql_flexible_server.main.fqdn
}

output "postgres_database" {
  description = "Application database name."
  value       = azurerm_postgresql_flexible_server_database.tickets.name
}