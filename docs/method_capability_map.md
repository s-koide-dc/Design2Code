# Method Capability Map

## Purpose
Provide an explicit, deterministic mapping for `intent`, `capabilities`, and parameter roles for methods harvested from libraries that do **not** include custom attributes.

This map is a required workaround for third-party or standard libraries where attributes cannot be added. It avoids keyword/heuristic inference and keeps behavior compliant with project constraints.

## File Location
`C:\workspace\NLP\resources\method_capability_map.json`

## Format
```json
{
  "version": 1,
  "methods": {
    "Namespace.Type.Method": {
      "intent": "FETCH",
      "capabilities": ["FILE_IO", "READ"],
      "param_roles": { "path": "path", "content": "content" }
    }
  }
}
```

## Rules
1. **Exact match only**: Keys must be fully qualified method names.
2. **No inference**: If a method is not in the map and has no attributes, `intent`/`capabilities` remain empty.
3. **Param roles are optional**: Use when binding requires explicit roles (e.g., `path`, `url`, `sql`).
4. **Keep minimal**: Add only the methods you actually need in generation paths.

## Usage
- `MethodHarvesterCLI` reads the map when:
  - `--map <path>` is provided, or
  - `METHOD_CAPABILITY_MAP` environment variable is set, or
  - a file named `method_capability_map.json` exists next to the executable.
- Python harvesters (`method_harvester.py`, `dynamic_harvester.py`) also read the same map from `resources/`.

## Runtime Scope
- このマップは **ハーベスト時のみ** に参照されます。  
  生成・合成のランタイムでは **直接参照されません**。

## Suggestion Tool (Assist Only)
`scripts/tools/suggest_method_capabilities.py` generates **suggestions** for entries missing in the map.
- Uses **exact-match rules only** (no regex/keyword heuristics).
- Output is written to `cache/` as JSON and Markdown.
- Human review is required before copying into `method_capability_map.json`.

## Notes
This map is **not** a fallback for missing spec metadata. It is only for libraries that cannot be annotated.
