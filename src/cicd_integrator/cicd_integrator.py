# -*- coding: utf-8 -*-
# src/cicd_integrator/cicd_integrator.py

"""
CI/CD統合機能モジュール
GitHub Actions、品質ゲート、パイプライン設定の統合管理を提供
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict


class CICDIntegrator:
    """CI/CD統合の中心的なコントローラー"""
    
    def __init__(self, workspace_root: str = ".", log_manager=None):
        self.workspace_root = Path(workspace_root)
        self.log_manager = log_manager
        self.config = self._load_cicd_config()
        self.generators = {
            "github_actions": GitHubActionsGenerator(self.config),
            "azure_devops": AzureDevOpsGenerator(self.config),
            "jenkins": JenkinsGenerator(self.config)
        }
        self.quality_gate_manager = QualityGateManager(self.config)
        self.report_integrator = QualityReportIntegrator(self.config)
    
    def _load_cicd_config(self) -> Dict[str, Any]:
        """CI/CD設定を読み込む"""
        config_path = self.workspace_root / "resources" / "cicd_config.json"
        
        # デフォルト設定
        default_config = {
            "platforms": {
                "github_actions": {
                    "enabled": True,
                    "workflow_path": ".github/workflows",
                    "default_runner": "ubuntu-latest"
                },
                "azure_devops": {
                    "enabled": False,
                    "pipeline_path": "azure-pipelines.yml"
                },
                "jenkins": {
                    "enabled": False,
                    "pipeline_path": "Jenkinsfile"
                }
            },
            "quality_gates": {
                "test_coverage_threshold": 80,
                "quality_score_threshold": 7.0,
                "max_high_priority_smells": 0,
                "max_medium_priority_smells": 5,
                "timeout_seconds": 300
            },
            "notifications": {
                "pr_comments": True,
                "slack_enabled": False,
                "email_enabled": False
            },
            "language_configs": {
                "csharp": {
                    "build_command": "dotnet build",
                    "test_command": "dotnet test",
                    "coverage_tool": "coverlet",
                    "package_restore": "dotnet restore"
                },
                "python": {
                    "build_command": "py -m pip install -r requirements.txt",
                    "test_command": "py -m unittest discover -s tests -p \"test_*.py\" -t .",
                    "coverage_tool": "coverage",
                    "package_restore": "py -m pip install -r requirements.txt"
                },
                "javascript": {
                    "build_command": "npm run build",
                    "test_command": "npm test",
                    "coverage_tool": "jest",
                    "package_restore": "npm install"
                }
            },
            "quality_tool_commands": {
                "refactoring_analyzer": "python -m src.refactoring_analyzer.refactoring_analyzer",
                "quality_gate_checker": "python -m src.cicd_integrator.quality_gate_checker"
            }
        }
        
        try:
            if config_path.exists():
                with config_path.open('r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                # デフォルト設定とマージ
                self._deep_merge_config(default_config, loaded_config)
        except Exception as e:
            if self.log_manager:
                self.log_manager.log_event("cicd_config_error", {"error": str(e)}, "WARNING")
        
        return default_config
    
    def _deep_merge_config(self, base_config: Dict[str, Any], override_config: Dict[str, Any]) -> None:
        """設定の深いマージを実行"""
        for key, value in override_config.items():
            if key in base_config and isinstance(value, dict) and isinstance(base_config[key], dict):
                self._deep_merge_config(base_config[key], value)
            else:
                base_config[key] = value
    
    def generate_pipeline(self, project_info: Dict[str, Any], options: Dict[str, Any] = None) -> Dict[str, Any]:
        """CI/CDパイプラインを生成"""
        options = options or {}
        
        try:
            if self.log_manager:
                self.log_manager.log_event("pipeline_generation_start", {
                    "project_name": project_info.get("name", "unknown"),
                    "language": project_info.get("language", "unknown"),
                    "platform": project_info.get("ci_platform", "github_actions")
                })
            
            # プロジェクト情報の検証
            validation_result = self._validate_project_info(project_info)
            if not validation_result["valid"]:
                return {
                    "status": "error",
                    "message": f"プロジェクト情報が無効です: {validation_result['errors']}"
                }
            
            platform = project_info.get("ci_platform", "github_actions")
            
            if platform not in self.generators:
                return {
                    "status": "error",
                    "message": f"サポートされていないCI/CDプラットフォームです: {platform}"
                }
            
            # パイプライン生成
            generator = self.generators[platform]
            pipeline_config = generator.generate_pipeline(project_info, options)
            
            # 品質ゲート設定
            quality_gates = self.quality_gate_manager.setup_gates(
                project_info.get("quality_gates", {}), 
                project_info.get("language")
            )
            
            # 設定ファイル生成
            config_files = self._generate_config_files(platform, pipeline_config, project_info)
            
            # 結果統合
            result = {
                "status": "success",
                "platform": platform,
                "project_info": project_info,
                "pipeline_config": pipeline_config,
                "quality_gates": quality_gates,
                "config_files": config_files,
                "generated_at": datetime.now().isoformat()
            }
            
            if self.log_manager:
                self.log_manager.log_event("pipeline_generation_complete", {
                    "platform": platform,
                    "config_files_count": len(config_files),
                    "quality_gates_count": len(quality_gates)
                })
            
            return result
            
        except Exception as e:
            error_result = {
                "status": "error",
                "message": f"パイプライン生成中にエラーが発生しました: {str(e)}",
                "project_info": project_info,
                "error_type": type(e).__name__
            }
            
            if self.log_manager:
                self.log_manager.log_event("pipeline_generation_error", {
                    "project_name": project_info.get("name", "unknown"),
                    "error": str(e),
                    "error_type": type(e).__name__
                }, "ERROR")
            
            return error_result
    
    def setup_quality_gates(self, quality_config: Dict[str, Any], language: str = "csharp") -> Dict[str, Any]:
        """品質ゲートを設定"""
        try:
            if self.log_manager:
                self.log_manager.log_event("quality_gates_setup_start", {
                    "language": language,
                    "config_keys": list(quality_config.keys())
                })
            
            gates = self.quality_gate_manager.setup_gates(quality_config, language)
            
            result = {
                "status": "success",
                "language": language,
                "gates": gates,
                "total_gates": len(gates),
                "blocking_gates": len([g for g in gates if g.get("type") == "blocking"]),
                "warning_gates": len([g for g in gates if g.get("type") == "warning"])
            }
            
            if self.log_manager:
                self.log_manager.log_event("quality_gates_setup_complete", {
                    "total_gates": result["total_gates"],
                    "blocking_gates": result["blocking_gates"],
                    "warning_gates": result["warning_gates"]
                })
            
            return result
            
        except Exception as e:
            error_result = {
                "status": "error",
                "message": f"品質ゲート設定中にエラーが発生しました: {str(e)}",
                "language": language,
                "error_type": type(e).__name__
            }
            
            if self.log_manager:
                self.log_manager.log_event("quality_gates_setup_error", {
                    "language": language,
                    "error": str(e),
                    "error_type": type(e).__name__
                }, "ERROR")
            
            return error_result
    
    def integrate_quality_reports(self, reports: List[Dict[str, Any]], options: Dict[str, Any] = None) -> Dict[str, Any]:
        """品質レポートを統合"""
        options = options or {}
        
        try:
            if self.log_manager:
                self.log_manager.log_event("report_integration_start", {
                    "reports_count": len(reports),
                    "report_types": [r.get("type", "unknown") for r in reports]
                })
            
            integrated_report = self.report_integrator.integrate_reports(reports, options)
            
            # 統合レポートファイルの生成
            output_formats = options.get("output_formats", ["json", "html"])
            report_files = self._generate_integrated_reports(integrated_report, output_formats)
            
            result = {
                "status": "success",
                "integrated_report": integrated_report,
                "report_files": report_files,
                "summary": {
                    "total_reports": len(reports),
                    "overall_score": integrated_report.get("overall_score", 0),
                    "quality_trend": integrated_report.get("quality_trend", "stable")
                }
            }
            
            if self.log_manager:
                self.log_manager.log_event("report_integration_complete", {
                    "overall_score": result["summary"]["overall_score"],
                    "report_files_count": len(report_files)
                })
            
            return result
            
        except Exception as e:
            error_result = {
                "status": "error",
                "message": f"レポート統合中にエラーが発生しました: {str(e)}",
                "reports_count": len(reports),
                "error_type": type(e).__name__
            }
            
            if self.log_manager:
                self.log_manager.log_event("report_integration_error", {
                    "reports_count": len(reports),
                    "error": str(e),
                    "error_type": type(e).__name__
                }, "ERROR")
            
            return error_result
    
    def _validate_project_info(self, project_info: Dict[str, Any]) -> Dict[str, Any]:
        """プロジェクト情報を検証"""
        errors = []
        
        required_fields = ["name", "language"]
        for field in required_fields:
            if field not in project_info or not project_info[field]:
                errors.append(f"必須フィールド '{field}' が不足しています")
        
        # 言語サポートチェック
        language = project_info.get("language")
        if language and language not in self.config.get("language_configs", {}):
            errors.append(f"サポートされていない言語です: {language}")
        
        # CI/CDプラットフォームチェック
        platform = project_info.get("ci_platform", "github_actions")
        if platform not in self.generators:
            errors.append(f"サポートされていないCI/CDプラットフォームです: {platform}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def _generate_config_files(self, platform: str, pipeline_config: Dict[str, Any], project_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """設定ファイルを生成"""
        config_files = []
        
        try:
            generator = self.generators[platform]
            files = generator.generate_config_files(pipeline_config, project_info)
            config_files.extend(files)
            
        except Exception as e:
            if self.log_manager:
                self.log_manager.log_event("config_file_generation_error", {
                    "platform": platform,
                    "error": str(e)
                }, "ERROR")
        
        return config_files
    
    def _generate_integrated_reports(self, integrated_report: Dict[str, Any], output_formats: List[str]) -> List[Dict[str, str]]:
        """統合レポートファイルを生成"""
        report_files = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_dir = self.workspace_root / "cicd_reports"
        report_dir.mkdir(exist_ok=True)
        
        # JSON レポート
        if "json" in output_formats:
            json_path = report_dir / f"integrated_report_{timestamp}.json"
            try:
                with json_path.open('w', encoding='utf-8') as f:
                    json.dump(integrated_report, f, ensure_ascii=False, indent=2)
                report_files.append({"type": "json", "path": str(json_path)})
            except Exception as e:
                if self.log_manager:
                    self.log_manager.log_event("json_report_error", {"error": str(e)}, "ERROR")
        
        # HTML レポート
        if "html" in output_formats:
            html_path = report_dir / f"integrated_report_{timestamp}.html"
            try:
                html_content = self._generate_html_report(integrated_report)
                with html_path.open('w', encoding='utf-8') as f:
                    f.write(html_content)
                report_files.append({"type": "html", "path": str(html_path)})
            except Exception as e:
                if self.log_manager:
                    self.log_manager.log_event("html_report_error", {"error": str(e)}, "ERROR")
        
        return report_files
    
    def _generate_html_report(self, integrated_report: Dict[str, Any]) -> str:
        """HTML統合レポートを生成"""
        return f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CI/CD統合品質レポート</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background: #2196f3; color: white; padding: 20px; border-radius: 5px; }}
        .summary {{ background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .metric {{ display: inline-block; margin: 10px; padding: 15px; background: white; border-radius: 3px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .score {{ font-size: 2em; font-weight: bold; }}
        .good {{ color: #4caf50; }}
        .warning {{ color: #ff9800; }}
        .error {{ color: #f44336; }}
        .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>CI/CD統合品質レポート</h1>
        <p>生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    
    <div class="summary">
        <h2>総合品質スコア</h2>
        <div class="metric">
            <div class="score {'good' if integrated_report.get('overall_score', 0) >= 8 else 'warning' if integrated_report.get('overall_score', 0) >= 6 else 'error'}">
                {integrated_report.get('overall_score', 0):.1f}/10
            </div>
            <div>総合スコア</div>
        </div>
        <div class="metric">
            <div class="score">
                {integrated_report.get('test_coverage', 0):.1f}%
            </div>
            <div>テストカバレッジ</div>
        </div>
        <div class="metric">
            <div class="score">
                {integrated_report.get('quality_issues', 0)}
            </div>
            <div>品質問題</div>
        </div>
    </div>
    
    <div class="section">
        <h3>品質トレンド</h3>
        <p>トレンド: <strong>{integrated_report.get('quality_trend', 'stable')}</strong></p>
        <p>前回比較: {integrated_report.get('trend_description', '初回分析のため比較データなし')}</p>
    </div>
    
    <div class="section">
        <h3>推奨アクション</h3>
        <ul>
            {''.join([f'<li>{action}</li>' for action in integrated_report.get('recommended_actions', [])])}
        </ul>
    </div>
    
    <p><small>このレポートはCI/CD統合機能により自動生成されました</small></p>
</body>
</html>"""


