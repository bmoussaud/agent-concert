---
applyTo: '*'
description: "Guidelines for writing clear, consistent, and meaningful git commit messages following Conventional Commits specification."
---

# Git Commit Message Guidelines

## Format

All commit messages should follow the **Conventional Commits** specification:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

## Commit Types

Use these standard types for all commits:

- **feat**: A new feature for the user
- **fix**: A bug fix
- **docs**: Documentation only changes
- **style**: Changes that don't affect code meaning (white-space, formatting, missing semi-colons)
- **refactor**: Code change that neither fixes a bug nor adds a feature
- **perf**: Code change that improves performance
- **test**: Adding missing tests or correcting existing tests
- **build**: Changes that affect the build system or external dependencies (npm, pip, azd)
- **ci**: Changes to CI configuration files and scripts (GitHub Actions, Azure Pipelines)
- **chore**: Other changes that don't modify src or test files
- **revert**: Reverts a previous commit

## Rules

### Subject Line (First Line)

1. **Use imperative mood**: "Add feature" not "Added feature" or "Adds feature"
2. **Don't capitalize** the first letter after the colon
3. **No period** at the end
4. **Keep it under 72 characters**
5. **Be specific and descriptive**: Explain *what* and *why*, not *how*

### Body (Optional)

- Use the body to explain **what** and **why**, not **how**
- Wrap at 72 characters
- Separate from subject with a blank line
- Use bullet points when listing multiple changes

### Footer (Optional)

- Reference issues: `Fixes #123`, `Closes #456`, `Relates to #789`
- Note breaking changes: `BREAKING CHANGE: description`

## Examples

### Simple Feature
```
feat: add blob storage connection to foundry project
```

### Feature with Scope
```
feat(infra): add managed identity with RBAC assignments
```

### Bug Fix with Body
```
fix(ai-search): use ProjectManagedIdentity auth type for connections

The previous ManagedIdentity auth type is not supported by AI Foundry
projects. Updated to ProjectManagedIdentity and added required metadata
fields (AccountName, ContainerName) for blob storage connections.
```

### Breaking Change
```
refactor(infra)!: move all RBAC assignments to dedicated module

BREAKING CHANGE: Role assignments are now defined in a separate
role-assignments.bicep module instead of inline within resource modules.
This requires updating any external references to role assignments.
```

### Documentation
```
docs: add azure AI search available regions list
```

### Infrastructure Change
```
build(bicep): update storage and search API versions to latest stable
```

### Multiple Changes (Use Body)
```
feat(infra): add AI search and storage infrastructure

- Create ai-search.bicep module with basic SKU
- Create storage.bicep module with 'input' container
- Add RBAC role assignments for project and search identities
- Update main.bicep to wire new modules
- Add storage and search endpoints to outputs
```

## When to Commit

- **Commit often**: Small, focused commits are better than large ones
- **One logical change per commit**: Don't mix unrelated changes
- **Commit working code**: Each commit should leave the codebase in a working state
- **Before switching tasks**: Commit your current work before starting something new

## What NOT to Do

❌ `fix stuff`  
❌ `WIP`  
❌ `updated files`  
❌ `Fix. Fixed bug. Fixed it again.`  
❌ `feat: Add feature, fix bug, update docs, refactor code`  

✅ `fix(storage): prevent blob access when public access is disabled`  
✅ `feat(auth): add managed identity for storage access`  
✅ `docs(readme): add deployment prerequisites`  
✅ `refactor(rbac): extract role assignments to dedicated module`

## Scopes (Project-Specific)

Common scopes for this project:

- **infra**: Infrastructure/Bicep changes
- **ai-foundry**: AI Foundry resource changes
- **storage**: Storage account changes
- **search**: AI Search changes
- **rbac**: Role assignment changes
- **auth**: Authentication/authorization
- **docs**: Documentation
- **ci**: CI/CD workflows

## References

- [Conventional Commits](https://www.conventionalcommits.org/)
- [Angular Commit Guidelines](https://github.com/angular/angular/blob/main/CONTRIBUTING.md#commit)
