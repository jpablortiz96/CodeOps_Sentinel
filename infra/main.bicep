// CodeOps Sentinel - Azure Infrastructure as Code
// Deploy: az deployment group create --resource-group codeops-sentinel-rg --template-file main.bicep

@description('Environment name')
param appEnv string = 'production'

@description('Azure region')
param location string = resourceGroup().location

@description('Backend container image')
param backendImage string = 'ghcr.io/your-org/sentinel-backend:latest'

@description('App Service SKU')
param appServiceSku string = 'B2'

var appName = 'codeops-sentinel'
var tags = {
  project: 'codeops-sentinel'
  environment: appEnv
  managedBy: 'bicep'
}

// ── Log Analytics Workspace ────────────────────────────────
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${appName}-logs'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
  }
}

// ── Application Insights ───────────────────────────────────
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${appName}-insights'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

// ── Azure OpenAI Service ───────────────────────────────────
resource openAiService 'Microsoft.CognitiveServices/accounts@2024-04-01-preview' = {
  name: '${appName}-openai'
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: { name: 'S0' }
  properties: {
    customSubDomainName: '${appName}-openai'
    publicNetworkAccess: 'Enabled'
  }
}

resource gpt4oDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-04-01-preview' = {
  parent: openAiService
  name: 'gpt-4o'
  sku: {
    name: 'Standard'
    capacity: 40
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o'
      version: '2024-08-06'
    }
  }
}

// ── App Service Plan ───────────────────────────────────────
resource appServicePlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: '${appName}-plan'
  location: location
  tags: tags
  kind: 'linux'
  sku: {
    name: appServiceSku
    tier: 'Basic'
  }
  properties: {
    reserved: true  // Linux
  }
}

// ── Backend: Azure App Service ─────────────────────────────
resource backendApp 'Microsoft.Web/sites@2023-12-01' = {
  name: '${appName}-api'
  location: location
  tags: tags
  properties: {
    serverFarmId: appServicePlan.id
    siteConfig: {
      linuxFxVersion: 'DOCKER|${backendImage}'
      alwaysOn: true
      webSocketsEnabled: true  // Required for WebSocket support
      appSettings: [
        { name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE', value: 'false' }
        { name: 'DOCKER_REGISTRY_SERVER_URL', value: 'https://ghcr.io' }
        { name: 'APP_ENV', value: appEnv }
        { name: 'SIMULATION_MODE', value: 'false' }
        { name: 'APPINSIGHTS_INSTRUMENTATIONKEY', value: appInsights.properties.InstrumentationKey }
        { name: 'AZURE_OPENAI_ENDPOINT', value: openAiService.properties.endpoint }
        { name: 'AZURE_MONITOR_WORKSPACE', value: logAnalytics.id }
      ]
    }
    httpsOnly: true
  }
}

// ── Frontend: Azure Static Web App ────────────────────────
resource staticWebApp 'Microsoft.Web/staticSites@2023-12-01' = {
  name: '${appName}-frontend'
  location: location
  tags: tags
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
  properties: {
    repositoryUrl: 'https://github.com/your-org/codeops-sentinel'
    branch: 'main'
    buildProperties: {
      appLocation: '/frontend'
      outputLocation: 'dist'
    }
  }
}

// ── Outputs ────────────────────────────────────────────────
output backendUrl string = 'https://${backendApp.properties.defaultHostName}'
output frontendUrl string = 'https://${staticWebApp.properties.defaultHostname}'
output openAiEndpoint string = openAiService.properties.endpoint
output logAnalyticsWorkspaceId string = logAnalytics.properties.customerId
