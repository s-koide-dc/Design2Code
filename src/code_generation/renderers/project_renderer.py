
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
            "    <PackageReference Include=\"Microsoft.AspNetCore.Mvc.Testing\" Version=\"*\" />",
            "    <PackageReference Include=\"NSubstitute\" Version=\"*\" />",
            "    <PackageReference Include=\"Microsoft.Data.Sqlite\" Version=\"10.0.10\" />",
            "    <PackageReference Include=\"SQLitePCLRaw.bundle_e_sqlite3\" Version=\"3.0.3\" />",
            "    <PackageReference Include=\"Microsoft.Data.SqlClient\" Version=\"7.0.2\" />",
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
            "public partial class Program { }",
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


def render_project_wiring_tests(project_name: str, service_names: list[str], repository_names: list[str]) -> str:
    lines = [
        "using Microsoft.AspNetCore.Mvc.Testing;",
        "using Microsoft.Extensions.DependencyInjection;",
        "using Xunit;",
        "",
        f"namespace {project_name}.Tests;",
        "",
        "public sealed class ProjectWiringTests : IClassFixture<WebApplicationFactory<Program>>",
        "{",
        "    private readonly WebApplicationFactory<Program> _factory;",
        "",
        "    public ProjectWiringTests(WebApplicationFactory<Program> factory)",
        "    {",
        "        _factory = factory;",
        "    }",
        "",
        "    [Fact]",
        "    public void GeneratedApplication_ResolvesDeclaredLayers()",
        "    {",
        "        using var scope = _factory.Services.CreateScope();",
    ]
    for name in service_names:
        lines.append(f"        Assert.NotNull(scope.ServiceProvider.GetService<{project_name}.Services.I{name}>());")
    for name in repository_names:
        lines.append(f"        Assert.NotNull(scope.ServiceProvider.GetService<{project_name}.Repositories.I{name}>());")
    lines.extend(["    }", "}", ""])
    return "\n".join(lines)


def render_project_endpoint_tests(project_name: str, cases: list[dict[str, str]], repository_names: list[str]) -> str:
    lines = [
        "using Microsoft.AspNetCore.Hosting;",
        "using Microsoft.AspNetCore.Mvc.Testing;",
        "using Microsoft.AspNetCore.TestHost;",
        "using Microsoft.Extensions.DependencyInjection;",
        "using Microsoft.Extensions.DependencyInjection.Extensions;",
        "using NSubstitute;",
        "using System.Text;",
        "using Xunit;",
        f"using {project_name}.Models;",
        f"using {project_name}.Repositories;",
        "",
        f"namespace {project_name}.Tests;",
        "",
        "public sealed class ProjectEndpointTests",
        "{",
        "    private sealed class TestFactory : WebApplicationFactory<Program>",
        "    {",
    ]
    for name in repository_names:
        lines.append(f"        public I{name} Repository_{name} {{ get; }} = Substitute.For<I{name}>();")
    lines.extend([
        "",
        "        protected override void ConfigureWebHost(IWebHostBuilder builder)",
        "        {",
        "            builder.ConfigureTestServices(services =>",
        "            {",
    ])
    for name in repository_names:
        lines.append(f"                services.RemoveAll<I{name}>();")
        lines.append(f"                services.AddSingleton(Repository_{name});")
    lines.extend(["            });", "        }", "    }", ""])
    for case in cases:
        repo = case["repository"]
        route = case["route"]
        method_name = case["test_name"]
        setup_lines = case.get("setup_lines", [])
        lines.extend([
            "    [Fact]",
            f"    public async Task {method_name}()",
            "    {",
            "        using var factory = new TestFactory();",
        ])
        lines.extend([f"        {line}" for line in setup_lines])
        lines.extend([
            "        using var client = factory.CreateClient();",
        ])
        if case["verb"] == "GET":
            lines.append(f"        var response = await client.GetAsync(\"{route}\");")
        elif case["verb"] == "DELETE":
            lines.append(f"        var response = await client.DeleteAsync(\"{route}\");")
        else:
            body = case.get("body", "{}")
            lines.append(f"        var content = new StringContent(\"{body}\", Encoding.UTF8, \"application/json\");")
            if case["verb"] == "POST":
                lines.append(f"        var response = await client.PostAsync(\"{route}\", content);")
            else:
                lines.append(f"        var response = await client.PutAsync(\"{route}\", content);")
        if case.get("expected_status") is not None:
            lines.append(f"        Assert.Equal({case['expected_status']}, (int)response.StatusCode);")
        else:
            lines.append("        Assert.True(response.IsSuccessStatusCode);")
        lines.extend(["    }", ""])
    lines.extend(["}", ""])
    return "\n".join(lines)


