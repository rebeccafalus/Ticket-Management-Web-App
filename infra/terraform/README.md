# Azure infrastructure

This Terraform configuration provisions:

- An Azure resource group and VNet
- A delegated AKS subnet and a private PostgreSQL subnet
- An AKS cluster with Azure CNI, Azure network policy, OIDC, and workload identity enabled
- A private Azure Database for PostgreSQL Flexible Server with a `tickets` database
- Private DNS for PostgreSQL; storage defaults to the configured `postgres_storage_mb` value (32 GiB by default)

The default region is **West Central US** (`westcentralus`). This subscription
reported PostgreSQL provisioning restrictions in East US and rejected the
original `Standard_DS2_v2` AKS size. West Central US supports PostgreSQL 16
with `B_Standard_B1ms` and the default AKS size `Standard_D2as_v5`.

## Prerequisites

Install Terraform, Azure CLI, and kubectl. Authenticate and select a subscription:

```bash
az login
az account set --subscription <subscription-id>
az account show --query id -o tsv
```

Create a private variables file and keep it out of git:

```bash
cp infra/terraform/terraform.tfvars.example infra/terraform/terraform.tfvars
# Replace the subscription ID and PostgreSQL password in terraform.tfvars.
```

Initialize, review, and apply:

```bash
cd infra/terraform
terraform init
terraform fmt -check
terraform validate
rm -f tfplan
terraform plan -out=tfplan
terraform apply tfplan
```

Because the earlier failed attempt created the East US resource group and
network, changing the region causes Terraform to replace those resources in
the plan. Review the destroy/create actions carefully before applying. The
failed AKS and PostgreSQL resources were not created.

## Preserve the East US resources

Do not apply that replacement plan if the existing East US resource group must
remain. Azure resource groups cannot be moved between regions, and Terraform
will otherwise try to destroy the East US resources before recreating them.

Create the West Central deployment in a separate Terraform workspace and give
it a different environment suffix. This preserves the existing default
workspace and its East US state:

```bash
cd /workspaces/Ticket-Management-Web-App/infra/terraform

terraform workspace select default
terraform state pull > eastus-state-backup.json

terraform workspace new staging-west
terraform plan \
  -var='environment=staging-west' \
  -out=staging-west.tfplan
terraform apply staging-west.tfplan
```

The new resources will be named with the `staging-west` suffix, for example:
`rg-ticket-management-staging-west`, `aks-ticket-management-staging-west`,
and `psql-ticketmanagementstagingwest`. The original
`rg-ticket-management-staging` resource group remains intact.

After applying, use the West workspace for outputs and AKS credentials:

```bash
terraform workspace select staging-west
az aks get-credentials \
  --resource-group "$(terraform output -raw resource_group_name)" \
  --name "$(terraform output -raw aks_cluster_name)" \
  --overwrite-existing
kubectl config current-context
kubectl get nodes
```

Do not run `terraform apply` from the `default` workspace with the current
West Central variables; that workspace still manages the East US resources
and will plan their replacement. Do not commit `eastus-state-backup.json`.

Retrieve AKS credentials:

```bash
az aks get-credentials \
  --resource-group "$(terraform output -raw resource_group_name)" \
  --name "$(terraform output -raw aks_cluster_name)" \
  --overwrite-existing
kubectl get nodes
```

## Deploy the application

The CI workflow is designed to deploy GHCR images after replacing the image
owner and immutable tag. For a manual deployment, use the same image tag in
`infra/k8s/deployments.yaml`, then apply:

```bash
kubectl apply -f ../k8s/namespace.yaml
kubectl apply -f ../k8s/services.yaml -f ../k8s/deployments.yaml
kubectl -n ticket-management rollout status deployment/frontend
kubectl -n ticket-management rollout status deployment/backend-py
kubectl -n ticket-management rollout status deployment/ml
kubectl -n ticket-management rollout status deployment/route-go
```

For Azure PostgreSQL, do not apply the local `../k8s/postgres.yaml` StatefulSet.
Instead, create an application secret from the Terraform outputs and the
administrator password, then configure the API/ML services to use that server.
The database endpoint is available with:

```bash
terraform output -raw postgres_fqdn
```

The current application only exposes health endpoints and does not yet open a
database connection. Add the connection string when database-backed features
are implemented. Never commit `terraform.tfvars`, Terraform state, or database
passwords.

## Destroy

Review carefully before destroying because this deletes AKS and the database:

```bash
terraform plan -destroy
terraform destroy
```