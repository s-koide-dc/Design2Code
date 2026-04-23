# Development Conventions

This document outlines the rules and conventions that must be followed by any agent (AI or human) contributing to this project.

## 1. General Workflow

This project operates on a Specification-Driven and AI-First development model. The `.design.md` file for each module is the central specification and drives implementation and testing.

1. Goal Definition (Human): Define a high-level goal for a new module.
2. Initial Scaffolding (Human): Run `create_module` to generate the basic file structure.
3. Specification Generation (AI & Human): The AI drafts the `.design.md` according to Section 9, and the human reviews and approves it.
4. Implementation & Testing (AI): Implement logic and tests strictly from the `.design.md`.
5. Review & Verification (Human): Review code and test results for alignment and quality.

## 2. AI_CHANGELOG.md

1. Order: New entries must be added at the top.
2. Format: `- **YYYY-MM-DD**: description`.
3. Example: `- **2025-12-20**: Refactored module_a to improve performance.`

## 3. Naming Conventions

1. Modules: Use `snake_case`.
2. Design documents: `[module_name].design.md`.
3. Python tests: `tests/test_[module_name].py` or `tests/unit/test_[module_name].py`.
4. Generated C# project tests: `Tests/{ServiceName}Tests.cs`.

## 4. Coding Style

1. JavaScript: ESLint with a common configuration (e.g., Airbnb, Standard).
2. Python: PEP 8.
3. C#: Microsoft C# Coding Conventions (PascalCase for public types/members, camelCase for locals/args).
4. Commenting: Add comments only where logic is complex or non-obvious; primary documentation lives in `.design.md`.

## 5. Entity Naming Conventions

Use these keys consistently between modules.

1. Filenames: `filename` for primary file operations.
2. Filenames: `source_filename` for copy/move/backup source.
3. Filenames: `destination_filename` for copy/move/backup target.
4. Content: `content` for file body data or appended text.
5. Commands: `command` for raw shell/CLI commands.
6. Paths: `project_path` for directory or project-level locations.

## 6. Commits

1. Use Conventional Commits.
2. Example: `feat(module_a): add new endpoint for user profiles`.

## 7. Script Usage and Operational Guidelines

General principles.

1. Automation first: Prefer scripts for routine tasks.
2. Validation: After significant change, run `sync_project_map.py` and project validation scripts.

Specific scripts.

1. `validate_project_consistency.py`
Purpose: Validate module presence, freshness, and dependency registration.
Timing: Before commit, in CI, after major changes.
Command: `python scripts/validate_project_consistency.py`.

2. `sync_project_map.py`
Purpose: Sync `ai_project_map.json` with the filesystem.
Timing: After file system changes, before commit, before major tasks.
Command: `python scripts/sync_project_map.py`.
Note: The script auto-discovers new modules and tools with default placeholders. Manually fill accurate summaries and dependencies.

3. `create_module`
Purpose: Scaffold module directory, source, design doc, and test file.
Timing: At the start of new module development.
Command (Unix-like): `./scripts/scaffold/create_module.sh <module_name> <language>`.
Command (Windows PowerShell): `powershell -ExecutionPolicy Bypass -File scripts/scaffold/create_module.ps1 -ModuleName <module_name> -Language <language>`.

## 8. AI Self-Correction Protocol

1. Pre-execution plan: State a step-by-step plan before any code modification, file operation, or complex command.
2. Verification failure analysis: Halt, explain the failure, hypothesize cause, propose a fix plan, and seek confirmation for significant fixes.
3. Task completion checklist.
- Code correctness.
- Documentation sync (.design.md).
- Project map sync (`scripts/sync_project_map.py`).
- Verification passed (tests, linters, builds).
- Changelog updated (`AI_CHANGELOG.md`).
- State updated if a task-tracking file/system exists.

## 9. Design Document Conventions

Use a single shared structure for both method-level and project-level specs. Do not split formats by level.

1. Purpose: High-level responsibility and role.
2. Input: Data received, types, formats, examples.
3. Output: Data returned, types, formats, examples.
4. Core Logic: Step-by-step logic that transforms inputs to outputs.
5. Test Cases: Happy Path and Edge Cases.

Human Spec vs Machine Spec.

1. Human Spec must include Purpose, Input, Output, Core Logic, Test Cases, and CRUD targets (Entities/DTO/Modules).
2. For standard CRUD, Human Spec may omit detailed steps/ops tags, structured test JSON, and repository SQL.
3. Machine Spec may fill standard CRUD steps, repo SQL templates, and default service Happy Path tests.
4. For non-standard CRUD (branching, special validation, custom SQL, unique side effects), Human Spec must be explicit.
5. Non-deterministic guessing (randomness, external-state drift) is prohibited.
   - Deterministic completion based on fixed dictionaries, fixed models, and fixed scoring rules is allowed.
   - The same input text must always yield the same branch/result under identical model/dictionary versions.