class GitHubActionsGenerator:
    """GitHub Actionsワークフロー生成器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    def generate_pipeline(self, project_info: Dict[str, Any], options: Dict[str, Any]) -> Dict[str, Any]:
        """GitHub Actionsパイプラインを生成"""
        language = project_info.get("language", "csharp")
        language_config = self.config.get("language_configs", {}).get(language, {})
        
        workflow = {
            "name": f"CI/CD Pipeline - {project_info.get('name', 'Project')}",
            "on": {
                "push": {"branches": ["main", "develop"]},
                "pull_request": {"branches": ["main"]}
            },
            "jobs": {
                "quality-check": {
                    "runs-on": self.config.get("platforms", {}).get("github_actions", {}).get("default_runner", "ubuntu-latest"),
                    "steps": self._generate_quality_steps(language, language_config, project_info)
                }
            }
        }
        
        return {
            "workflow": workflow,
            "language": language,
            "steps_count": len(workflow["jobs"]["quality-check"]["steps"])
        }
    
    def _generate_quality_steps(self, language: str, language_config: Dict[str, Any], project_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """品質チェックステップを生成"""
        steps = [
            {"name": "Checkout code", "uses": "actions/checkout@v3"},
        ]
        
        # 言語固有のセットアップ
        if language == "csharp":
            steps.extend([
                {
                    "name": "Setup .NET",
                    "uses": "actions/setup-dotnet@v3",
                    "with": {"dotnet-version": project_info.get("framework", "6.0.x")}
                },
                {
                    "name": "Restore dependencies",
                    "run": language_config.get("package_restore", "dotnet restore")
                }
            ])
        elif language == "python":
            steps.extend([
                {
                    "name": "Setup Python",
                    "uses": "actions/setup-python@v4",
                    "with": {"python-version": project_info.get("python_version", "3.9")}
                },
                {
                    "name": "Install dependencies",
                    "run": language_config.get("package_restore", "pip install -r requirements.txt")
                }
            ])
        elif language == "javascript":
            steps.extend([
                {
                    "name": "Setup Node.js",
                    "uses": "actions/setup-node@v3",
                    "with": {"node-version": project_info.get("node_version", "16")}
                },
                {
                    "name": "Install dependencies",
                    "run": language_config.get("package_restore", "npm install")
                }
            ])
        
        # 品質チェックステップ
        quality_analyzer_cmd = self.config.get("quality_tool_commands", {}).get("refactoring_analyzer", "echo 'Refactoring analyzer command not configured'")
        quality_gate_cmd = self.config.get("quality_tool_commands", {}).get("quality_gate_checker", "echo 'Quality gate checker command not configured'")

        steps.extend([
            {
                "name": "Build project",
                "run": language_config.get("build_command", "echo 'No build command specified'")
            },
            {
                "name": "Run tests",
                "run": language_config.get("test_command", "echo 'No test command specified'")
            },
            {
                "name": "Generate test coverage",
                "run": self._get_coverage_command(language, language_config)
            },
            {
                "name": "Run code quality analysis",
                "run": quality_analyzer_cmd
            },
            {
                "name": "Quality gate check",
                "run": quality_gate_cmd
            }
        ])
        
        return steps
    
    def _get_coverage_command(self, language: str, language_config: Dict[str, Any]) -> str:
        """カバレッジコマンドを取得"""
        coverage_commands = {
            "csharp": "dotnet test --collect:'XPlat Code Coverage'",
            "python": "py -m coverage run --source=src -m unittest discover -s tests -p \"test_*.py\" -t . && py -m coverage report",
            "javascript": "npm run test -- --coverage"
        }
        return coverage_commands.get(language, "echo 'Coverage not configured'")
    
    def generate_config_files(self, pipeline_config: Dict[str, Any], project_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """設定ファイルを生成"""
        config_files = []
        
        # GitHub Actionsワークフローファイル
        workflow_path = ".github/workflows/ci-cd.yml"
        workflow_content = self._dict_to_yaml(pipeline_config["workflow"])
        
        config_files.append({
            "path": workflow_path,
            "content": workflow_content,
            "type": "yaml",
            "description": "GitHub Actions CI/CDワークフロー"
        })
        
        return config_files
    
    def _dict_to_yaml(self, data: Dict[str, Any], indent: int = 0) -> str:
        """辞書をYAML形式の文字列に変換（再帰的実装）"""
        lines = []
        indent_str = "  " * indent
        
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"{indent_str}{key}:")
                lines.append(self._dict_to_yaml(value, indent + 1))
            elif isinstance(value, list):
                lines.append(f"{indent_str}{key}:")
                for item in value:
                    if isinstance(item, dict):
                        # リスト内の辞書: "- key: value" の形式にする
                        first_key = True
                        for sub_key, sub_value in item.items():
                            if first_key:
                                lines.append(f"{indent_str}- {sub_key}:")
                                # 値が辞書やリストの場合は再帰処理が必要だが、
                                # ここでは簡易的に直下の値がスカラーかネストかを判定
                                if isinstance(sub_value, (dict, list)):
                                    # ネストしている場合は次の行にインデントして記述
                                    lines.append(self._dict_to_yaml(sub_value, indent + 2))
                                else:
                                    # スカラー値の場合は上書きして1行にする
                                    lines[-1] = f"{indent_str}- {sub_key}: {self._format_value(sub_value)}"
                                first_key = False
                            else:
                                if isinstance(sub_value, (dict, list)):
                                    lines.append(f"{indent_str}  {sub_key}:")
                                    lines.append(self._dict_to_yaml(sub_value, indent + 2))
                                else:
                                    lines.append(f"{indent_str}  {sub_key}: {self._format_value(sub_value)}")
                    else:
                        lines.append(f"{indent_str}- {self._format_value(item)}")
            else:
                lines.append(f"{indent_str}{key}: {self._format_value(value)}")
        
        return "\n".join(lines)

    def _format_value(self, value: Any) -> str:
        """YAML値のフォーマット（クォート処理など）"""
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, str):
            if ":" in value or "#" in value or value.strip() == "":
                return f'"{value}"'
        return str(value)


class AzureDevOpsGenerator:
    """Azure DevOpsパイプライン生成器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    def generate_pipeline(self, project_info: Dict[str, Any], options: Dict[str, Any]) -> Dict[str, Any]:
        """Azure DevOpsパイプラインを生成"""
        language = project_info.get("language", "csharp")
        language_config = self.config.get("language_configs", {}).get(language, {})
        
        # 基本構成
        pipeline = {
            "trigger": ["main"],
            "pool": {
                "vmImage": "ubuntu-latest"
            },
            "steps": []
        }
        
        # 言語固有のステップ生成
        steps = []
        
        if language == "csharp":
            steps.append({
                "task": "UseDotNet@2",
                "displayName": "Use .NET Core sdk",
                "inputs": {"packageType": "sdk", "version": "6.x"}
            })
            steps.append({
                "script": language_config.get("package_restore", "dotnet restore"),
                "displayName": "Restore dependencies"
            })
            steps.append({
                "script": language_config.get("build_command", "dotnet build --configuration Release"),
                "displayName": "Build"
            })
            steps.append({
                "script": language_config.get("test_command", "dotnet test --no-build --configuration Release --collect 'XPlat Code Coverage'"),
                "displayName": "Test"
            })
            
        elif language == "python":
            steps.append({
                "task": "UsePythonVersion@0",
                "inputs": {"versionSpec": "3.9", "addToPath": True}
            })
            steps.append({
                "script": language_config.get("package_restore", "pip install -r requirements.txt"),
                "displayName": "Install dependencies"
            })
            steps.append({
                "script": "pip install pytest pytest-azurepipelines coverage",
                "displayName": "Install test tools"
            })
            steps.append({
                "script": language_config.get("test_command", "python -m pytest"),
                "displayName": "Test"
            })
            
        elif language == "javascript":
            steps.append({
                "task": "NodeTool@0",
                "inputs": {"versionSpec": "16.x"}
            })
            steps.append({
                "script": language_config.get("package_restore", "npm install"),
                "displayName": "Install dependencies"
            })
            steps.append({
                "script": language_config.get("build_command", "npm run build"),
                "displayName": "Build"
            })
            steps.append({
                "script": language_config.get("test_command", "npm test"),
                "displayName": "Test"
            })
            
        # Quality Gate Check
        quality_gate_cmd = self.config.get("quality_tool_commands", {}).get("quality_gate_checker", "echo 'Quality gate checker command not configured'")
        steps.append({
            "script": quality_gate_cmd,
            "displayName": "Check Quality Gates"
        })
        
        pipeline["steps"] = steps
        
        return {
            "pipeline": pipeline,
            "language": language
        }
    
    def generate_config_files(self, pipeline_config: Dict[str, Any], project_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """設定ファイルを生成"""
        config_files = []
        yaml_content = self._dict_to_yaml_simple(pipeline_config["pipeline"])
        
        config_files.append({
            "path": "azure-pipelines.yml",
            "content": yaml_content,
            "type": "yaml",
            "description": "Azure DevOps Pipeline definition"
        })
        return config_files

    def _dict_to_yaml_simple(self, data: Dict[str, Any], indent: int = 0) -> str:
        """簡易的なYAML変換"""
        lines = []
        indent_str = "  " * indent
        
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"{indent_str}{key}:")
                lines.append(self._dict_to_yaml_simple(value, indent + 1))
            elif isinstance(value, list):
                lines.append(f"{indent_str}{key}:")
                for item in value:
                    if isinstance(item, dict):
                        # リスト内の辞書の最初のキーにはハイフンをつける
                        first = True
                        for sub_key, sub_val in item.items():
                            if first:
                                lines.append(f"{indent_str}- {sub_key}: {sub_val}")
                                first = False
                            else:
                                lines.append(f"{indent_str}  {sub_key}: {sub_val}")
                    else:
                        lines.append(f"{indent_str}- {item}")
            else:
                lines.append(f"{indent_str}{key}: {value}")
        return "\n".join(lines)


