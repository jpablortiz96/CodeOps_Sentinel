// ============================================================================
// CodeOps Sentinel -- Azure Infrastructure (Bicep)
// Provisions: Log Analytics, App Insights, ACR, Container Apps Environment.
// The Container App itself is created by deploy.ps1 AFTER the image is built
// in ACR -- this avoids the "image not found" error during Bicep deployment.
// ============================================================================

@description('Location for all resources')
param location string = resourceGroup().location

@description('Environment tag')
param environment string = 'production'

@description('Azure Container Registry name (globally unique, alphanumeric only)')
param acrName string = 'codeopssentinelacr'

@description('Backend Container App name (used to compute the final URL)')
param backendAppName string = 'codeops-sentinel-api'

// ---- Variables --------------------------------------------------------------
var containerEnvName = 'codeops-sentinel-env'
var logAnalyticsName = 'codeops-sentinel-logs'
var appInsightsName  = 'codeops-sentinel-insights'
var tags = {
  project:     'CodeOps Sentinel'
  environment: environment
  hackathon:   'Microsoft-GitHub-AI'
}

// ---- Log Analytics Workspace ------------------------------------------------
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name:     logAnalyticsName
  location: location
  tags:     tags
  properties: {
    sku:             { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

// ---- Application Insights ---------------------------------------------------
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name:     appInsightsName
  location: location
  tags:     tags
  kind:     'web'
  properties: {
    Application_Type:    'web'
    WorkspaceResourceId: logAnalytics.id
    IngestionMode:       'LogAnalytics'
  }
}

// ---- Azure Container Registry -----------------------------------------------
resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name:     acrName
  location: location
  tags:     tags
  sku:      { name: 'Basic' }
  properties: {
    adminUserEnabled:    true
    publicNetworkAccess: 'Enabled'
  }
}

// ---- Container Apps Environment ---------------------------------------------
// Consumption plan: no VM quota required.
resource containerEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name:     containerEnvName
  location: location
  tags:     tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey:  logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

// ---- Outputs ----------------------------------------------------------------
// deploy.ps1 uses these to create the Container App after the image is built.
output acrLoginServer     string = acr.properties.loginServer
output acrName            string = acr.name
output containerEnvName   string = containerEnv.name
output containerEnvDomain string = containerEnv.properties.defaultDomain
output appInsightsConnStr string = appInsights.properties.ConnectionString
// Pre-compute the final backend URL: https://<appName>.<envDomain>
output backendUrl         string = 'https://${backendAppName}.${containerEnv.properties.defaultDomain}'
