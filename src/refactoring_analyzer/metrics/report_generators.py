# -*- coding: utf-8 -*-
# src/refactoring_analyzer/report_generators.py

import json
from datetime import datetime
from typing import Dict, List, Any

class RefactoringJSONReporter:
    """JSON形式リファクタリングレポート生成器"""
    
    def generate(self, output_path: str, smell_result: Dict[str, Any], suggestions: List[Dict[str, Any]], 
                quality_metrics: Dict[str, Any], recommendations: List[Dict[str, Any]]) -> None:
        """JSONレポートを生成"""
        report_data = {
            "smell_result": smell_result,
            "suggestions": suggestions,
            "quality_metrics": quality_metrics,
            "recommendations": recommendations,
            "generated_at": datetime.now().isoformat()
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)


class RefactoringHTMLReporter:
    """HTML形式リファクタリングレポート生成器"""
    
    def generate(self, output_path: str, smell_result: Dict[str, Any], suggestions: List[Dict[str, Any]], 
                quality_metrics: Dict[str, Any], recommendations: List[Dict[str, Any]]) -> None:
        """HTMLレポートを生成"""
        html_content = self._generate_html_template(smell_result, suggestions, quality_metrics, recommendations)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
    
    def _generate_html_template(self, smell_result: Dict[str, Any], suggestions: List[Dict[str, Any]], 
                               quality_metrics: Dict[str, Any], recommendations: List[Dict[str, Any]]) -> str:
        """HTMLテンプレートを生成"""
        code_smells = smell_result.get("code_smells", [])
        
        # Helper to format code smells
        smells_html = ""
        for smell in code_smells:
            severity = smell.get("severity", "medium")
            smells_html += f"""
            <div class="card smell-card border-{severity}">
                <div class="card-header bg-{severity} text-white">
                    <strong>{smell.get('type', 'unknown').upper()}</strong> 
                    <span class="badge badge-light float-right">{severity}</span>
                </div>
                <div class="card-body">
                    <h6 class="card-subtitle mb-2 text-muted">{smell.get('file', '')} (Lines: {smell.get('line_start', '?')}-{smell.get('line_end', '?')})</h6>
                    <p class="card-text">{smell.get('description', '')}</p>
                    {f'<div class="alert alert-secondary"><strong>Method:</strong> {smell.get("method")}</div>' if smell.get("method") else ""}
                </div>
            </div>"""

        # Helper to format suggestions
        suggestions_html = ""
        for sug in suggestions:
            priority = sug.get("priority", "medium")
            sug_info = sug.get("suggestion", {})
            suggestions_html += f"""
            <div class="card suggestion-card">
                <div class="card-body">
                    <h5 class="card-title text-primary">{sug.get('type', 'unknown').replace('_', ' ').title()}</h5>
                    <p><strong>Target:</strong> {sug.get('target', {}).get('file')} ({sug.get('target', {}).get('method', 'Class-level')})</p>
                    <p><strong>Action:</strong> {sug_info.get('description', '')}</p>
                    <div class="row">
                        <div class="col"><strong>Effort:</strong> {sug_info.get('estimated_effort', '?')}</div>
                        <div class="col"><strong>Safety:</strong> {sug_info.get('safety_level', '?')}</div>
                    </div>
                </div>
            </div>"""

        return f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>リファクタリング分析レポート</title>
    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
    <style>
        body {{ background-color: #f8f9fa; padding-top: 30px; }}
        .container {{ max-width: 1000px; }}
        .metric-value {{ font-size: 2rem; font-weight: bold; color: #007bff; }}
        .smell-card {{ margin-bottom: 15px; border-left: 5px solid; }}
        .border-high {{ border-left-color: #dc3545 !important; }}
        .border-medium {{ border-left-color: #ffc107 !important; }}
        .border-low {{ border-left-color: #28a745 !important; }}
        .bg-high {{ background-color: #dc3545; }}
        .bg-medium {{ background-color: #ffc107; }}
        .bg-low {{ background-color: #28a745; }}
        .suggestion-card {{ margin-bottom: 15px; border-left: 5px solid #007bff; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="jumbotron">
            <h1 class="display-4">リファクタリング分析レポート</h1>
            <p class="lead">AIによるコード品質分析結果</p>
            <hr class="my-4">
            <div class="row text-center">
                <div class="col">
                    <div class="text-muted">品質スコア</div>
                    <div class="metric-value">{quality_metrics.get('overall_score', 0):.1f}/10</div>
                </div>
                <div class="col">
                    <div class="text-muted">保守性指数</div>
                    <div class="metric-value">{quality_metrics.get('maintainability_index', 0)}</div>
                </div>
                <div class="col">
                    <div class="text-muted">技術的負債</div>
                    <div class="metric-value">{quality_metrics.get('technical_debt_hours', 0):.1f}h</div>
                </div>
            </div>
        </div>

        <div class="row">
            <div class="col-md-6">
                <h3 class="mb-3">コードスメル ({len(code_smells)})</h3>
                {smells_html if smells_html else "<p>検出されたコードスメルはありません。</p>"}
            </div>
            <div class="col-md-6">
                <h3 class="mb-3">改善提案 ({len(suggestions)})</h3>
                {suggestions_html if suggestions_html else "<p>提案された改善案はありません。</p>"}
            </div>
        </div>

        <div class="mt-5 mb-5 p-4 bg-white shadow-sm rounded">
            <h3>推奨アクション</h3>
            <ul class="list-group list-group-flush">
                {''.join([f'<li class="list-group-item"><strong>{rec.get("category", "").upper()}:</strong> {rec.get("description", "")}</li>' for rec in recommendations])}
            </ul>
        </div>

                <footer class="text-center text-muted mt-5 pb-5">

                    <p>生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

                </footer>

            </div>

        </body>

        </html>"""

        