def render_project_sqlite_endpoint_tests(project_name: str, cases: list[dict[str, str]]) -> str:
    lines = [
        "using System.Data;",
        "using System.Text;",
        "using Microsoft.AspNetCore.Hosting;",
        "using Microsoft.AspNetCore.Mvc.Testing;",
        "using Microsoft.AspNetCore.TestHost;",
        "using Microsoft.Data.Sqlite;",
        "using Microsoft.Extensions.DependencyInjection;",
        "using Microsoft.Extensions.DependencyInjection.Extensions;",
        "using Xunit;",
        "",
        f"namespace {project_name}.Tests;",
        "",
        "public sealed class ProjectSqliteEndpointTests",
        "{",
        "    private sealed class TestFactory : WebApplicationFactory<Program>",
        "    {",
        "        public SqliteConnection Connection { get; } = new(\"Data Source=:memory:\");",
        "",
        "        public TestFactory()",
        "        {",
        "            Connection.Open();",
        "        }",
        "",
        "        protected override void ConfigureWebHost(IWebHostBuilder builder)",
        "        {",
        "            builder.ConfigureTestServices(services =>",
        "            {",
        "                services.RemoveAll<IDbConnection>();",
        "                services.AddSingleton<IDbConnection>(Connection);",
        "            });",
        "        }",
        "",
        "        public void Execute(string sql)",
        "        {",
        "            using var command = Connection.CreateCommand();",
        "            command.CommandText = sql;",
        "            command.ExecuteNonQuery();",
        "        }",
        "",
        "        public object? Scalar(string sql)",
        "        {",
        "            using var command = Connection.CreateCommand();",
        "            command.CommandText = sql;",
        "            return command.ExecuteScalar();",
        "        }",
        "",
        "        protected override void Dispose(bool disposing)",
        "        {",
        "            if (disposing) Connection.Dispose();",
        "            base.Dispose(disposing);",
        "        }",
        "    }",
        "",
    ]
    for case in cases:
        name = case["test_name"]
        lines.extend([
            "    [Fact]",
            f"    public async Task {name}()",
            "    {",
            "        using var factory = new TestFactory();",
            f"        factory.Execute(\"{case['schema_sql']}\");",
        ])
        if case.get("seed_sql"):
            lines.append(f"        factory.Execute(\"{case['seed_sql']}\");")
        lines.extend([
            "        using var client = factory.CreateClient();",
            f"        var content = new StringContent(\"{case['body']}\", Encoding.UTF8, \"application/json\");",
            f"        var response = await client.{case['http_method']}Async(\"{case['route']}\"{', content' if case['http_method'] in {'Post', 'Put'} else ''});",
            "        Assert.True(response.IsSuccessStatusCode);",
        ])
        if case.get("response_contains"):
            lines.append(f"        Assert.Contains(\"{case['response_contains']}\", await response.Content.ReadAsStringAsync());")
        lines.append(f"        Assert.Equal({case['expected_scalar']}, factory.Scalar(\"{case['assert_sql']}\"));")
        lines.extend(["    }", ""])
    lines.extend(["}", ""])
    return "\n".join(lines)


