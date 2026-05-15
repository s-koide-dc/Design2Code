# Case 34: Return Weak Retention

## Source Scenario

- Scenario: `RETURN` intent 自体は分かるが、literal も upstream source も供給されず weak retention に留まるべきケース
- Benchmark role: `RETURN` provenance supply の failure 側

## Target Meaning Elements

- `spec_role=RETURN`
- `return_value_resolution` が付かないこと
- `return_source_node_id` が付かないこと

## Expected Structure Summary

- `結果を返す`

## Expected IR

```json
{
  "case_id": "case_34_return_weak_retention",
  "status": "draft",
  "module_name": "ReturnWeakRetention",
  "logic_tree": [
    {
      "id": "step_1",
      "type": "ACTION",
      "intent": "RETURN",
      "role": "RETURN",
      "target_entity": "Item",
      "cardinality": "SINGLE",
      "output_type": null,
      "source_kind": "memory",
      "source_ref": null,
      "input_link": null,
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "target_entity": "Item"
        },
        "spec_role": "RETURN"
      },
      "children": [],
      "else_children": []
    }
  ]
}
```

## Expected Node Notes

- `RETURN` intent は保持される
- しかし source provenance は deterministic に supply されないため、`return_value_resolution` は付かない
- これは failure ではなく weak retention の expected behavior として扱う

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_34_return_weak_retention.observed.json`
```

## Diff Notes

- `spec_role=RETURN` は保持された
- `return_value_resolution` は付かなかった
- `return_source_node_id` も付かなかった
- したがって lexical surface だけでは provenance supply せず、weak retention に留める境界が守られている

## Failure Mapping

- Primary: none
- Secondary: none
