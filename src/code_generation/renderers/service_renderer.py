from typing import List, Tuple


def render_service_class(name: str, iface: str, repo_iface: str, methods: list, root_namespace: str) -> str:
    method_blocks: List[str] = []
    for sig, body in methods:
        method_blocks.append(f"    {sig}")
        method_blocks.append("    {")
        method_blocks.extend([f"        {b}" for b in body])
        method_blocks.append("    }")
    return "\n".join(
        [
            "using System;",
            f"using {root_namespace}.DTO;",
            f"using {root_namespace}.Models;",
            f"using {root_namespace}.Repositories;",
            "",
            f"namespace {root_namespace}.Services;",
            "",
            f"public class {name} : {iface}",
            "{",
            f"    private readonly {repo_iface} _repo;",
            "",
            f"    public {name}({repo_iface} repo)",
            "    {",
            "        _repo = repo;",
            "    }",
            "",
            "\n".join(method_blocks),
            "}",
            "",
        ]
    )
