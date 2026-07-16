# ProjectContractValidator Design Document

## Purpose

`ProjectContractValidator` validates semantic contracts that span multiple generated files. It operates on the parsed `ProjectSpec` before relying on C# compilation, because compilation cannot prove that a controller, service, repository, DTO, and entity describe the same operation.

## Responsibilities

- Match declared service/repository methods with `method_specs` when a method specification is supplied.
- Compare declared method return types with method-spec outputs.
- Verify that parameter types refer to declared entities, DTOs, or supported primitive types.
- Verify that controllers have corresponding service and repository modules.
- Validate the basic HTTP verb/path shape of declared routes.
- After generation, verify that expected layer files exist, services and repositories implement their interfaces, controllers reference the matching service, and `Program.cs` contains the required DI registrations.

## Severity

- Structural and type-contract violations are blocking.
- Missing method specifications are warnings because the project generator supports default CRUD completion.

## Non-Goals

This layer does not parse generated C# or execute a database. Those checks remain the responsibility of compilation, runtime-oracle tests, and future endpoint integration tests.

The project generator also emits `Tests/ProjectWiringTests.cs`. This test boots the generated ASP.NET Core host through `WebApplicationFactory` and resolves the declared service/repository interfaces from the real DI container without issuing database queries.