6. If completion relies on external assets (dictionary/model), the path/version must be traceable.
7. **Design-Spec Inference Policy (補完→固定化)**:
   - Natural-language specs may be **inferred once** into explicit metadata (ops/semantic_roles/data_source/refs).
   - After inference, the **inferred design document** becomes the single source of truth; generation must use the embedded metadata only.
   - Inference must be **deterministic** under fixed model/dictionary/scoring versions and must record the asset versions used.
   - If inference is used, **persist the inferred metadata into a separate `.inferred.design.md`**; the original `.design.md` must not be modified.

### 9.1 Explicit Ops Metadata

Use explicit ops tags on Core Logic steps for non-trivial transformations or aggregations.

1. Syntax: `[ops:op_a,op_b]`.
2. Placement: After step header or refs tag and before natural language description.
3. Purpose: Declare exact transformation intent deterministically.
4. Prohibition: Do not infer ops via non-deterministic or external-state-driven guessing.

Supported ops.

1. `split_lines`: Split string into non-empty lines.
2. `trim_upper`: Trim and convert to upper-case (invariant).
3. `format_kv`: Build `MODE=..., REGION=...` from two values.
4. `aggregate_by_product`: Aggregate CSV rows into product totals.
5. `csv_serialize`: Serialize totals into CSV lines.
6. `display_names`: Display `Name` properties from a POCO list.
7. `use_api_key_header`: Attach input as `X-API-Key` header for HTTP requests.

Example.

`[ACTION|TRANSFORM|string|List<string>|NONE] [ops:split_lines] CSVを行配列に分割する`

### 9.2 Semantic Roles (必須の明示ルール)

1. DBクエリ（DATABASE_QUERY / PERSIST）: `semantic_roles.sql` を必須にする。
2. HTTPリクエスト（HTTP_REQUEST）: `semantic_roles.url` を必須にする。
3. ファイル入出力（PERSIST + file）: `semantic_roles.path` で保存先パスを明示する。

### 9.3 data_source の命名規約

1. `data_source.id` は英数字と `_` のみ。
2. 実パスや拡張子は `semantic_roles.path` で明示する。

### 9.4 HTTP/DB の明示リンク

1. HTTP/DB が標準 CRUD ではない場合、設計書で必ず明示する。
2. `HTTP_REQUEST` は `data_source`（kind=`http`）に紐づける。
3. `DATABASE_QUERY` / `PERSIST` は `data_source`（kind=`db`）に紐づける。
4. `refs` は data_source 行を除外した後の step_id に合わせて指定する。

### 9.5 ブラケットタグの複数指定

1. 1ステップ内で複数ブラケットタグを使用してよい。
2. `[refs:...]`, `[ops:...]`, `[semantic_roles:{...}]` のいずれかが含まれる場合は必ず保持する。

Example.

`[ACTION|PERSIST|User|void|DB|user_db] [semantic_roles:{"sql":"UPDATE Users SET ..."}] [refs:step_2] ...`

### 9.6 CMD_RUN の指定ルール

1. Core Logic の該当ステップに `semantic_roles.command` を明示する。
2. コマンド先頭トークンは `config/safety_policy.json` の `safe_commands` に含まれている必要がある。
3. 破壊的操作は避け、必要な場合は手順を明示する。

Example.

`[ACTION|CMD_RUN|string|void|NONE] [semantic_roles.command="py -m unittest tests.unit.test_regression_scenarios"] テストを実行する`

### 9.7 ELSE/END の明示ルール

1. `ELSE` / `END` は必ず明示タグで記述する（`[ELSE|GENERAL]`, `[END|GENERAL]`）。
2. 省略や自然文のみの記述は禁止（誤推論防止のため）。

### 9.8 自然文の厳密化ルール（メタ削減方針）

1. 条件分岐は自然文だけでなく、**比較対象・演算子・閾値**を明示する。
2. 係数・割合・固定値は自然文中に**数値を必ず記述**する（例: 15%、0.15）。
3. 対象プロパティ名は**実体のフィールド名**で明示する（例: `Total`, `CustomerType`）。
4. 曖昧表現（「適切に」「必要に応じて」「高い場合」など）は禁止。
5. これらが書かれていない場合は **semantic_roles の明示を必須**とする。

## 10. Tools Directory Conventions

The `tools/` directory holds language-specific helper applications invoked by `action_executor`.

### 10.1 Directory Structure

1. Root: `project_root/tools/`.
2. Subdirectories: One per language/domain (e.g., `tools/csharp/`).
3. Tool project folder: `tools/<language>/<tool_name>/` with source and project files.
4. Tool-specific files: Optional `config.json` and required `.design.md`.

### 10.2 Integration with AI Core

1. Invocation: `action_executor` runs compiled tools with input args.
2. Interface: Use standardized I/O (e.g., JSON via stdin/stdout).

### 10.3 Build Process

1. CI/CD must build all tools (e.g., `dotnet build` for C# tools).
2. Ensure required SDKs/runtimes are available.

### 10.4 Versioning and Maintenance

1. Tools are version-controlled with the project.
2. Tool `.design.md` must stay current.
3. Each tool should include unit tests and integration tests.

### 10.5 Tool Creation Script (`create_tool`)

1. Purpose: Scaffold a new tool project.
2. Parameters: `tool_name`, `language`, optional `tool_type`.
3. Behavior: Create directory structure, initialize project, generate `.design.md`, and prompt manual updates to `ai_project_map.json`.
