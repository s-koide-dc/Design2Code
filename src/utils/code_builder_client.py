# -*- coding: utf-8 -*-
import json
import subprocess
import os
import logging

class CodeBuilderClient:
    """C# CodeBuilder ツールと連携して論理設計図から C# コードを生成するクライアント"""

    def __init__(self, config):
        self.config = config
        root = getattr(config, 'workspace_root', os.getcwd())
        self.project_path = os.path.join(root, "tools", "csharp", "CodeBuilder", "CodeBuilder.csproj")
        self.exe_path = self._resolve_exe_path(root)
        self.use_dotnet_run = self.exe_path is None
        self.json_start_marker = "__CODEBUILDER_JSON_START__"
        self.json_end_marker = "__CODEBUILDER_JSON_END__"

    def _resolve_exe_path(self, root: str) -> str | None:
        release = os.path.join(root, "tools", "csharp", "CodeBuilder", "bin", "Release", "net10.0", "CodeBuilder.exe")
        debug = os.path.join(root, "tools", "csharp", "CodeBuilder", "bin", "Debug", "net10.0", "CodeBuilder.exe")
        if os.path.exists(release):
            return release
        if os.path.exists(debug):
            return debug
        return None

    def _extract_json_payload(self, stdout: str) -> str:
        if not stdout:
            return ""
        if self.json_start_marker in stdout and self.json_end_marker in stdout:
            start_idx = stdout.rfind(self.json_start_marker)
            end_idx = stdout.rfind(self.json_end_marker)
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                payload = stdout[start_idx + len(self.json_start_marker):end_idx]
                return payload.strip()
        # Fallback: try last non-empty line
        lines = [l for l in stdout.strip().split('\n') if l.strip()]
        return lines[-1] if lines else ""

    def build_code(self, blueprint: dict) -> dict:
        """Blueprint JSON を CodeBuilder に渡し、生成されたコードを受け取る"""
        if not os.path.exists(self.project_path):
            return {"status": "fallback", "code": self._render_fallback_code(blueprint)}
        import time
        root = getattr(self.config, 'workspace_root', os.getcwd())
        ts = time.time_ns()
        run_id = f"{ts}_{os.getpid()}"
        blueprint_dir = os.path.join(root, "cache", "blueprints", run_id)
        blueprint_path = os.path.abspath(os.path.join(blueprint_dir, "blueprint.json"))
        
        try:
            os.makedirs(os.path.dirname(blueprint_path), exist_ok=True)
            with open(blueprint_path, "w", encoding="utf-8") as f:
                json.dump(blueprint, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Failed to save blueprint: {e}")

        json_input = json.dumps(blueprint, ensure_ascii=False)
        
        try:
            if self.use_dotnet_run:
                cmd = ["dotnet", "run", "--project", self.project_path, "--quiet", "--nologo", "--"]
            else:
                cmd = [self.exe_path]
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8'
            )

            stdout, stderr = process.communicate(input=json_input)

            if process.returncode != 0:
                logging.error(f"CodeBuilder failed with return code {process.returncode}")
                logging.error(f"Stderr: {stderr}")
                return {"status": "error", "message": stderr}

            # Extract the JSON part with markers (fallback to last line)
            json_str = self._extract_json_payload(stdout)
            try:
                result = json.loads(json_str)
            except json.JSONDecodeError:
                print(f"[ERROR] CodeBuilder output was not JSON: {stdout}")
                return {"status": "error", "message": "Non-JSON output from CodeBuilder"}

            if "code" in result:
                # Keep the code as rendered by CodeBuilder
                result["code"] = result["code"].replace('\r\n', '\n')
            return result

        except Exception as e:
            logging.exception("Failed to communicate with CodeBuilder")
            return {"status": "error", "message": str(e)}

    def _render_fallback_code(self, blueprint: dict) -> str:
        """Minimal in-process renderer for tests when CodeBuilder is unavailable."""
        usings = blueprint.get("usings", []) or []
        namespace = blueprint.get("namespace", "Generated")
        class_name = blueprint.get("class_name", "GeneratedProcessor")
        fields = blueprint.get("fields", []) or []
        methods = blueprint.get("methods", []) or []
        extra_code = blueprint.get("extra_code", []) or []

        lines = []
        for u in usings:
            lines.append(f"using {u};")
        lines.append("")
        lines.append(f"namespace {namespace}")
        lines.append("{")
        lines.append(f"    public partial class {class_name}")
        lines.append("    {")
        for f in fields:
            lines.append(f"        private readonly {f.get('type', 'object')} {f.get('name', '')};")

        # Constructor
        if fields:
            ctor_params = []
            for f in fields:
                f_type = f.get("type", "object")
                f_name = f.get("name", "")
                param_name = f_name.lstrip("_") if f_name else "dep"
                ctor_params.append(f"{f_type} {param_name}")
            lines.append(f"        public {class_name}({', '.join(ctor_params)})")
            lines.append("        {")
            for f in fields:
                f_name = f.get("name", "")
                param_name = f_name.lstrip("_") if f_name else "dep"
                lines.append(f"            {f_name} = {param_name};")
            lines.append("        }")

        for m in methods:
            ret = m.get("return_type", "void")
            name = m.get("name", "Method")
            params = m.get("params", []) or []
            param_str = ", ".join([f"{p.get('type', 'object')} {p.get('name', 'arg')}" for p in params])
            lines.append("")
            lines.append(f"        public {ret} {name}({param_str})")
            lines.append("        {")
            body = m.get("body", []) or []
            for stmt in body:
                rendered = self._render_stmt(stmt)
                for bline in rendered.splitlines():
                    lines.append(f"            {bline}")
            lines.append("        }")

        lines.append("    }")
        lines.append("}")
        if extra_code:
            lines.append("")
            for code in extra_code:
                if isinstance(code, str) and code.strip():
                    lines.append(code.strip())
                    lines.append("")
        return "\n".join(lines)

    def _render_stmt(self, stmt: dict) -> str:
        if not isinstance(stmt, dict):
            return ""
        if "code" in stmt and stmt.get("code"):
            return str(stmt.get("code")).rstrip()
        s_type = stmt.get("type")
        if s_type == "call":
            call_expr = stmt.get("call_expr")
            if call_expr:
                return f"{call_expr};"
            method = stmt.get("method")
            if isinstance(method, tuple):
                method = method[0]
            args = stmt.get("args")
            if method and args is not None:
                return f"{method}({', '.join(args)});"
            if method and "(" not in method:
                return f"{method}();"
            return f"{method};" if method else ""
        if s_type == "assign":
            return f"{stmt.get('var_name', '')} = {stmt.get('value', '')};"
        if s_type == "comment":
            return f"// {stmt.get('text', '')}"
        if s_type == "foreach":
            source = stmt.get("source", "")
            item_name = stmt.get("item_name", "item")
            var_type = stmt.get("var_type", "var")
            var_decl = var_type if var_type and var_type != "var" else "var"
            body_lines = []
            for b in stmt.get("body", []) or []:
                rendered = self._render_stmt(b)
                for line in rendered.splitlines():
                    body_lines.append(f"    {line}")
            body_block = "\n".join(body_lines) if body_lines else "    // TODO: foreach body"
            return f"foreach ({var_decl} {item_name} in {source})\n{{\n{body_block}\n}}"
        if s_type == "if":
            cond = stmt.get("condition", "true")
            body_lines = []
            for b in stmt.get("body", []) or []:
                rendered = self._render_stmt(b)
                for line in rendered.splitlines():
                    body_lines.append(f"    {line}")
            body_block = "\n".join(body_lines) if body_lines else "    // TODO: if body"
            code = f"if ({cond})\n{{\n{body_block}\n}}"
            else_body = stmt.get("else_body", []) or []
            if else_body:
                else_lines = []
                else_lines.append("    // TODO: else")
                for b in else_body:
                    rendered = self._render_stmt(b)
                    for line in rendered.splitlines():
                        else_lines.append(f"    {line}")
                else_block = "\n".join(else_lines) if else_lines else "    // TODO: else body"
                code += f"\nelse\n{{\n{else_block}\n}}"
            return code
        return f"// TODO: {stmt.get('text', stmt.get('type', ''))}"
