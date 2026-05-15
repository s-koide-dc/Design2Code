# Case 33: Return Input-Link Supply

## Source Scenario

- Scenario: non-literal `RETURN` だが upstream dependency が明示されており、`input_link_var` まで上がるべきケース
- Benchmark role: `RETURN` provenance supply の success 側

## Target Meaning Elements

- `spec_role=RETURN`
- `return_source_node_id`
- `return_value_resolution=input_link_var`

## Expected Structure Summary

- ユーザーを取得する
- 取得したユーザーを返す

## Expected IR

```json
{
  "case_id": "case_33_return_input_link_supply",
  "status": "draft",
  "module_name": "ReturnInputLinkSupply",
  "logic_tree": [
    {
      "id": "step_1",
      "type": "ACTION",
      "intent": "FETCH",
      "role": "FETCH",
      "target_entity": "User",
      "cardinality": "SINGLE",
      "output_type": "User",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": null,
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "target_entity": "User"
        },
        "spec_role": "FETCH"
      },
      "children": [],
      "else_children": []
    },
    {
      "id": "step_2",
      "type": "ACTION",
      "intent": "RETURN",
      "role": "RETURN",
      "target_entity": "User",
      "cardinality": "SINGLE",
      "output_type": "User",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": "step_1",
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "target_entity": "User",
          "return_source_node_id": "step_1",
          "return_value_resolution": "input_link_var"
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

- non-literal `RETURN` でも `input_link` があるので supply success とみなす
- latest var fallback ではなく、semantic source として `return_source_node_id=step_1` を持つことが重要

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_33_return_input_link_supply.observed.json`
```

## Diff Notes

- `step_2` は `return_source_node_id=step_1`, `return_value_resolution=input_link_var` を保持した
- したがって non-literal `RETURN` でも upstream dependency が明示されていれば deterministic supply が成立する

## Failure Mapping

- Primary: none
- Secondary: none
