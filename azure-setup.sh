#!/usr/bin/env bash
# azure-setup.sh — One-time Azure resource provisioning for AI Accelerator.
# Run this ONCE before the first deployment.
#
# Prerequisites: Azure CLI installed and logged in (az login)
# Usage: bash azure-setup.sh
#
# NOTE: Service principal creation (for GitHub Actions CI/CD) requires Azure AD
# admin rights and is NOT included here. Use azure-deploy.ps1 for manual
# deployments, or ask your Azure AD admin to create a service principal and
# grant it Contributor access to the resource group.

set -euo pipefail

# ── Configuration — change these to suit your environment ────────────────────
RESOURCE_GROUP="amar-pethkar-sandbox-rg"
LOCATION="uksouth"
ACR_NAME="aiaccelacr"            # must be globally unique, alphanumeric only
MYSQL_SERVER="ai-accel-mysql"    # must be globally unique
MYSQL_ADMIN="aiadmin"
MYSQL_DB="ai_config_wizard"
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
# ─────────────────────────────────────────────────────────────────────────────

echo "Using subscription: ${SUBSCRIPTION_ID}"
echo ""

# 1. Resource Group
echo "── Creating resource group..."
az group create --name "${RESOURCE_GROUP}" --location "${LOCATION}"

# 2. Azure Container Registry
echo "── Creating ACR..."
az acr create \
  --resource-group "${RESOURCE_GROUP}" \
  --name "${ACR_NAME}" \
  --sku Basic \
  --admin-enabled true

ACR_LOGIN_SERVER=$(az acr show --name "${ACR_NAME}" --query loginServer -o tsv)
ACR_USERNAME=$(az acr credential show --name "${ACR_NAME}" --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name "${ACR_NAME}" --query "passwords[0].value" -o tsv)

# 3. Azure Database for MySQL Flexible Server
echo "── Creating MySQL Flexible Server (this takes ~5 minutes)..."

# Generate a random password for the MySQL admin
MYSQL_ADMIN_PASSWORD=$(openssl rand -base64 24)
# Generate a password for the application user
MYSQL_USER_PASSWORD=$(openssl rand -base64 24)

az mysql flexible-server create \
  --resource-group "${RESOURCE_GROUP}" \
  --name "${MYSQL_SERVER}" \
  --location "${LOCATION}" \
  --admin-user "${MYSQL_ADMIN}" \
  --admin-password "${MYSQL_ADMIN_PASSWORD}" \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --storage-size 20 \
  --version 8.0.21 \
  --public-access 0.0.0.0  # allow Azure services

az mysql flexible-server db create \
  --resource-group "${RESOURCE_GROUP}" \
  --server-name "${MYSQL_SERVER}" \
  --database-name "${MYSQL_DB}"

# Create application-level DB user (requires mysql client or az mysql cli)
# For now, use the admin account as the app user.
# To harden: connect to MySQL and create a least-privilege user.
MYSQL_HOST=$(az mysql flexible-server show \
  --resource-group "${RESOURCE_GROUP}" \
  --name "${MYSQL_SERVER}" \
  --query fullyQualifiedDomainName -o tsv)

DATABASE_URL="mysql+asyncmy://${MYSQL_ADMIN}:${MYSQL_ADMIN_PASSWORD}@${MYSQL_HOST}/${MYSQL_DB}"

# ── Print deployment values ───────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  Azure resources provisioned. Values for azure-deploy.ps1:"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "ACR_NAME         = ${ACR_NAME}"
echo "ACR_LOGIN_SERVER = ${ACR_LOGIN_SERVER}"
echo "ACR_USERNAME     = ${ACR_USERNAME}"
echo "ACR_PASSWORD     = ${ACR_PASSWORD}"
echo "RESOURCE_GROUP   = ${RESOURCE_GROUP}"
echo "LOCATION         = ${LOCATION}"
echo "DATABASE_URL     = ${DATABASE_URL}"
echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  IMPORTANT: Store these values securely."
echo ""
echo "  For GitHub Actions CI/CD, ask your Azure AD admin to create"
echo "  a service principal with Contributor access to:"
echo "  /subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}"
echo "════════════════════════════════════════════════════════════════"
