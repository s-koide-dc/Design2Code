from typing import List


def render_repository_class(name: str, iface: str, methods: list, root_namespace: str) -> str:
    method_blocks: List[str] = []
    for sig, body in methods:
        method_blocks.append(f"    {sig}")
        method_blocks.append("    {")
        method_blocks.extend([f"        {b}" for b in body])
        method_blocks.append("    }")
    return "\n".join(
        [
            "using System.Data;",
            "using Dapper;",
            f"using {root_namespace}.Models;",
            "",
            f"namespace {root_namespace}.Repositories;",
            "",
            f"public class {name} : {iface}",
            "{",
            "    private readonly IDbConnection _db;",
            "",
            f"    public {name}(IDbConnection db) {{ _db = db; }}",
            "",
            "\n".join(method_blocks),
            "}",
            "",
        ]
    )