class JenkinsGenerator:
    """Jenkinsパイプライン生成器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    def generate_pipeline(self, project_info: Dict[str, Any], options: Dict[str, Any]) -> Dict[str, Any]:
        """Jenkinsパイプラインを生成"""
        language = project_info.get("language", "csharp")
        language_config = self.config.get("language_configs", {}).get(language, {})
        
        pipeline = {
            "agent": "any",
            "stages": [
                {
                    "name": "Build",
                    "steps": [language_config.get("package_restore", "echo restore"), language_config.get("build_command", "echo build")]
                },
                {
                    "name": "Test",
                    "steps": [language_config.get("test_command", "echo test")]
                },
                {
                    "name": "Quality Gate",
                    "steps": [self.config.get("quality_tool_commands", {}).get("quality_gate_checker", "echo 'Quality gate checker command not configured'")]
                }
            ]
        }
        
        return {
            "pipeline": pipeline,
            "language": language
        }
    
    def generate_config_files(self, pipeline_config: Dict[str, Any], project_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """設定ファイルを生成"""
        pipeline = pipeline_config["pipeline"]
        
        jenkinsfile_content = "pipeline {\n"
        jenkinsfile_content += f"    agent {pipeline['agent']}\n"
        jenkinsfile_content += "    stages {\n"
        
        for stage in pipeline["stages"]:
            jenkinsfile_content += f"        stage('{stage['name']}') {{'\n"
            jenkinsfile_content += "            steps {\n"
            for step in stage["steps"]:
                # WindowsバッチかUnixシェルか判定が必要だが、ここではshとする
                jenkinsfile_content += f"                sh '{step}'\n"
            jenkinsfile_content += "            }\n"
            jenkinsfile_content += "        }\n"
            
        jenkinsfile_content += "    }\n"
        jenkinsfile_content += "}\n"
        
        return [{
            "path": "Jenkinsfile",
            "content": jenkinsfile_content,
            "type": "groovy",
            "description": "Jenkins Declarative Pipeline"
        }]


class QualityGateManager:
    """品質ゲート管理器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    def setup_gates(self, quality_config: Dict[str, Any], language: str) -> List[Dict[str, Any]]:
        """品質ゲートを設定"""
        base_config = self.config.get("quality_gates", {})
        merged_config = {**base_config, **quality_config}
        
        gates = [
            {
                "name": "test_execution",
                "type": "blocking",
                "condition": "all_tests_pass",
                "description": "全テストが成功すること",
                "timeout": merged_config.get("timeout_seconds", 300)
            },
            {
                "name": "coverage_check",
                "type": "blocking",
                "condition": f"coverage >= {merged_config.get('test_coverage_threshold', 80)}",
                "description": f"テストカバレッジが{merged_config.get('test_coverage_threshold', 80)}%以上であること",
                "metric": "line_coverage"
            },
            {
                "name": "quality_score",
                "type": "warning",
                "condition": f"quality_score >= {merged_config.get('quality_score_threshold', 7.0)}",
                "description": f"品質スコアが{merged_config.get('quality_score_threshold', 7.0)}以上であること",
                "metric": "overall_quality_score"
            },
            {
                "name": "high_priority_smells",
                "type": "blocking",
                "condition": f"high_priority_smells <= {merged_config.get('max_high_priority_smells', 0)}",
                "description": f"高優先度のコードスメルが{merged_config.get('max_high_priority_smells', 0)}個以下であること",
                "metric": "high_priority_smell_count"
            },
            {
                "name": "medium_priority_smells",
                "type": "warning",
                "condition": f"medium_priority_smells <= {merged_config.get('max_medium_priority_smells', 5)}",
                "description": f"中優先度のコードスメルが{merged_config.get('max_medium_priority_smells', 5)}個以下であること",
                "metric": "medium_priority_smell_count"
            }
        ]
        
        return gates
    
    def evaluate_gate(self, gate_config: Dict[str, Any], metrics: Dict[str, Any]) -> Dict[str, Any]:
        """品質ゲートを評価"""
        gate_name = gate_config.get("name", "unknown")
        condition = gate_config.get("condition", "")
        gate_type = gate_config.get("type", "warning")
        
        try:
            # 簡易的な条件評価（実際の実装では安全な評価器を使用）
            result = self._evaluate_condition(condition, metrics)
            
            return {
                "gate_name": gate_name,
                "type": gate_type,
                "condition": condition,
                "result": result,
                "status": "passed" if result else "failed",
                "message": f"ゲート '{gate_name}' {"通過" if result else "失敗"}"
            }
            
        except Exception as e:
            return {
                "gate_name": gate_name,
                "type": gate_type,
                "condition": condition,
                "result": False,
                "status": "error",
                "message": f"ゲート評価エラー: {str(e)}"
            }
    
    def _evaluate_condition(self, condition: str, metrics: Dict[str, Any]) -> bool:
        """条件を安全に評価"""
        try:
            # メトリクス値の取得と正規化
            # 例: condition = "coverage >= 80"
            parts = condition.split()
            if len(parts) != 3:
                return False
                
            metric_key = parts[0]
            operator = parts[1]
            threshold_str = parts[2]
            
            # メトリクス値の取得
            metric_val = metrics.get(metric_key)
            if metric_val is None:
                # all_tests_pass="True" のようなケースへの対応
                if metric_key == "all_tests_pass" and condition == "all_tests_pass":
                    return metrics.get("all_tests_pass", False)
                return False
            
            # 数値変換の試行
            try:
                threshold = float(threshold_str)
                val = float(metric_val)
            except ValueError:
                # ブール値または文字列比較
                if threshold_str.lower() == "true": threshold = True
                elif threshold_str.lower() == "false": threshold = False
                else: 
                    # クォート除去 ('foo' -> foo)
                    threshold = threshold_str.strip("'" ).strip('"')
                val = metric_val
                
            # 比較演算
            if operator == ">=": return val >= threshold
            elif operator == ">": return val > threshold
            elif operator == "<=": return val <= threshold
            elif operator == "<": return val < threshold
            elif operator == "==": return val == threshold
            elif operator == "!=": return val != threshold
            
            return False
            
        except Exception:
            # フォールバック: 元の簡易実装ロジックの一部を再利用
            if "coverage >=" in condition:
                t = float(condition.split(">=")[1].strip())
                return metrics.get("coverage", 0) >= t
            
            return False


