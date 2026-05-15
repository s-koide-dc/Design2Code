# Case 36: Calculate Default Target Retention

## Source Scenario

- Scenario: `CALCULATE` 自体は explicit intent で成立しているが、target metadata が無い最小ケース
- Benchmark role: `calculate_target_resolution=default_target` を独立観測するための weak-retention case

## Target Meaning Elements

- `CALCULATE` 昇格と target/property supply の分離
- target metadata が無い場合に property-aware concretization を発明しないこと
- `default_target` と `default_scope_var` が同居する最小ケース

## Expected Structure Summary

- 値を計算する

## Expected IR

```json
{
  "case_id": "case_36_calculate_default_target_retention",
  "status": "draft",
  "module_name": "CalculateDefaultTargetRetention",
  "logic_tree": [
    {
      "id": "step_1",
      "type": "ACTION",
      "intent": "CALC",
      "role": "ACTION",
      "target_entity": "Item",
      "cardinality": "SINGLE",
      "output_type": "decimal",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": null,
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "target_entity": "Item",
          "calculate_target_resolution": "default_target",
          "calculate_source_resolution": "default_scope_var"
        },
        "spec_role": "CALCULATE"
      },
      "children": [],
      "else_children": []
    }
  ]
}
```

## Expected Node Notes

- `CALCULATE` role 自体は explicit intent から成立してよい
- ただし `target_hint` / `property` が無いので target-side provenance は `default_target` に留まる
- source 側も upstream node が無いため `default_scope_var` に留まる
- downstream では property-aware assignment や schema-backed numeric property fallback を発明してはならない

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_36_calculate_default_target_retention.observed.json`
```

## Diff Notes

- 計算ノードは `intent=CALC`, `spec_role=CALCULATE` として保持された
- `semantic_roles.target_entity=Item` のまま target/property metadata は追加されなかった
- `calculate_target_resolution=default_target` と `calculate_source_resolution=default_scope_var` が同時に付き、target と source の両方が weak retention であることを IR 上で読める
- このケースは `explicit_target` と違い、target metadata 自体が存在しない境界を表している

## Failure Mapping

- Primary: `None`
- Secondary: `None`
