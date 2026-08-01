# Deploy a Azure App Service

## Paso 1: Crear App Service

```powershell
# Variables
$resourceGroup = "rg-copilot-postgres"
$appServiceName = "copilot-postgres-mcp"
$location = "canadacentral"

# Crear grupo de recursos (si no existe)
az group create --name $resourceGroup --location $location

# Crear App Service Plan
az appservice plan create `
  --name "$appServiceName-plan" `
  --resource-group $resourceGroup `
  --sku B1 `
  --is-linux

# Crear App Service
az webapp create `
  --resource-group $resourceGroup `
  --plan "$appServiceName-plan" `
  --name $appServiceName `
  --runtime "PYTHON|3.11"
```

## Paso 2: Configurar variables de entorno

```powershell
az webapp config appsettings set `
  --resource-group $resourceGroup `
  --name $appServiceName `
  --settings `
    PGHOST="dmdl-server.postgres.database.azure.com" `
    PGDATABASE="postgres" `
    PGUSER="copilot_reader" `
    PGPASSWORD="TU_PASSWORD_AQUI" `
    PGSSLMODE="require" `
    WEBSITES_PORT=8000 `
    ALLOWED_SCHEMAS="public"
```

## Paso 3: Deploy del código

```powershell
# Dentro de C:\Users\mreba\MCP_Datalake

# Inicializar repo git (si no existe)
git init
git add .
git commit -m "initial commit"

# Configurar deployment
az webapp deployment source config-local-git `
  --resource-group $resourceGroup `
  --name $appServiceName

# Agregar remote git
git remote add azure https://$appServiceName.scm.azurewebsites.net/$appServiceName.git

# Deploy
git push azure main
```

## Paso 4: Obtener la URL

```powershell
$url = az webapp show `
  --resource-group $resourceGroup `
  --name $appServiceName `
  --query "defaultHostName" `
  --output tsv

Write-Host "Tu app está en: https://$url/mcp"
```

Esa URL la usas en el copilot-connector.yaml en lugar del tunnel.
