# -*- coding: utf-8 -*- 
# src/action_executor/action_executor.py

import os
import subprocess
import re
import json
import shlex
import shutil
from datetime import datetime
from src.file_operations.file_operations import FileOperations
from src.csharp_operations.csharp_operations import CSharpOperations
from src.test_operations.test_operations import TestAndCoverageOperations
from src.refactoring_operations.refactoring_operations import RefactoringOperations
from src.cicd_operations.cicd_operations import CICDOperations
from src.tdd_operations.tdd_operations import TDDOperations
from src.utils.context_utils import normalize_path

# Additional components
from ..test_generator.test_generator import TestGenerator
from src.advanced_tdd.main import AdvancedTDDSupport
from ..coverage_analyzer.coverage_analyzer import CoverageAnalyzer
from ..refactoring_analyzer.refactoring_analyzer import RefactoringAnalyzer
from ..cicd_integrator.cicd_integrator import CICDIntegrator

class ActionExecutor:
    def __init__(self, log_manager, workspace_root=None, error_patterns_path=None, autonomous_learning=None, vector_engine=None, morph_analyzer=None, config_manager=None, semantic_analyzer=None):
        self.log_manager = log_manager
        self.autonomous_learning = autonomous_learning
        self.config_manager = config_manager
        self.workspace_root = workspace_root or os.getcwd()
        self.safe_commands = ["git", "ls", "dir", "type", "cat", "echo", "date", "time", "dotnet", "py", "python"]
        self.simple_whitelist = ["dir", "ls", "echo", "type", "cat", "date", "time"]
        self.allowed_subcommands = {
            "git": ["status", "log", "diff", "show", "branch", "rev-parse", "ls-files"],
            "dotnet": ["test", "build", "restore", "clean", "list"],
            "npm": ["test", "list"],
        }
        self.disallowed_args = {
            "python": ["-c", "-m"],
            "py": ["-c", "-m"],
        }
        self.python_allowed_dirs = ["scripts"]
        self.python_allowed_scripts = []
        self.blocked_metacharacters = ['&', '|', ';', '>', '<', '`', '$']
        self.read_commands = ["cat", "type"]
        self.list_commands = ["ls", "dir"]
        self.read_allowed_dirs = ["AIFiles", "config", "docs", "scripts", "src", "tests"]
        self.read_blocked_rules = [
            {"pattern": ".env", "match": "basename_exact"},
            {"pattern": "private_key", "match": "segment"},
            {"pattern": "api_key", "match": "segment"},
            {"pattern": "apikey", "match": "segment"},
            {"pattern": "secrets", "match": "segment"},
            {"pattern": "secret", "match": "segment"},
            {"pattern": "token", "match": "segment"},
        ]
        
        self.vector_engine = vector_engine
        self.morph_analyzer = morph_analyzer
        self.semantic_analyzer = semantic_analyzer

        # Load from safety_policy (via ConfigManager)
        if config_manager:
            policy_data = config_manager.get_safety_policy()
            self.safe_commands = policy_data.get("safe_commands", self.safe_commands)
            self.simple_whitelist = policy_data.get("simple_whitelist", self.simple_whitelist)
            self.allowed_subcommands = policy_data.get("allowed_subcommands", self.allowed_subcommands)
            self.disallowed_args = policy_data.get("disallowed_args", self.disallowed_args)
            self.python_allowed_dirs = policy_data.get("python_allowed_dirs", self.python_allowed_dirs)
            self.python_allowed_scripts = policy_data.get("python_allowed_scripts", self.python_allowed_scripts)
            self.blocked_metacharacters = policy_data.get("blocked_metacharacters", self.blocked_metacharacters)
            self.read_commands = policy_data.get("read_commands", self.read_commands)
            self.list_commands = policy_data.get("list_commands", self.list_commands)
            self.read_allowed_dirs = policy_data.get("read_allowed_dirs", self.read_allowed_dirs)
            self.read_blocked_rules = policy_data.get("read_blocked_rules", self.read_blocked_rules)
            
        ep_path = error_patterns_path
        if not ep_path and config_manager:
            ep_path = config_manager.error_patterns_path
        elif not ep_path:
            ep_path = "resources/error_patterns.json"
            
        self.error_patterns = self._load_error_patterns(ep_path)
        self.test_generator = TestGenerator(self.workspace_root)
        self.advanced_tdd_support = AdvancedTDDSupport(self.workspace_root, test_generator=self.test_generator)
        self.coverage_analyzer = CoverageAnalyzer(self.workspace_root, log_manager)
        self.refactoring_analyzer = RefactoringAnalyzer(self.workspace_root, log_manager, action_executor=self)
        self.cicd_integrator = CICDIntegrator(self.workspace_root, log_manager)
        
        # オペレーションクラスの初期化
        self.file_ops = FileOperations(self)
        self.csharp_ops = CSharpOperations(self)
        self.test_ops = TestAndCoverageOperations(self)
        self.ref_ops = RefactoringOperations(self)
        self.cicd_ops = CICDOperations(self)
        self.tdd_ops = TDDOperations(self)

    @property
    def compliance_auditor(self):
        if self.autonomous_learning:
            return self.autonomous_learning.compliance_auditor
        return None

    def execute(self, context: dict) -> dict:
        """
        Executes an action based on the plan created by the Planner.
        """
        context.setdefault("action_result", {"status": "error", "message": "アクションが実行されませんでした。"}) # Default error

        plan = context.get("plan", {})
        action_method_name = plan.get("action_method")
        parameters = plan.get("parameters", {})
        confirmation_needed = plan.get("confirmation_needed", False)
        safety_check_status = plan.get("safety_check_status", "UNKNOWN")

        # 1. Pre-execution Validation (Safety Policy)
        if safety_check_status == "BLOCK":
            context["action_result"] = {"status": "error", "message": "Safety Policyにより禁止された操作です。実行できません。"}
            return context
        
        # 2. Confirmation Check
        if confirmation_needed:
            if not (context.get("confirmation_granted") or context.get("confirmed")):
                context["action_result"] = {"status": "error", "message": "ユーザー承認が必要な操作です。"}
                return context

        # 3. Mandatory backup for high-risk changes
        if action_method_name in ["_delete_file", "_apply_code_fix", "_apply_refactoring"]:
            if not self._ensure_backup_for_action(action_method_name, parameters, context):
                return context

        # 3. Execute the action
        if action_method_name:
            self.log_manager.log_event("action_execution_start", {"action": action_method_name, "parameters": parameters}, level="INFO")
            result_ctx = self.execute_action(action_method_name, context, parameters)
            
            # Log completion status
            status = result_ctx.get("action_result", {}).get("status", "error")
            self.log_manager.log_event("action_execution", {
                "action": action_method_name, 
                "parameters": parameters, 
                "status": status,
                "message": result_ctx.get("action_result", {}).get("message", "")
            }, level="INFO")
            return result_ctx
        
        return context

    def execute_action(self, method_name: str, context: dict, parameters: dict) -> dict:
        """
        Directly executes an action method by name. Useful for tests and internal dispatch.
        """
        action_func = getattr(self, method_name, None)
        if action_func and callable(action_func):
            try:
                return action_func(context, parameters)
            except Exception as e:
                context["action_result"] = {"status": "error", "message": f"アクション実行中に予期せぬエラー: {e}"}
        else:
            context["action_result"] = {"status": "error", "message": f"不明なアクションメソッド: {method_name}"}
        
        return context

    def _run_learning_cycle(self, context: dict, parameters: dict) -> dict:
        """Executes the autonomous learning cycle."""
        if not self.autonomous_learning:
             context["action_result"] = {"status": "error", "message": "自律学習モジュールが有効化されていません。"}
             return context

        try:
            result = self.autonomous_learning.run_learning_cycle()
            status = result.get("status")
            
            if status == "success":
                report = result.get("report", {})
                patterns_found = result.get("patterns_found", 0)
                rules_applied = result.get("rules_applied", 0)
                msg = f"学習サイクルが完了しました。\nパターン抽出数: {patterns_found}\n適用された新ルール数: {rules_applied}"
                context["action_result"] = {"status": "success", "message": msg, "details": result}
            elif status == "skipped":
                reason = result.get("reason")
                msg = f"学習サイクルはスキップされました。理由: {reason}"
                context["action_result"] = {"status": "success", "message": msg, "details": result}
            else:
                 msg = f"学習サイクル中にエラーが発生しました: {result.get('error')}"
                 context["action_result"] = {"status": "error", "message": msg, "details": result}
                 
        except Exception as e:
            context["action_result"] = {"status": "error", "message": f"学習サイクル実行中に予期せぬエラー: {e}"}
            
        return context

    def _manage_knowledge(self, context: dict, parameters: dict) -> dict:
        """学習した知識の表示・検索・削除等の管理アクション (Phase 3)"""
        if not self.autonomous_learning:
             context["action_result"] = {"status": "error", "message": "自律学習モジュールが有効化されていません。"}
             return context

        op = parameters.get("operation", "list")
        
        if op == "list":
            summary = self.autonomous_learning.generate_knowledge_summary()
            msg = "【現在の学習状況】\n"
            msg += f"- 修復パターン数: {summary['repair_knowledge']['patterns_count']}\n"
            msg += f"- リトライルール数: {summary['retry_rules']['count']}\n"
            msg += f"- コンプライアンス監査項目: {summary['compliance']['findings_count']}件\n"
            
            proactive = summary['compliance'].get('proactive_suggestion')
            if proactive:
                msg += f"\n💡 AIからの提案:\n  {proactive['message']}\n"
            
            if summary.get("recent_feedback"):
                msg += "\n【直近のフィードバック】\n"
                for fb in summary["recent_feedback"]:
                    msg += f"- {fb.get('feedback')} ({fb.get('timestamp')[:10]})\n"
            
            context["action_result"] = {"status": "success", "message": msg, "summary": summary}
            
        elif op == "search_code":
            query = parameters.get("query")
            if not query:
                context["action_result"] = {"status": "error", "message": "検索クエリを指定してください。"}
                return context
            
            results = self.autonomous_learning.find_relevant_code(query)
            if not results:
                context["action_result"] = {"status": "success", "message": "関連するコードは見つかりませんでした。"}
                return context
            
            msg = f"「{query}」に関連するコンポーネント:\n"
            for r in results:
                msg += f"- {r['name']} ({r['file']}): {r['summary'][:100]}... (類似度: {r['similarity']:.2f})\n"
            
            context["action_result"] = {"status": "success", "message": msg, "results": results}
        
        else:
            context["action_result"] = {"status": "error", "message": f"不明な操作です: {op}"}

        return context

    def _reverse_dictionary_lookup(self, context: dict, parameters: dict) -> dict:
        """意味（日本語）からの逆引き検索を実行する (Phase 3)"""
        if not self.semantic_analyzer:
            # SemanticAnalyzer が注入されていない場合は、自前で初期化を試みる
            from src.semantic_analyzer.semantic_analyzer import SemanticAnalyzer
            # task_manager は context から取得可能か、None で初期化
            self.semantic_analyzer = SemanticAnalyzer(task_manager=None, config_manager=self.config_manager)

        query = parameters.get("query")
        if not query:
            context["action_result"] = {"status": "error", "message": "検索クエリを指定してください。"}
            return context

        results = self.semantic_analyzer.search_by_meaning(query)
        if not results:
            context["action_result"] = {"status": "success", "message": f"「{query}」の意味を持つ言葉は見つかりませんでした。"}
            return context

        msg = f"「{query}」の意味を持つ可能性のある言葉:\n"
        for r in results:
            msg += f"- {r['word']}: {r['meaning']}\n"
        
        context["action_result"] = {"status": "success", "message": msg, "results": results}
        return context

    def _generate_design_doc(self, context: dict, parameters: dict) -> dict:
        """ソースコードから設計書 (.design.md) を自動生成する"""
        target_file = self._get_entity_value(parameters.get("target_file"))
        if not target_file:
            context["action_result"] = {"status": "error", "message": "対象ファイルが指定されていません。"}
            return context

        full_path = self._safe_join(target_file)
        if not full_path or not os.path.exists(full_path):
            context["action_result"] = {"status": "error", "message": f"ファイルが見つかりません: {target_file}"}
            return context

        try:
            # 1. AST解析
            from src.advanced_tdd.ast_analyzer import ASTAnalyzer
            analyzer = ASTAnalyzer()
            structure = analyzer.analyze_file(full_path)
            
            # 2. Markdown生成
            module_name = os.path.splitext(os.path.basename(target_file))[0]
            doc_content = f"# {module_name} Design Document\n\n"
            doc_content += "## 1. Purpose\n(ここにモジュールの目的を記述してください。自動生成されたスケルトンです。)\n\n"
            doc_content += "## 2. Structured Specification\n\n"
            
            for cls in structure.get('classes', []):
                doc_content += f"### Class: {cls['name']}\n"
                if cls.get('docstring'):
                    doc_content += f"- **Description**: {cls['docstring']}\n"
                
                if cls.get('methods'):
                    doc_content += "- **Methods**:\n"
                    for m in cls['methods']:
                        # メソッド名が文字列か辞書かによって処理を分岐
                        m_name = m['name'] if isinstance(m, dict) else str(m)
                        doc_content += f"    - `{m_name}`\n"
                doc_content += "\n"

            for func in structure.get('functions', []):
                doc_content += f"### Function: {func['name']}\n"
                if func.get('docstring'):
                    doc_content += f"- **Description**: {func['docstring']}\n"
                doc_content += "\n"

            doc_content += "## 3. Core Logic\n(ロジックの詳細をここに記述してください。)\n"

            # 3. ファイル書き出し (規約に基づき src/{module}/{module}.design.md)
            design_path = os.path.splitext(target_file)[0] + ".design.md"
            full_design_path = self._safe_join(design_path)
            
            with open(full_design_path, 'w', encoding='utf-8') as f:
                f.write(doc_content)
            
            context["action_result"] = {
                "status": "success", 
                "message": f"設計書 '{design_path}' を生成しました。内容を確認・補記してください。",
                "generated_file": design_path
            }
        except Exception as e:
            context["action_result"] = {"status": "error", "message": f"設計書生成中にエラーが発生しました: {e}"}

        return context

    def _refine_design_doc(self, context: dict, parameters: dict) -> dict:
        """設計書内のプレースホルダーをコード分析に基づき自動補完・同期する"""
        target_design = self._get_entity_value(parameters.get("filename")) or self._get_entity_value(parameters.get("target_file"))
        if not target_design:
            context["action_result"] = {"status": "error", "message": "対象の設計書が指定されていません。"}
            return context

        full_design_path = self._safe_join(target_design)
        if not full_design_path or not os.path.exists(full_design_path):
            context["action_result"] = {"status": "error", "message": f"設計書が見つかりません: {target_design}"}
            return context

        # 対応するソースファイルを特定 (例: .design.md -> .py)
        source_file = target_design.replace(".design.md", ".py")
        if not os.path.exists(self._safe_join(source_file)):
            source_file = target_design.replace(".design.md", ".cs")
        
        full_source_path = self._safe_join(source_file)
        if not full_source_path or not os.path.exists(full_source_path):
            context["action_result"] = {"status": "error", "message": f"対応するソースファイルが見つかりません: {source_file}"}
            return context

        try:
            from src.utils.design_doc_refiner import DesignDocRefiner
            refiner = DesignDocRefiner(self.config_manager)
            
            result = refiner.sync_from_code(full_design_path, full_source_path)
            
            if result["status"] == "success":
                msg = f"設計書 '{target_design}' を実装と同期しました。\n"
                if result.get("findings"):
                    msg += f"\n【整合性監査レポート (Score: {result.get('audit_score')})】\n"
                    for f in result["findings"][:3]: # 上位3件を表示
                        icon = "🔴" if f["severity"] == "high" else "🟡"
                        msg += f"- {icon} {f['detail']}\n"
                
                context["action_result"] = {
                    "status": "success",
                    "message": msg,
                    "audit_result": result
                }
            elif result["status"] == "no_change":
                context["action_result"] = {"status": "success", "message": result["message"]}
            else:
                context["action_result"] = {"status": "error", "message": result["message"]}

        except Exception as e:
            context["action_result"] = {"status": "error", "message": f"設計書の同期中にエラーが発生しました: {e}"}

        return context

    def _create_file(self, context, parameters):
        return self.file_ops.create_file(context, parameters)

    def _append_file(self, context, parameters):
        return self.file_ops.append_file(context, parameters)

    def _delete_file(self, context, parameters):
        return self.file_ops.delete_file(context, parameters)

    def _read_file(self, context, parameters):
        return self.file_ops.read_file(context, parameters)

    def _list_dir(self, context, parameters):
        return self.file_ops.list_dir(context, parameters)

    def _run_command(self, context, parameters):
        cmd_str = self._get_entity_value(parameters.get("command"))
        if not cmd_str:
            context["action_result"] = {"status": "error", "message": "コマンドが指定されていません。"}
            return context

        # Safely split the command string into a list of arguments
        try:
            cmd_parts = shlex.split(cmd_str)
        except ValueError:
            context["action_result"] = {"status": "error", "message": "コマンドの形式が正しくありません。"}
            return context
        
        if not cmd_parts:
            context["action_result"] = {"status": "error", "message": "コマンドが空です。"}
            return context

        # 1. Base command validation
        base_cmd = cmd_parts[0].lower()

        if base_cmd not in self.safe_commands:
            context["action_result"] = {"status": "error", "message": f"コマンド '{base_cmd}' は許可されていません。"}
            return context

        # 2. Subcommand validation
        if base_cmd in self.allowed_subcommands and self.allowed_subcommands[base_cmd]:
            if len(cmd_parts) < 2 or cmd_parts[1].lower() not in self.allowed_subcommands[base_cmd]:
                allowed_str = ", ".join(self.allowed_subcommands[base_cmd])
                context["action_result"] = {"status": "error", "message": f"コマンド '{base_cmd}' のサブコマンドが許可されていないか、指定されていません。許可されているサブコマンド: {allowed_str}"}
                return context

        # 3. Argument validation
        if base_cmd in self.disallowed_args and self.disallowed_args[base_cmd]:
            disallowed = [a.lower() for a in self.disallowed_args[base_cmd]]
            for part in cmd_parts[1:]:
                if part.lower() in disallowed:
                    context["action_result"] = {"status": "error", "message": "コマンド引数に禁止されたオプションが含まれています。"}
                    return context

        # Prevent chaining and redirections first
        for part in cmd_parts[1:]:
            if any(char in part for char in self.blocked_metacharacters):
                context["action_result"] = {"status": "error", "message": "コマンド引数に不正な文字が含まれています。"}
                return context

        if base_cmd in self.read_commands:
            targets = self._extract_non_option_args(cmd_parts)
            if not targets:
                context["action_result"] = {"status": "error", "message": "読み取り対象のパスが指定されていません。"}
                return context
            for target in targets:
                if not self._is_allowed_read_path(target):
                    context["action_result"] = {"status": "error", "message": "読み取り対象のパスが許可範囲外です。"}
                    return context
                if self._is_blocked_read_path(target):
                    context["action_result"] = {"status": "error", "message": "読み取り対象のパスが禁止されています。"}
                    return context

        if base_cmd in self.list_commands:
            targets = self._extract_non_option_args(cmd_parts)
            for target in targets:
                if not self._is_allowed_read_path(target):
                    context["action_result"] = {"status": "error", "message": "一覧取得対象のパスが許可範囲外です。"}
                    return context
                if self._is_blocked_read_path(target):
                    context["action_result"] = {"status": "error", "message": "一覧取得対象のパスが禁止されています。"}
                    return context

        if base_cmd in ["python", "py"]:
            script_path = self._extract_python_script_path(cmd_parts)
            if not script_path:
                context["action_result"] = {"status": "error", "message": "python/py はスクリプトファイルの指定が必須です。"}
                return context
            if not self._is_allowed_python_script(script_path):
                context["action_result"] = {"status": "error", "message": "python/py の実行は scripts 配下のスクリプトに限定されています。"}
                return context
            if self.python_allowed_scripts and not self._is_whitelisted_python_script(script_path):
                context["action_result"] = {"status": "error", "message": "python/py の実行は許可されたスクリプトに限定されています。"}
                return context

        # On Windows, prefix built-ins with 'cmd /c'
        shell_builtins = ["echo", "dir", "type", "date", "time"]
        if os.name == 'nt' and base_cmd in shell_builtins:
             actual_cmd = ["cmd", "/c"] + cmd_parts
        else:
             actual_cmd = cmd_parts

        try:
            # Execute with shell=False, passing arguments as a list
            result = subprocess.run(actual_cmd, capture_output=True, text=True, timeout=10, check=False)
            if result.returncode != 0:
                if self.autonomous_learning:
                    self.autonomous_learning.trigger_learning(
                        event_type="ACTION_FAILED",
                        data={"event": "command_failed", "command": cmd_str, "returncode": result.returncode, "stderr": result.stderr}
                    )
            output = result.stdout if result.returncode == 0 else result.stderr
            context["action_result"] = {"status": "success", "message": f"コマンド実行結果:\n{output}"}
        except FileNotFoundError as e:
            context["action_result"] = {"status": "error", "message": f"コマンド '{cmd_parts[0]}' が見つかりません。", "type": "FileNotFoundError"}
        except subprocess.TimeoutExpired as e:
            context["action_result"] = {"status": "error", "message": "コマンドがタイムアウトしました。", "type": "TimeoutExpired"}
        except Exception as e:
            context["action_result"] = {"status": "error", "message": f"コマンドの実行に失敗しました: {e}", "type": type(e).__name__}
            
        return context

    def _ensure_backup_for_action(self, action_method_name: str, parameters: dict, context: dict) -> bool:
        backup_dir = "backup"
        targets = []
        if action_method_name == "_delete_file":
            filename = self._get_entity_value(parameters.get("filename"))
            if filename:
                targets.append(filename)
        elif action_method_name in ["_apply_code_fix", "_apply_refactoring"]:
            filename = self._get_entity_value(parameters.get("filename"))
            if filename:
                targets.append(filename)
        if not targets:
            context["action_result"] = {"status": "error", "message": "バックアップ対象が特定できません。"}
            return False

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        for target in targets:
            src_path = self._safe_join(target)
            if not src_path or not os.path.exists(src_path):
                context["action_result"] = {"status": "error", "message": f"バックアップ対象が見つかりません: {target}"}
                return False
            base_name = os.path.basename(target)
            backup_rel = os.path.join(backup_dir, f"{base_name}.{timestamp}.bak")
            backup_path = self._safe_join(backup_rel)
            if not backup_path:
                context["action_result"] = {"status": "error", "message": "バックアップ先パスが無効です。"}
                return False
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            try:
                shutil.copy2(src_path, backup_path)
            except Exception as e:
                context["action_result"] = {"status": "error", "message": f"バックアップに失敗しました: {e}"}
                return False
        return True

    def _extract_non_option_args(self, cmd_parts: list[str]) -> list[str]:
        args = []
        for part in cmd_parts[1:]:
            if part.startswith("-"):
                continue
            args.append(part)
        return args

    def _extract_python_script_path(self, cmd_parts: list[str]) -> str | None:
        for part in cmd_parts[1:]:
            if part.startswith("-"):
                continue
            return part
        return None

    def _is_allowed_python_script(self, script_path: str) -> bool:
        target = self._safe_join(script_path)
        if not target or not os.path.exists(target):
            return False
        allowed_roots = []
        for rel in self.python_allowed_dirs:
            if not rel:
                continue
            allowed_roots.append(os.path.realpath(os.path.join(self.workspace_root, rel)))
        for root in allowed_roots:
            if target == root:
                continue
            if target.startswith(root + os.sep):
                return True
        return False

    def _is_whitelisted_python_script(self, script_path: str) -> bool:
        target = self._safe_join(script_path)
        if not target:
            return False
        rel = os.path.relpath(target, self.workspace_root)
        rel = normalize_path(rel)
        whitelist = [normalize_path(p) for p in self.python_allowed_scripts]
        return rel in whitelist

    def _is_allowed_read_path(self, path_text: str) -> bool:
        target = self._safe_join(path_text)
        if not target:
            return False
        if not self.read_allowed_dirs:
            return True
        allowed_roots = []
        for rel in self.read_allowed_dirs:
            if not rel:
                continue
            allowed_roots.append(os.path.realpath(os.path.join(self.workspace_root, rel)))
        for root in allowed_roots:
            if target == root:
                return True
            if target.startswith(root + os.sep):
                return True
        return False

    def _is_blocked_read_path(self, path_text: str) -> bool:
        if not self.read_blocked_rules:
            return False
        target = self._safe_join(path_text)
        if not target:
            return True
        rel = normalize_path(os.path.relpath(target, self.workspace_root)).lower()
        return self._matches_blocked_rules(rel, self.read_blocked_rules)

    def _matches_blocked_rules(self, rel_path: str, rules: list[dict]) -> bool:
        if not rel_path:
            return False
        segments = [seg for seg in rel_path.split("/") if seg]
        basename = segments[-1] if segments else ""
        base_no_ext = basename.rsplit(".", 1)[0] if "." in basename else basename
        tokens = self._split_tokens(base_no_ext)
        for rule in rules:
            pattern = str(rule.get("pattern", "")).lower()
            match = str(rule.get("match", "segment")).lower()
            if not pattern:
                continue
            if match == "basename_exact" and basename == pattern:
                return True
            if match == "segment":
                if pattern in tokens:
                    return True
        return False

    def _split_tokens(self, text: str) -> list[str]:
        tokens = []
        current = []
        for ch in str(text):
            if ch.isalnum():
                current.append(ch.lower())
            else:
                if current:
                    tokens.append("".join(current))
                    current = []
        if current:
            tokens.append("".join(current))
        return tokens

    def _safe_join(self, filename):
        if not filename or '\0' in filename:
            return None

        # Resolve the real path of the workspace root (follows symlinks)
        workspace_real = os.path.realpath(self.workspace_root)
        
        try:
            # 外部ユーティリティで正規化
            from src.utils.context_utils import normalize_path
            filename = normalize_path(filename)
            
            # Join and resolve the real path of the target file
            target_path = os.path.join(workspace_real, filename)
            target_real = os.path.realpath(target_path)
        except (ValueError, TypeError):
            return None

        # Block Windows UNC paths
        if os.name == 'nt' and (target_real.startswith('\\\\') or target_path.startswith('\\\\')):
            return None
        
        # Ensure the target path is strictly within the workspace root
        # Using realpath handles symbolic link attacks
        if not target_real.startswith(workspace_real + os.sep) and target_real != workspace_real:
            return None
            
        return target_real

    def _move_file(self, context, parameters):
        return self.file_ops.move_file(context, parameters)

    def _copy_file(self, context, parameters):
        return self.file_ops.copy_file(context, parameters)

    def _analyze_csharp(self, context, parameters):
        return self.csharp_ops.analyze_csharp(context, parameters)

    def _run_dotnet_test(self, context: dict, parameters: dict) -> dict:
        return self.csharp_ops.run_dotnet_test(context, parameters)

    def _parse_dotnet_test_result(self, output: str) -> dict:
        return self.csharp_ops.parse_dotnet_test_result(output)

    def _get_cwd(self, context, parameters):
        """Returns the current working directory relative to workspace root (which is usually just '.')"""
        # Since we simulate workspace root as the environment, we might just return the workspace path
        # or just confirm we are at root.
        # But users might think of 'cd' logic. We don't support 'cd' yet (stateful CWD).
        # So we return the absolute path of workspace root.
        context["action_result"] = {"status": "success", "message": f"現在の作業ディレクトリ: {self.workspace_root}"}
        return context

    def get_required_entities_for_intent(self, intent: str) -> list:
        """
        Returns a list of entity keys required for a given intent to execute successfully.
        """
        if intent == "FILE_CREATE":
            return ["filename", "content"]
        elif intent == "FILE_READ":
            return ["filename"]
        elif intent == "FILE_APPEND":
            return ["filename", "content"]
        elif intent == "FILE_DELETE":
            return ["filename"]
        elif intent == "FILE_MOVE":
            return ["source_filename", "destination_filename"]
        elif intent == "FILE_COPY":
            return ["source_filename", "destination_filename"]
        elif intent == "BACKUP_AND_DELETE":
            return ["source_filename", "destination_filename"]
        elif intent == "READ_AND_CREATE":
            return ["source_filename", "destination_filename", "content"]
        elif intent == "LIST_DIR":
            # 'directory' is optional, defaults to '.'
            return [] 
        elif intent == "CMD_RUN":
            return ["command"]
        elif intent == "GET_CWD":
            return []
        elif intent == "CS_ANALYZE":
            return ["filename"]
        elif intent == "CS_TEST_RUN":
            return ["project_path"]
        elif intent == "GENERATE_TESTS":
            return ["filename"]
        elif intent == "CS_QUERY_ANALYSIS":
            # output_path and query_type are always required.
            # target_name is required for most query_types, but not for "unused_methods".
            # For simplicity, we'll keep target_name as required for the intent and handle its optionality in _query_csharp_analysis_results.
            return ["output_path", "query_type", "target_name"]
        elif intent == "MEASURE_COVERAGE":
            return ["project_path", "language"]
        elif intent == "ANALYZE_COVERAGE_GAPS":
            return ["project_path", "language"]
        elif intent == "GENERATE_COVERAGE_REPORT":
            return ["project_path", "language"]
        elif intent == "ANALYZE_REFACTORING":
            return ["project_path", "language"]
        elif intent == "SUGGEST_REFACTORING":
            return ["project_path", "language"]
        elif intent == "APPLY_REFACTORING":
            return ["project_path", "suggestion_id"]
        elif intent == "QUALITY_CHECK":
            return [] # metrics_file is optional
        elif intent == "DOC_GEN":
            return ["target_file"]
        elif intent == "DOC_REFINE":
            return ["filename"]
        elif intent == "RUN_LEARNING_CYCLE":
            return []
        elif intent == "MANAGE_KNOWLEDGE":
            return ["operation"]
        elif intent == "REVERSE_DICTIONARY_SEARCH":
            return ["query"]
        elif intent == "EXECUTE_GOAL_DRIVEN_TDD":
            return ["goal_description", "acceptance_criteria"]
        return []


    def _load_error_patterns(self, filepath: str) -> list:
        """Loads error patterns from a JSON file."""
        if not os.path.exists(filepath):
            return []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f).get("error_patterns", [])
        except Exception as e:
            return []

    def _handle_exception_with_patterns(self, exc: Exception, default_message: str) -> dict:
        """
        Matches an exception against loaded patterns and returns a structured error message.
        """
        error_message = str(exc)
        
        # Trigger autonomous learning for any action failure
        if self.autonomous_learning:
            self.autonomous_learning.trigger_learning(
                event_type="ACTION_FAILED", 
                data={"error_type": exc.__class__.__name__, "message": error_message}
            )

        for pattern_obj in self.error_patterns:
            try:
                if (pattern_obj["type"] == exc.__class__.__name__) and \
                   re.search(pattern_obj["regex"], error_message): # Match by regex and exception type
                    return {
                        "status": "error",
                        "message": pattern_obj["user_message"],
                        "suggested_action": pattern_obj["suggested_action"],
                        "original_error": error_message
                    }
            except re.error:
                continue # Skip invalid regex patterns
        
        # Fallback to default generic message
        return {
            "status": "error", 
            "message": default_message, 
            "original_error": error_message,
            "original_error_type": exc.__class__.__name__ # Add this
        }


    def _get_entity_value(self, entity_data, default=None):
        """Extracts the 'value' from an entity dict or returns the data itself if it's a string."""
        if isinstance(entity_data, dict) and "value" in entity_data:
            return entity_data["value"]
        return entity_data # Already a string or None, or other type

    def _generate_test_cases(self, context: dict, parameters: dict) -> dict:
        return self.test_ops.generate_test_cases(context, parameters)

    def _load_csharp_analysis_results(self, output_path: str) -> tuple[dict, dict]:
        return self.csharp_ops.load_csharp_analysis_results(output_path)

    def _recursively_find_callers(self, target_method_id: str, all_detail_objects_by_id: dict, visited_methods: set) -> set:
        return self.csharp_ops.recursively_find_callers(target_method_id, all_detail_objects_by_id, visited_methods)

    def _query_csharp_analysis_results(self, context: dict, parameters: dict) -> dict:
        return self.csharp_ops.query_csharp_analysis_results(context, parameters)
    def _measure_coverage(self, context: dict, parameters: dict) -> dict:
        return self.test_ops.measure_coverage(context, parameters)

    def _analyze_coverage_gaps(self, context: dict, parameters: dict) -> dict:
        return self.test_ops.analyze_coverage_gaps(context, parameters)

    def _generate_coverage_report(self, context: dict, parameters: dict) -> dict:
        return self.test_ops.generate_coverage_report(context, parameters)
    def _analyze_refactoring(self, context: dict, parameters: dict) -> dict:
        return self.ref_ops.analyze_refactoring(context, parameters)

    def _suggest_refactoring(self, context: dict, parameters: dict) -> dict:
        return self.ref_ops.suggest_refactoring(context, parameters)

    def _apply_refactoring(self, context: dict, parameters: dict) -> dict:
        return self.ref_ops.apply_refactoring(context, parameters)
    def _setup_cicd_pipeline(self, context: dict, parameters: dict) -> dict:
        return self.cicd_ops.setup_cicd_pipeline(context, parameters)
    
    def _configure_quality_gates(self, context: dict, parameters: dict) -> dict:
        return self.cicd_ops.configure_quality_gates(context, parameters)
    
    def _generate_cicd_config(self, context: dict, parameters: dict) -> dict:
        return self.cicd_ops.generate_cicd_config(context, parameters)
    
    def _find_latest_report(self, report_dir: str) -> dict:
        return self.cicd_ops.find_latest_report(report_dir)
    # ===== 高度TDD支援機能 (Phase 3-4) =====
    
    def _analyze_test_failure(self, context: dict, parameters: dict) -> dict:
        return self.tdd_ops.analyze_test_failure(context)
    
    def _execute_goal_driven_tdd(self, context: dict, parameters: dict) -> dict:
        return self.tdd_ops.execute_goal_driven_tdd(context)
    
    def _apply_code_fix(self, context: dict, parameters: dict) -> dict:
        return self.tdd_ops.apply_code_fix(context)
    
    def _validate_code_syntax(self, file_path: str, relative_path: str) -> dict:
        return self.tdd_ops.validate_code_syntax(file_path, relative_path)
    
    def _check_quality_gates(self, context: dict, parameters: dict) -> dict:
        return self.cicd_ops.check_quality_gates(context, parameters)
        # TODO: Implement Logic: **実行と例外ハンドリング**:
