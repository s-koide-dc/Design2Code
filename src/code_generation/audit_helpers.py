# -*- coding: utf-8 -*-
"""Audit helpers for design and logic."""
from __future__ import annotations


class AuditHelpers:
    def __init__(self, owner) -> None:
        self.owner = owner

    def get_logic_auditor(self):
        if self.owner._logic_auditor is None:
            resolver = self.owner._get_ops_resolver()
            self.owner._logic_auditor = self.owner._logic_auditor or self.owner._get_logic_auditor_factory(resolver)
        return self.owner._logic_auditor

    def get_doc_refiner(self):
        if self.owner._doc_refiner is None:
            resolver = self.owner._get_ops_resolver()
            self.owner._doc_refiner = self.owner._doc_refiner or self.owner._get_doc_refiner_factory(resolver)
        return self.owner._doc_refiner

    def audit_logic(self, core_logic: list, body_lines: list, label: str) -> list:
        if not core_logic or not body_lines:
            return []
        auditor = self.get_logic_auditor()
        normalized = self.owner._normalize_core_logic(core_logic)
        goals = auditor.extract_assertion_goals(normalized)
        findings = auditor.verify_logic_goals(goals, "\n".join(body_lines))
        for f in findings:
            f["method"] = label
        return findings

    def audit_design_doc(self, design_doc: str, source_path: str, label: str, source_code: str | None = None) -> list:
        if not design_doc:
            return []
        refiner = self.get_doc_refiner()
        result = refiner.audit_only(design_doc, source_path, source_code=source_code)
        findings = []
        if isinstance(result, dict):
            for item in result.get("findings", []) or []:
                findings.append({
                    "method": label,
                    "reason": item.get("type", "logic_gap"),
                    "detail": item.get("detail", ""),
                })
        return findings
