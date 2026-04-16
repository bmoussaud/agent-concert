---
description: 'Infrastructure as Code with Bicep'
applyTo: '**/*.bicep'
---

## Naming Conventions

-   When writing Bicep code, use lowerCamelCase for all names (variables, parameters, resources)
-   Use resource type descriptive symbolic names (e.g., 'storageAccount' not 'storageAccountName')
-   Avoid using 'name' in a symbolic name as it represents the resource, not the resource's name
-   Avoid distinguishing variables and parameters by the use of suffixes

## Structure and Declaration

-   Always declare parameters at the top of files with @description decorators
-   Use latest stable API versions for all resources
-   Use descriptive @description decorators for all parameters
-   Specify minimum and maximum character length for naming parameters

## Parameters

-   Set default values that are safe for test environments (use low-cost pricing tiers)
-   Use @allowed decorator sparingly to avoid blocking valid deployments
-   Use parameters for settings that change between deployments

## Variables

-   Variables automatically infer type from the resolved value
-   Use variables to contain complex expressions instead of embedding them directly in resource properties

## Resource References

-   Use symbolic names for resource references instead of reference() or resourceId() functions
-   Create resource dependencies through symbolic names (resourceA.id) not explicit dependsOn
-   For accessing properties from other resources, use the 'existing' keyword instead of passing values through outputs

## Resource Names

-   Use template expressions with uniqueString() to create meaningful and unique resource names
-   Add prefixes to uniqueString() results since some resources don't allow names starting with numbers

## Child Resources

-   Avoid excessive nesting of child resources
-   Use parent property or nesting instead of constructing resource names for child resources

## Security

-   Never include secrets or keys in outputs
-   Use `@secure()` for sensitive parameters (secrets, connection strings)
-   Use resource properties directly in outputs (e.g., storageAccount.properties.primaryEndpoints)
-   Enable managed identities wherever possible
-   Configure network ACLs with `bypass: 'AzureServices'` where applicable

## Azure Verified Modules (AVM)

Prefer AVM modules over raw resource declarations when available:

```bicep
module managedIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.5.0' = {
  name: 'managedIdentityDeployment'
  params: { ... }
}
```

- Pin to specific module versions (e.g., `:0.5.0`)
- Access module outputs via dot notation: `managedIdentity.outputs.principalId`

## Role Assignments

Follow a consistent pattern for role assignments. Note: `az.deployer().objectId` is available in interactive deployments; for automated/CI deployments, pass the principal ID as a parameter instead.

```bicep
roleAssignments: [
  {
    principalId: managedIdentity.outputs.principalId
    roleDefinitionIdOrName: 'Search Index Data Contributor'
    principalType: 'ServicePrincipal'
  }
  {
    principalId: az.deployer().objectId
    roleDefinitionIdOrName: 'Search Index Data Contributor'
    principalType: 'User'
  }
]
```

## Diagnostics and Tags

- Apply tags universally to all resources: `tags: tags`
- Configure diagnostic settings pointing to Log Analytics:

```bicep
diagnosticSettings: [
  {
    workspaceResourceId: logAnalyticsWorkspace.outputs.id
    name: 'resourceDiag'
  }
]
```

## Documentation

-   Include helpful // comments within your Bicep files to improve readability
-   Use `@description()` on all parameters with clear explanations
