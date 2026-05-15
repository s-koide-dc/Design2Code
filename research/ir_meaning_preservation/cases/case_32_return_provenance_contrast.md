# Case 32: Return Provenance Contrast

## Source Scenario

- Scenario: `RETURN` が literal return なのか、upstream value return なのかを同一ケース内で区別したい
- Benchmark role: `RETURN` に対する `return_value_resolution` と `return_source_node_id` の観測

## Target Meaning Elements

- `spec_role=RETURN`
- `return_value`
- `return_value_resolution`
- `return_source_node_id`

## Expected Structure Summary

- ユーザーを取得する
- ユーザーが null なら `null` を返す
- そうでなければ、取得したユーザーを返す

## Expected IR

```json
{
  "case_id": "case_32_return_provenance_contrast",
  "status": "draft",
  "module_name": "ReturnProvenanceContrast",
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
      "type": "CONDITION",
      "intent": "EXISTS",
      "role": "CHECK",
      "target_entity": "User",
      "cardinality": "SINGLE",
      "output_type": "bool",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": "step_1",
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "target_entity": "User",
          "structure_kind": "condition"
        },
        "spec_role": "CHECK",
        "check_kind": "null_check",
        "check_subject": "user",
        "expected_truth": false,
        "subject_resolution": "explicit_subject"
      },
      "children": [
        {
          "id": "step_3",
          "type": "ACTION",
          "intent": "RETURN",
          "role": "RETURN",
          "target_entity": "User",
          "cardinality": "SINGLE",
          "output_type": "User",
          "source_kind": "memory",
          "source_ref": null,
          "input_link": null,
          "semantic_map": {
            "logic": [],
            "semantic_roles": {
              "target_entity": "User",
              "return_value": "null",
              "return_value_resolution": "literal_null"
            },
            "spec_role": "RETURN"
          },
          "children": [],
          "else_children": []
        }
      ],
      "else_children": [
        {
          "id": "step_5",
          "type": "ACTION",
          "intent": "RETURN",
          "role": "RETURN",
          "target_entity": "User",
          "cardinality": "SINGLE",
          "output_type": "User",
          "source_kind": "memory",
          "source_ref": null,
          "input_link": "step_2",
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
  ]
}
```

## Expected Node Notes

- `step_3` は literal early return であり、`return_value=null`, `return_value_resolution=literal_null` を持つ
- `step_5` は value return であり、返却対象は branch base の `CONDITION` ではなく、その upstream data source `step_1` を `return_source_node_id` として保持する
- `RETURN` の source provenance は `input_link` と同一ではなく、semantic return source を別 field で持つことが重要

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_32_return_provenance_contrast.observed.json`
```

## Diff Notes

- `step_3` は `return_value=null`, `return_value_resolution=literal_null` を保持した
- `step_5` は `input_link=step_2` を保ちながら、semantic source として `return_source_node_id=step_1` を保持した
- これにより、構造依存と return-source provenance を IR 上で分離できる

## Failure Mapping

- Primary: none
- Secondary: none