class QualityReportIntegrator:
    """品質レポート統合器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    def integrate_reports(self, reports: List[Dict[str, Any]], options: Dict[str, Any]) -> Dict[str, Any]:
        """複数の品質レポートを統合"""
        integrated = {
            "overall_score": 0,
            "test_coverage": 0,
            "quality_issues": 0,
            "quality_trend": "stable",
            "trend_description": "初回分析のため比較データなし",
            "recommended_actions": [],
            "report_details": {},
            "integration_timestamp": datetime.now().isoformat()
        }
        
        # レポートタイプ別の処理
        test_reports = [r for r in reports if r.get("type") == "test"]
        coverage_reports = [r for r in reports if r.get("type") == "coverage"]
        refactoring_reports = [r for r in reports if r.get("type") == "refactoring"]
        
        # テストレポートの統合
        if test_reports:
            integrated["report_details"]["test"] = self._integrate_test_reports(test_reports)
            integrated["all_tests_pass"] = all(r.get("all_tests_pass", False) for r in test_reports)
        
        # カバレッジレポートの統合
        if coverage_reports:
            integrated["report_details"]["coverage"] = self._integrate_coverage_reports(coverage_reports)
            integrated["test_coverage"] = max(r.get("line_coverage", 0) for r in coverage_reports)
        
        # リファクタリングレポートの統合
        if refactoring_reports:
            integrated["report_details"]["refactoring"] = self._integrate_refactoring_reports(refactoring_reports)
            integrated["overall_score"] = max(r.get("quality_metrics", {}).get("overall_score", 0) for r in refactoring_reports)
            integrated["quality_issues"] = sum(len(r.get("code_smells", [])) for r in refactoring_reports)
        
        # 推奨アクションの生成
        integrated["recommended_actions"] = self._generate_recommendations(integrated)
        
        return integrated
    
    def _integrate_test_reports(self, test_reports: List[Dict[str, Any]]) -> Dict[str, Any]:
        """テストレポートを統合"""
        total_tests = sum(r.get("total_tests", 0) for r in test_reports)
        passed_tests = sum(r.get("passed_tests", 0) for r in test_reports)
        
        return {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": total_tests - passed_tests,
            "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0
        }
    
    def _integrate_coverage_reports(self, coverage_reports: List[Dict[str, Any]]) -> Dict[str, Any]:
        """カバレッジレポートを統合"""
        return {
            "line_coverage": max(r.get("line_coverage", 0) for r in coverage_reports),
            "branch_coverage": max(r.get("branch_coverage", 0) for r in coverage_reports),
            "method_coverage": max(r.get("method_coverage", 0) for r in coverage_reports)
        }
    
    def _integrate_refactoring_reports(self, refactoring_reports: List[Dict[str, Any]]) -> Dict[str, Any]:
        """リファクタリングレポートを統合"""
        all_smells = []
        for report in refactoring_reports:
            all_smells.extend(report.get("code_smells", []))
        
        high_priority = len([s for s in all_smells if s.get("severity") == "high"])
        medium_priority = len([s for s in all_smells if s.get("severity") == "medium"])
        low_priority = len([s for s in all_smells if s.get("severity") == "low"])
        
        return {
            "total_smells": len(all_smells),
            "high_priority_smells": high_priority,
            "medium_priority_smells": medium_priority,
            "low_priority_smells": low_priority,
            "overall_score": max(r.get("quality_metrics", {}).get("overall_score", 0) for r in refactoring_reports)
        }
    
    def _generate_recommendations(self, integrated_report: Dict[str, Any]) -> List[str]:
        """推奨アクションを生成"""
        recommendations = []
        
        # テストカバレッジの推奨
        coverage = integrated_report.get("test_coverage", 0)
        if coverage < 80:
            recommendations.append(f"テストカバレッジを{coverage:.1f}%から80%以上に向上させてください")
        
        # 品質スコアの推奨
        quality_score = integrated_report.get("overall_score", 0)
        if quality_score < 7.0:
            recommendations.append(f"品質スコアを{quality_score:.1f}から7.0以上に向上させてください")
        
        # コードスメルの推奨
        quality_issues = integrated_report.get("quality_issues", 0)
        if quality_issues > 0:
            recommendations.append(f"{quality_issues}個の品質問題を修正してください")
        
        # テスト失敗の推奨
        if not integrated_report.get("all_tests_pass", True):
            recommendations.append("失敗したテストを修正してください")
        
        if not recommendations:
            recommendations.append("品質基準を満たしています。現在の品質を維持してください")
        
        return recommendations
