
def render_csproj(project_name: str, target_framework: str, package_lines: list) -> str:
    return "\n".join(
        [
            "<Project Sdk=\"Microsoft.NET.Sdk.Web\">",
            "  <PropertyGroup>",
            f"    <RootNamespace>{project_name}</RootNamespace>",
            f"    <TargetFramework>{target_framework}</TargetFramework>",
            "    <ImplicitUsings>enable</ImplicitUsings>",
            "    <Nullable>enable</Nullable>",
            "  </PropertyGroup>",
            "  <ItemGroup>",
            "    <Compile Remove=\"Tests\\**\\*.cs\" />",
            "    <Content Remove=\"Tests\\**\\*\" />",
            "    <None Remove=\"Tests\\**\\*\" />",
            "  </ItemGroup>",
            "\n".join(package_lines),
            "</Project>",
            "",
        ]
    )


def render_test_csproj(test_name: str, target_framework: str, project_name: str) -> str:
    return "\n".join(
        [
            "<Project Sdk=\"Microsoft.NET.Sdk\">",
            "  <PropertyGroup>",
            f"    <RootNamespace>{test_name}</RootNamespace>",
            f"    <TargetFramework>{target_framework}</TargetFramework>",
            "    <ImplicitUsings>enable</ImplicitUsings>",
            "    <Nullable>enable</Nullable>",
            "    <IsTestProject>true</IsTestProject>",
            "  </PropertyGroup>",
            "  <ItemGroup>",
            "    <PackageReference Include=\"xunit\" Version=\"*\" />",
            "    <PackageReference Include=\"xunit.runner.visualstudio\" Version=\"*\" />",
            "    <PackageReference Include=\"Microsoft.NET.Test.Sdk\" Version=\"*\" />",
            "  </ItemGroup>",
            "  <ItemGroup>",
            f"    <ProjectReference Include=\"..\\{project_name}.csproj\" />",
            "  </ItemGroup>",
            "</Project>",
            "",
        ]
    )


def render_program(service_regs: str, repo_regs: str, db_registration: str, root_namespace: str) -> str:
    return "\n".join(
        [
            "using System.Data;",
            "using Microsoft.AspNetCore.Builder;",
            "using Microsoft.Extensions.DependencyInjection;",
            "using Microsoft.Extensions.Hosting;",
            "using Microsoft.Data.SqlClient;",
            "",
            f"using {root_namespace}.Repositories;",
            f"using {root_namespace}.Services;",
            "",
            "var builder = WebApplication.CreateBuilder(args);",
            "builder.Services.AddControllers();",
            service_regs,
            repo_regs,
            db_registration,
            "var app = builder.Build();",
            "app.MapControllers();",
            "app.Run();",
            "",
        ]
    )


def render_appsettings() -> str:
    return "\n".join(
        [
            "{",
            "  \"ConnectionStrings\": {",
            "    \"Default\": \"Server=.;Database=AppDb;Trusted_Connection=True;\"",
            "  }",
            "}",
            "",
        ]
    )
