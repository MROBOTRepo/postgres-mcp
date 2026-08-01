# Docker Deployment Guide for FastMCP PostgreSQL

## Why Docker?

- ✓ No Oryx interference (bypasses build cache issues)
- ✓ Clean, reproducible environment
- ✓ Exact control over runtime
- ✓ Standard way to deploy on Azure Container Instances & App Service

## Prerequisites

1. **Azure CLI** installed (`az` command)
2. **Docker** installed locally
3. **Azure Subscription** access

## Step 1: Build Docker Image Locally (Optional Test)

```bash
cd C:\Users\mreba\MCP_Datalake
docker build -t postgres-mcp:latest .
```

Test it locally:
```bash
docker run -p 8000:8000 \
  -e PGHOST=your-postgres.database.windows.net \
  -e PGDATABASE=your_db \
  -e PGUSER=your_user \
  -e PGPASSWORD=your_password \
  postgres-mcp:latest
```

Should see: `FastMCP servidor en http://0.0.0.0:8000/`

## Step 2: Push to Azure Container Registry (ACR)

### 2a. Create ACR (if you don't have one)

```bash
az acr create \
  --resource-group <your-resource-group> \
  --name copilotpostgres \
  --sku Basic
```

### 2b. Login to ACR

```bash
az acr login --name copilotpostgres
```

### 2c. Build & Push to ACR

```bash
az acr build \
  --registry copilotpostgres \
  --image postgres-mcp:latest \
  C:\Users\mreba\MCP_Datalake
```

This will:
- Upload your files to Azure
- Build the Docker image in the cloud
- Store it in your ACR

## Step 3: Connect App Service to ACR

### 3a. Via Azure Portal

1. **App Service** → **Deployment Center**
2. **Source**: Container Registries
3. **Registry**: copilotpostgres
4. **Image**: postgres-mcp
5. **Tag**: latest
6. **Save**

Azure will automatically deploy the latest image.

### 3b. Via Azure CLI

```bash
az webapp config container set \
  --name copilot-postgres-mcp-caevb3e3dqh8f5dx \
  --resource-group <your-resource-group> \
  --docker-custom-image-name copilotpostgres.azurecr.io/postgres-mcp:latest \
  --docker-registry-server-url https://copilotpostgres.azurecr.io \
  --docker-registry-server-user <acr-username> \
  --docker-registry-server-password <acr-password>
```

Get ACR credentials:
```bash
az acr credential show \
  --resource-group <your-resource-group> \
  --name copilotpostgres
```

## Step 4: Set Environment Variables

Portal → **App Service** → **Configuration** → **Application settings**

Add:
```
PGHOST = your-postgres-server.database.windows.net
PGDATABASE = your_db
PGUSER = your_user@your-server
PGPASSWORD = your_password
PGPORT = 5432
PGSSLMODE = require
ALLOWED_SCHEMAS = public
MAX_ROWS = 500
```

**Save** - App Service will restart automatically.

## Step 5: Test

```bash
curl https://copilot-postgres-mcp-caevb3e3dqh8f5dx.azurewebsites.net/
# Should return: MCP Server (proxy mode)

curl -X POST https://copilot-postgres-mcp-caevb3e3dqh8f5dx.azurewebsites.net/ \
  -H "Content-Type: application/json" \
  -d '{"method":"tools/list"}'
# Should return MCP tools list
```

## Updates

To push a new version:

```bash
# Make changes locally
# Then:

az acr build \
  --registry copilotpostgres \
  --image postgres-mcp:latest \
  C:\Users\mreba\MCP_Datalake

# App Service will auto-pull the new image
```

## Troubleshooting

### Image won't build

```bash
az acr build-task list --registry copilotpostgres
```

Check logs in Portal → ACR → Runs

### App Service not starting

Portal → **App Service** → **Log Stream** (bottom left)

Look for Python errors or connection issues.

### Still getting 404 on /mcp/mcp

Verify:
1. FastMCP is actually running (check logs)
2. Copilot connector YAML has correct host
3. Environment variables are set correctly

---

**No more Oryx cache issues.** The Docker approach gives you clean, repeatable deployments.
