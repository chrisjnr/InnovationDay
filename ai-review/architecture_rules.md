# Architecture Rules (AI Enforcement)

## Layered Boundaries
- UI must not call infrastructure directly.
- Domain must not depend on external libs.
- Infrastructure depends on Domain, never reverse.
- No circular dependencies.

## Clean Structure
- Controllers contain no business logic.
- Services orchestrate interactions only.
- Repositories control data access only.
- DTOs contain no domain logic.

## Naming & Location
- Files must be in correct layer.
- Class name == file name.
- Avoid `Utils`, `Helpers`, `Common`.

## Coupling Rules
- No service locators or global state.
- External libs must be abstracted via interfaces.
- Use DI everywhere.

## API/Microservices
- No leaking internal domain models.
- Endpoints follow REST conventions.
- Breaking API changes must be versioned.

## Cloud/DevOps
- Configuration via environment, not constants.
- No secrets.
- Logging follows standard format.

## Forbidden Patterns
- God classes/methods
- Inline SQL
- Business logic inside controllers
- Overloaded feature flags