def render_project_sqlserver_endpoint_tests(project_name: str, cases: list[dict[str, str]]) -> str:
    lines = [
        "using System.Data;",
        "using System.Text;",
        "using Microsoft.AspNetCore.Hosting;",
        "using Microsoft.AspNetCore.Mvc.Testing;",
        "using Microsoft.AspNetCore.TestHost;",
        "using Microsoft.Data.SqlClient;",
        "using Microsoft.Extensions.DependencyInjection;",
        "using Microsoft.Extensions.DependencyInjection.Extensions;",
        "using Xunit;",
        "",
        f"namespace {project_name}.Tests;",
        "",
        "public sealed class ProjectSqlServerEndpointTests",
        "{",
        "    private sealed class TestFactory : WebApplicationFactory<Program>",
        "    {",
        "        private readonly string _databaseName = \"GeneratedTests_\" + Guid.NewGuid().ToString(\"N\");",
        "        public SqlConnection Connection { get; private set; } = null!;",
        "",
        "        public TestFactory()",
        "        {",
        "            var master = new SqlConnection(\"Server=(localdb)\\\\MSSQLLocalDB;Integrated Security=True;Database=master;TrustServerCertificate=True\");",
        "            master.Open();",
        "            using var create = master.CreateCommand();",
        "            create.CommandText = $\"CREATE DATABASE [{_databaseName}]\";",
        "            create.ExecuteNonQuery();",
        "            master.Dispose();",
        "            Connection = new SqlConnection($\"Server=(localdb)\\\\MSSQLLocalDB;Integrated Security=True;Database={_databaseName};TrustServerCertificate=True\");",
        "            Connection.Open();",
        "        }",
        "",
        "        protected override void ConfigureWebHost(IWebHostBuilder builder)",
        "        {",
        "            builder.ConfigureTestServices(services =>",
        "            {",
        "                services.RemoveAll<IDbConnection>();",
        "                services.AddSingleton<IDbConnection>(Connection);",
        "            });",
        "        }",
        "",
        "        public void Execute(string sql)",
        "        {",
        "            using var command = Connection.CreateCommand();",
        "            command.CommandText = sql;",
        "            command.ExecuteNonQuery();",
        "        }",
        "",
        "        public object? Scalar(string sql)",
        "        {",
        "            using var command = Connection.CreateCommand();",
        "            command.CommandText = sql;",
        "            return command.ExecuteScalar();",
        "        }",
        "",
        "        protected override void Dispose(bool disposing)",
        "        {",
        "            if (disposing)",
        "            {",
        "                Connection.Dispose();",
        "                SqlConnection.ClearAllPools();",
        "                using var master = new SqlConnection(\"Server=(localdb)\\\\MSSQLLocalDB;Integrated Security=True;Database=master;TrustServerCertificate=True\");",
        "                master.Open();",
        "                using var drop = master.CreateCommand();",
        "                drop.CommandText = $\"IF DB_ID(N'{_databaseName}') IS NOT NULL BEGIN ALTER DATABASE [{_databaseName}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE [{_databaseName}] END\";",
        "                drop.ExecuteNonQuery();",
        "            }",
        "            base.Dispose(disposing);",
        "        }",
        "    }",
        "",
    ]
    for case in cases:
        lines.extend([
            "    [Fact]",
            f"    public async Task {case['test_name']}()",
            "    {",
            "        using var factory = new TestFactory();",
            f"        factory.Execute(\"{case['schema_sql']}\");",
        ])
        if case.get("seed_sql"):
            lines.append(f"        factory.Execute(\"{case['seed_sql']}\");")
        lines.extend([
            "        using var client = factory.CreateClient();",
        ])
        method = case["http_method"]
        if method in {"Post", "Put"}:
            lines.append(f"        var content = new StringContent(\"{case['body']}\", Encoding.UTF8, \"application/json\");")
            lines.append(f"        var response = await client.{method}Async(\"{case['route']}\", content);")
        else:
            lines.append(f"        var response = await client.{method}Async(\"{case['route']}\");")
        lines.append("        Assert.True(response.IsSuccessStatusCode);")
        if case.get("response_contains"):
            lines.append(f"        Assert.Contains(\"{case['response_contains']}\", await response.Content.ReadAsStringAsync());")
        lines.append(f"        Assert.Equal({case['expected_scalar']}, factory.Scalar(\"{case['assert_sql']}\"));")
        lines.extend(["    }", ""])
    lines.extend(["}", ""])
    return "\n".join(lines)
