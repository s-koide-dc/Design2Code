# Case 17: Check Subject Provenance

## Source Scenario

- Scenario: `CHECK` の subject が quoted literal から取れる場合と、history から補われる場合を区別したいケース
- Benchmark role: `CHECK` に対する `subject_resolution` の観測

## Target Meaning Elements

- `spec_role=CHECK`
- `check_kind`
- `check_subject`
- `subject_resolution`

## Expected Structure Summary

- `config.json` が存在するか確認する
- 設定を読み込む
- `config` が null か確認する

## Expected IR

```json
{
  "case_id": "case_17_check_subject_provenance",
  "status": "draft",
  "module_name": "CheckSubjectProvenance",
  "logic_tree": [
    {
      "id": "step_1",
      "type": "CONDITION",
      "intent": "EXISTS",
      "role": "CHECK",
      "target_entity": "Item",
      "cardinality": "SINGLE",
      "output_type": "bool",
      "source_kind": "file",
      "source_ref": "config.json",
      "input_link": null,
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "target_entity": "Item"
        },
        "spec_role": "CHECK",
        "check_kind": "exists_check",
        "check_subject": "config.json",
        "expected_truth": true,
        "source_ref": "config.json",
        "source_kind": "file",
        "subject_resolution": "quoted_literal"
      },
      "children": [
        {
          "id": "step_2",
          "type": "ACTION",
          "intent": "FETCH",
          "role": "FETCH",
          "target_entity": "Config",
          "cardinality": "SINGLE",
          "output_type": "string",
          "source_kind": "file",
          "source_ref": "config.json",
          "input_link": "step_1",
          "semantic_map": {
            "logic": [],
            "semantic_roles": {
              "target_entity": "Config",
              "path": "config.json"
            },
            "spec_role": "FETCH"
          },
          "children": [],
          "else_children": []
        }
      ],
      "else_children": []
    },
    {
      "id": "step_3",
      "type": "CONDITION",
      "intent": "EXISTS",
      "role": "CHECK",
      "target_entity": "Config",
      "cardinality": "SINGLE",
      "output_type": "bool",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": "step_2",
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "target_entity": "Config"
        },
        "spec_role": "CHECK",
        "check_kind": "null_check",
        "check_subject": "config",
        "expected_truth": false,
        "subject_resolution": "explicit_subject"
      },
      "children": [
        {
          "id": "step_4",
          "type": "ACTION",
          "intent": "DISPLAY",
          "role": "DISPLAY",
          "target_entity": "Config",
          "cardinality": "SINGLE",
          "output_type": "string",
          "source_kind": "memory",
          "source_ref": null,
          "input_link": "step_3",
          "semantic_map": {
            "logic": [],
            "semantic_roles": {
              "target_entity": "Config",
              "message": "設定を読み込めません"
            },
            "spec_role": "DISPLAY"
          },
          "children": [],
          "else_children": []
        }
      ],
      "else_children": []
    }
  ]
}
```

## Expected Node Notes

- quoted path を直接持つ場合は `subject_resolution=quoted_literal`
- 文面に subject が明示されている場合は `subject_resolution=explicit_subject`
- 十分な根拠がない場合は `subject_resolution=default_subject`
- `step_1` と `step_3` はどちらも `CHECK` だが、subject の由来が異なることが重要
- `step_3` は entity continuity を保ちながら、subject 自体は文面から直接解決される

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_17_check_subject_provenance.observed.json`
```

## Diff Notes

- `step_1` は `check_kind=exists_check`, `check_subject=config.json`, `source_ref/source_kind` まで保持された
- `step_3` も `check_kind=null_check`, `check_subject=config` を保持した
- `step_1.subject_resolution=quoted_literal`, `step_3.subject_resolution=explicit_subject` まで保持された
- これにより、quoted literal 由来と explicit subject 由来は IR field 上で分離できる
- `target_entity=Config` は両方で保持されているため、subject provenance より entity continuity の方は既に安定している

## Failure Mapping

- Primary: none
- Secondary: none
