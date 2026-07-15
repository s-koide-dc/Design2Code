# -*- coding: utf-8 -*-
import os
import json
from pathlib import Path
from typing import Dict, Any, List


class ConfigLoadError(RuntimeError):
    """Raised when strict configuration loading detects invalid files."""

class ConfigManager:
    """
    Centralized configuration management for the AI pipeline.
    Handles loading of all JSON configs and providing path resolution.
    """
    def __init__(self, workspace_root=None, strict: bool = False):
        self.workspace_root = Path(workspace_root or os.getcwd()).resolve()
        self.load_errors: List[Dict[str, str]] = []
        self.missing_config_files: List[str] = []

        # Load core configurations (Moved from resources to config/)
        self.config_data = self._load_json(self.workspace_root / "config" / "config.json")
        self.safety_policy = self._load_json(self.workspace_root / "config" / "safety_policy.json")
        self.retry_rules = self._load_json(self.workspace_root / "config" / "retry_rules.json")
        self.project_rules = self._load_json(self.workspace_root / "config" / "project_rules.json")
        self.scoring_rules = self._load_json(self.workspace_root / "config" / "scoring_rules.json")
        self.user_preferences = self._load_json(self.workspace_root / "config" / "user_preferences.json")
        self.response_rewriter_config = self._load_json(self.workspace_root / "config" / "response_rewriter_config.json")
        if strict and self.load_errors:
            invalid_files = ", ".join(error["path"] for error in self.load_errors)
            raise ConfigLoadError(f"Invalid configuration file(s): {invalid_files}")

        # Paths for Config files
        self.error_patterns_path = str(self.workspace_root / "config" / "error_patterns.json")
        self.cicd_config_path = str(self.workspace_root / "config" / "cicd_config.json")
        self.coverage_config_path = str(self.workspace_root / "config" / "coverage_config.json")
        self.refactoring_config_path = str(self.workspace_root / "config" / "refactoring_config.json")
        self.response_rewriter_config_path = str(self.workspace_root / "config" / "response_rewriter_config.json")
        self.method_store_path = str(self.workspace_root / "resources" / "method_store.json")
        self.storage_dir = str(self.workspace_root / "resources" / "vectors" / "vector_db")

        # Paths for Data Assets (Stay in resources/)
        self.intent_corpus_path = str(self.workspace_root / "resources" / "intent_corpus.json")
        self.vector_model_path = str(self.workspace_root / "resources" / "vectors" / "chive-1.3-mc90.txt")
        self.knowledge_base_path = str(self.workspace_root / "resources" / "custom_knowledge.json")
        self.custom_knowledge_path = self.knowledge_base_path
        self.dictionary_db_path = str(self.workspace_root / "resources" / "dictionary.db")
        self.dependency_map_path = str(self.workspace_root / "resources" / "dependency_map.json")
        self.task_definitions_path = str(self.workspace_root / "resources" / "task_definitions.json")
        self.domain_dictionary_path = str(self.workspace_root / "resources" / "domain_dictionary.json")
        self.repair_knowledge_path = str(self.workspace_root / "resources" / "repair_knowledge.json")

    def _load_json(self, path):
        config_path = Path(path)
        if not config_path.exists():
            self.missing_config_files.append(str(config_path))
            return {}
        try:
            with config_path.open('r', encoding='utf-8') as f:
                loaded = json.load(f)
        except json.JSONDecodeError:
            self.load_errors.append({
                "path": str(config_path),
                "error_type": "JSONDecodeError",
            })
            return {}
        except OSError as exc:
            self.load_errors.append({
                "path": str(config_path),
                "error_type": type(exc).__name__,
            })
            return {}
        if not isinstance(loaded, dict):
            self.load_errors.append({
                "path": str(config_path),
                "error_type": "InvalidTopLevelType",
            })
            return {}
        return loaded

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from config.json data."""
        return self.config_data.get(key, default)

    def get_section(self, section_name: str) -> Dict[str, Any]:
        """Get a full section (e.g., 'clarification') from config.json."""
        return self.config_data.get(section_name, {})

    def get_safety_policy(self) -> Dict[str, Any]:
        return self.safety_policy

    def get_safety_policy_model(self):
        from src.safety.policy import SafetyPolicy
        return SafetyPolicy.from_mapping(self.safety_policy)

    def get_retry_rules(self) -> list:
        return self.retry_rules.get("retry_rules", [])

    def get_project_rules(self) -> Dict[str, Any]:
        return self.project_rules

    def get_scoring_rules(self) -> Dict[str, Any]:
        return self.scoring_rules

    def get_task_manager_config(self) -> Dict[str, Any]:
        return self.get_section("task_manager")
