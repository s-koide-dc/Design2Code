from typing import List


def _sanitize_identifier(text: str) -> str:
    if not isinstance(text, str):
        return "Case"
    cleaned = []
    for ch in text:
        if ch.isalnum() or ch == "_":
            cleaned.append(ch)
        else:
            cleaned.append("_")
    name = "".join(cleaned).strip("_")
    if not name:
        return "Case"
    if name[0].isdigit():
        return "Case_" + name
    return name


def render_service_tests(test_context: dict, root_namespace: str) -> str:
    context = dict(test_context)
    get_method = context.get("GetMethod", "")
    has_get = isinstance(get_method, str) and get_method.strip() != ""
    structured_cases = context.get("StructuredTestCases") or []
    lines = [
        "using System.Collections.Generic;",
        "using Xunit;",
        "",
        f"using {root_namespace}.DTO;",
        f"using {root_namespace}.Models;",
        f"using {root_namespace}.Repositories;",
        f"using {root_namespace}.Services;",
        "",
        f"namespace {root_namespace}.Tests;",
        "",
        f"public class {context['ServiceClass']}Tests",
        "{",
        f"    private sealed class FakeRepo : {context['RepositoryInterface']}",
        "    {",
        f"        public List<{context['EntityClass']}> Items {{ get; }} = new List<{context['EntityClass']}>();",
        "        public bool DeleteResult { get; set; } = false;",
        f"        public List<{context['EntityClass']}> {context['RepoList']}() => Items;",
        f"        public {context['EntityClass']}? {context['RepoGet']}({context['IdType']} id) => Items.Find(u => u.Id == id);",
        f"        public {context['EntityClass']} {context['RepoCreate']}({context['EntityClass']} entity)",
        "        {",
        "            var nextId = Items.Count + 1;",
        f"            var created = new {context['EntityClass']} {{ Id = nextId{context['EntityInit']} }};",
        "            Items.Add(created);",
        "            return created;",
        "        }",
        f"        public {context['EntityClass']}? {context['RepoUpdate']}({context['IdType']} id, {context['EntityClass']} entity)",
        "        {",
        "            var existing = Items.Find(u => u.Id == id);",
        "            if (existing == null) return null;",
        f"{context['UpdateAssignments']}",
        "            return existing;",
        "        }",
        f"        public bool {context['RepoDelete']}({context['IdType']} id)",
        "        {",
        "            return DeleteResult;",
        "        }",
        "    }",
        "",
        "    [Fact]",
        f"    public void {context['ListMethod']}_Empty_ReturnsEmptyList()",
        "    {",
        "        var repo = new FakeRepo();",
        f"        var service = new {context['ServiceClass']}(repo);",
        f"        var result = service.{context['ListMethod']}();",
        "        Assert.Empty(result);",
        "    }",
        "",
        "    [Fact]",
        f"    public void {context['CreateMethod']}_ValidRequest_ReturnsResponse()",
        "    {",
        "        var repo = new FakeRepo();",
        f"        var service = new {context['ServiceClass']}(repo);",
        f"        var req = new {context['CreateDto']} {context['ValidRequestInit']};",
        f"        var result = service.{context['CreateMethod']}(req);",
        "        Assert.NotNull(result);",
        "    }",
        "",
    ]
    if has_get:
        lines.extend([
            "    [Fact]",
            f"    public void {get_method}_WhenExists_ReturnsResponse()",
            "    {",
            "        var repo = new FakeRepo();",
            f"        var service = new {context['ServiceClass']}(repo);",
            f"        var req = new {context['CreateDto']} {context['ValidRequestInit']};",
            f"        var created = service.{context['CreateMethod']}(req);",
            "        Assert.NotNull(created);",
            "        var id = created!.Id;",
            f"        var fetched = service.{get_method}(id);",
            "        Assert.NotNull(fetched);",
            "    }",
            "",
        ])
        edge_get = any(
            isinstance(case, dict)
            and case.get("method") == get_method
            and case.get("type") == "edge_case"
            for case in structured_cases
        )
        if edge_get:
            lines.extend([
                "    [Fact]",
                f"    public void {get_method}_WhenMissing_ReturnsNull()",
                "    {",
                "        var repo = new FakeRepo();",
                f"        var service = new {context['ServiceClass']}(repo);",
                f"        var result = service.{get_method}({context['IdValue']});",
                "        Assert.Null(result);",
                "    }",
                "",
            ])
    for case in structured_cases:
        if not isinstance(case, dict):
            continue
        method_name = case.get("method")
        if not method_name:
            continue
        case_name = _sanitize_identifier(case.get("name") or "Case")
        arrange = case.get("arrange") if isinstance(case.get("arrange"), list) else []
        act = case.get("act")
        asserts = case.get("assert") if isinstance(case.get("assert"), list) else []
        if not isinstance(act, str) or not act.strip():
            continue
        lines.extend([
            "    [Fact]",
            f"    public void {method_name}_{case_name}()",
            "    {",
            "        // Arrange",
        ])
        for line in arrange:
            if isinstance(line, str) and line.strip():
                lines.append(f"        {line}")
        lines.extend([
            "",
            "        // Act",
            f"        {act}",
            "",
            "        // Assert",
        ])
        for line in asserts:
            if isinstance(line, str) and line.strip():
                lines.append(f"        {line}")
        lines.extend([
            "    }",
            "",
        ])
    lines.extend([
        f"{context['InvalidTest']}",
        "    [Fact]",
        f"    public void {context['UpdateMethod']}_NotFound_ReturnsNull()",
        "    {",
        "        var repo = new FakeRepo();",
        f"        var service = new {context['ServiceClass']}(repo);",
        f"        var req = new {context['CreateDto']} {context['ValidRequestInit']};",
        f"        var result = service.{context['UpdateMethod']}({context['IdValue']}, req);",
        "        Assert.Null(result);",
        "    }",
        "",
        "    [Fact]",
        f"    public void {context['UpdateMethod']}_ValidRequest_ReturnsResponse()",
        "    {",
        "        var repo = new FakeRepo();",
        f"        var service = new {context['ServiceClass']}(repo);",
        f"        var createReq = new {context['CreateDto']} {context['ValidRequestInit']};",
        f"        var created = service.{context['CreateMethod']}(createReq);",
        "        Assert.NotNull(created);",
        "        var id = created!.Id;",
        f"        var updateReq = new {context['CreateDto']} {context['ValidRequestInit']};",
        f"        var result = service.{context['UpdateMethod']}(id, updateReq);",
        "        Assert.NotNull(result);",
        "    }",
        "",
        "    [Fact]",
        f"    public void {context['DeleteMethod']}_WhenRepoReturnsFalse_ReturnsFalse()",
        "    {",
        "        var repo = new FakeRepo { DeleteResult = false };",
        f"        var service = new {context['ServiceClass']}(repo);",
        f"        var result = service.{context['DeleteMethod']}({context['IdValue']});",
        "        Assert.False(result);",
        "    }",
        "",
        "    [Fact]",
        f"    public void {context['DeleteMethod']}_WhenRepoReturnsTrue_ReturnsTrue()",
        "    {",
        "        var repo = new FakeRepo { DeleteResult = true };",
        f"        var service = new {context['ServiceClass']}(repo);",
        f"        var result = service.{context['DeleteMethod']}({context['IdValue']});",
        "        Assert.True(result);",
        "    }",
        "}",
        "",
    ])
    return "\n".join(lines)
