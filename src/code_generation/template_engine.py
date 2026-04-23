# -*- coding: utf-8 -*-
import json
import os
from typing import Dict, Any


class TemplateEngine:
    def __init__(self, base_dir: str) -> None:
        self._base_dir = base_dir
        self._cache: Dict[str, str] = {}

    def _path(self, name: str) -> str:
        return os.path.join(self._base_dir, name)

    def load(self, name: str) -> str:
        if name in self._cache:
            return self._cache[name]
        path = self._path(name)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self._cache[name] = content
        return content

    def render(self, name: str, values: Dict[str, Any]) -> str:
        template = self.load(name)
        return template.format_map(values)

    def load_json(self, name: str) -> Dict[str, Any]:
        path = self._path(name)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
