# azure-deploy.ps1 — Manual build & deploy for AI Accelerator on Windows.
# Run this whenever you want to push a new deployment to Azure.
#
# Architecture: Single ACI container group with MySQL + backend + frontend.
# MySQL is internal only (localhost:3306). Backend and frontend are public.
#
# Prerequisites:
#   - Azure CLI installed and logged in (az login)
#   - Run from the repo root directory
#   - azure-setup.sh must have been run once to provision ACR and Storage Account
#
# Usage:  .\azure-deploy.ps1

# ── Configuration ─────────────────────────────────────────────────────────────
$RESOURCE_GROUP    = "amar-pethkar-sandbox-rg"
$LOCATION          = "uksouth"
$ACR_NAME          = "aiaccelacr"
$STORAGE_ACCOUNT   = "aiaccelstore"
$ACI_GROUP_NAME    = "ai-accel-app"
$ACI_DNS_LABEL     = "ai-accel-app"   # must be globally unique within region
$MYSQL_PASSWORD    = "AiAccel2026xPwd99"
$ACI_YAML_TEMPLATE = "aci-group.yaml"
# ─────────────────────────────────────────────────────────────────────────────

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$APP_URL     = "http://$ACI_DNS_LABEL.$LOCATION.azurecontainer.io"
$BACKEND_URL = "$APP_URL`:8000"
$IMAGE_TAG   = (git rev-parse --short HEAD 2>$null) ?? "latest"

Write-Host "=================================================="
Write-Host "  Deploying AI Accelerator to Azure"
Write-Host "  Tag:      $IMAGE_TAG"
Write-Host "  App URL:  $APP_URL"
Write-Host "=================================================="

# ── Retrieve credentials ───────────────────────────────────────────────────
Write-Host "`n── Fetching credentials..."
$ACR_PASSWORD   = az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv
$STORAGE_KEY    = az storage account keys list --account-name $STORAGE_ACCOUNT --resource-group $RESOURCE_GROUP --query "[0].value" -o tsv

# ── Build images inside Azure (no local Docker required) ─────────────────────
Write-Host "`n── Building backend image in ACR..."
az acr build --registry $ACR_NAME --image "backend:$IMAGE_TAG" --image "backend:latest" --file "backend/Dockerfile" .

Write-Host "`n── Building frontend image in ACR (backend URL baked in at build time)..."
az acr build --registry $ACR_NAME --image "frontend:$IMAGE_TAG" --image "frontend:latest" --build-arg "VITE_API_BASE_URL=$BACKEND_URL" --file "frontend/Dockerfile" .

# ── Patch the ACI YAML with real credentials then deploy ────────────────────
Write-Host "`n── Deploying ACI container group..."
$yaml = Get-Content $ACI_YAML_TEMPLATE -Raw
$yaml = $yaml.Replace("<ACR_PASSWORD>", $ACR_PASSWORD)
$yaml = $yaml.Replace("<STORAGE_KEY>", $STORAGE_KEY)
$yaml = $yaml.Replace("ai-accel-app:latest", "ai-accel-app:$IMAGE_TAG")

$tempYaml = [System.IO.Path]::GetTempFileName() + ".yaml"
$yaml | Set-Content $tempYaml -Encoding UTF8

az container delete --resource-group $RESOURCE_GROUP --name $ACI_GROUP_NAME --yes 2>$null
Start-Sleep -Seconds 5

az container create --resource-group $RESOURCE_GROUP --file $tempYaml
Remove-Item $tempYaml

Write-Host "`n=================================================="
Write-Host "  Deployment complete!"
Write-Host "  Frontend: $APP_URL"
Write-Host "  Backend:  $BACKEND_URL"
Write-Host "  API Docs: $BACKEND_URL/docs"
Write-Host "=================================================="
