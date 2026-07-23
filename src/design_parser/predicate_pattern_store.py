# -*- coding: utf-8 -*-
"""Verified predicate patterns used only to expand local semantic candidates."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


class PredicatePatternStore:
    """Loads traceable predicate examples; it never decides a generated predicate."""

    def __init__(self, config_manager, vector_engine=None, morph_analyzer=None) -> None:
        self.config_manager = config_manager
        self.vector_engine = vector_engine
        self.morph_analyzer = morph_analyzer
        self.patterns = self._load_patterns()
        self._vectors = self._vectorize_patterns()

    def _load_patterns(self) -> List[Dict[str, Any]]:
        root = Path(getattr(self.config_manager, "workspace_root", "."))
        path = root / "resources" / "predicate_patterns.json"
        if not path.is_file():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        patterns = data.get("patterns", []) if isinstance(data, dict) else []
        return [pattern for pattern in patterns if self._is_valid_pattern(pattern)]

    @staticmethod
    def _is_valid_pattern(pattern: Any) -> bool:
        if not isinstance(pattern, dict) or not isinstance(pattern.get("goal"), dict):
            return False
        return bool(pattern.get("id")) and isinstance(pattern.get("utterances"), list)

    def _tokens(self, text: str) -> List[str]:
        if self.morph_analyzer:
            tokens = self.morph_analyzer.tokenize(text)
            return [str(token.get("surface")) for token in tokens if isinstance(token, dict) and token.get("surface")]
        return list(text)

    def _vectorize_patterns(self) -> Dict[str, Any]:
        if not self.vector_engine or getattr(self.vector_engine, "store", None) is None:
            return {}
        vectors: Dict[str, Any] = {}
        for pattern in self.patterns:
            text = " ".join(str(value) for value in pattern.get("utterances", []) if value)
            vector = self.vector_engine.get_sentence_vector(self._tokens(text))
            if vector is not None:
                vectors[str(pattern["id"])] = vector
        return vectors

    def retrieve(self, text: str) -> List[Dict[str, Any]]:
        """Return semantic candidates with provenance; callers must validate structure."""
        if not self._vectors:
            return []
        query = self.vector_engine.get_sentence_vector(self._tokens(text))
        if query is None:
            return []
        candidates = []
        for pattern in self.patterns:
            vector = self._vectors.get(str(pattern["id"]))
            if vector is None:
                continue
            candidates.append({
                "id": pattern["id"],
                "goal": dict(pattern["goal"]),
                "value_kind": pattern.get("value_kind"),
                "property_type": pattern.get("property_type"),
                "polarity": pattern.get("polarity"),
                "provenance": list(pattern.get("provenance", [])),
                "similarity": float(self.vector_engine.vector_similarity(query, vector)),
            })
        return sorted(candidates, key=lambda candidate: (-candidate["similarity"], candidate["id"]))

    def resolve_unique(self, text: str, *, property_type: str, value_kind: str, polarity: str | None = None, operator: str | None = None) -> Dict[str, Any] | None:
        candidates = [
            candidate for candidate in self.retrieve(text)
            if candidate.get("property_type") == property_type and candidate.get("value_kind") == value_kind
            and (polarity is None or candidate.get("polarity") == polarity)
            and (operator is None or (candidate.get("goal") or {}).get("operator") == operator)
        ]
        return candidates[0] if len(candidates) == 1 else None


class PropertySemanticStore:
    """Resolves schema properties from their authored semantic descriptions."""

    def __init__(self, entity_schema: Dict[str, Any], vector_engine=None, morph_analyzer=None) -> None:
        self.entity_schema = entity_schema if isinstance(entity_schema, dict) else {}
        self.vector_engine = vector_engine
        self.morph_analyzer = morph_analyzer

    def _tokens(self, text: str) -> List[str]:
        if self.morph_analyzer and hasattr(self.morph_analyzer, "tokenize"):
            return [str(token.get("surface")) for token in self.morph_analyzer.tokenize(text) if isinstance(token, dict) and token.get("surface")]
        return list(text)

    def resolve(self, entity_name: str, text: str, *, numeric_only: bool = False, required_operator: str | None = None) -> str | None:
        if not self.vector_engine or getattr(self.vector_engine, "store", None) is None:
            return None
        entity = next((item for item in self.entity_schema.get("entities", []) if item.get("name") == entity_name), None)
        if not isinstance(entity, dict):
            return None
        query = self.vector_engine.get_sentence_vector(self._tokens(text))
        if query is None:
            return None
        candidates = []
        for name, semantics in (entity.get("property_semantics") or {}).items():
            if required_operator and required_operator not in (entity.get("predicate_capabilities") or {}).get(name, []):
                continue
            if required_operator and required_operator not in (semantics.get("predicate_forms") or {}):
                continue
            prop_type = str((entity.get("properties") or {}).get(name) or "").lower()
            if numeric_only and not any(marker in prop_type for marker in ("int", "decimal", "double", "float", "long")):
                continue
            if not isinstance(semantics, dict):
                continue
            forms = []
            if required_operator:
                forms = (semantics.get("predicate_forms") or {}).get(required_operator, [])
            description = " ".join([str(semantics.get("description") or ""), *[str(item) for item in semantics.get("examples", [])], *[str(item) for item in forms]])
            vector = self.vector_engine.get_sentence_vector(self._tokens(description))
            if vector is not None:
                candidates.append((float(self.vector_engine.vector_similarity(query, vector)), str(name)))
        if not candidates:
            return None
        # Embedding proximity is retrieval evidence only.  Multiple schema
        # properties of the required type are structurally ambiguous, even if
        # one happens to rank first, so fail closed instead of guessing.
        if len(candidates) != 1:
            return None
        return candidates[0][1]
