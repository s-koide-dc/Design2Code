# Pipeline Stages Design Document

## 1. Purpose
The `stages.py` module defines the discrete processing units that make up the AI's core execution pipeline [Phase 3]. Following the Chain of Responsibility pattern, each stage performs a specific type of analysis or action on the shared `context` object, enabling a modular, testable, and observable processing flow.

## 2. Structured Specification

### 2.1 Interface
- **Base Class**: `PipelineStage` (ABC)
- **Method**: `execute(context: dict, pipeline: Pipeline) -> dict`
- **Context**: A mutable dictionary acting as the blackboard for the session.

### 2.2 Stage Definitions

#### 2.2.1 SetupStage
- **Goal**: Initialize the request context.
- **Logic**:
    1.  **Validation**: Check input length (Max 200KB).
    2.  **Session Extraction**: Parse `session_id:` prefix or use default.
    3.  **Feedback**: If session is awaiting feedback, record it via `AutonomousLearning` and exit early.

#### 2.2.2 LanguageAnalysisStage
- **Goal**: Low-level linguistic processing.
- **Logic**:
    1.  Invoke `MorphAnalyzer` for tokenization.
    2.  Invoke `SyntacticAnalyzer` for dependency parsing.

#### 2.2.3 IntentDetectionStage
- **Goal**: Determine user intent and handle meta-commands.
- **Logic**:
    1.  Invoke `IntentDetector`.
    2.  **Correction**: If intent is "CORRECTION", enter feedback mode.
    3.  **Confirmation**: If intent is "AGREE"/"DISAGREE" and a plan is pending, confirm or cancel the plan.
        - On "AGREE", set `confirmation_granted = true` in the context and clear the pending plan.

#### 2.2.4 SemanticAnalysisStage
- **Goal**: Deep understanding and context history.
- **Logic**:
    1.  Retrieve history from `ContextManager`.
    2.  Invoke `SemanticAnalyzer`.
    3.  **Healing Detection**: Check if the previous turn resulted in an error to enable "Healing Mode".

#### 2.2.5 TaskManagementStage
- **Goal**: Update task states (TODO/IN_PROGRESS/DONE).
- **Logic**:
    1.  Invoke `TaskManager.manage_task_state`.
    2.  **Interruption**: If a conversational intent (e.g., GREETING) interrupts a task, generate a response and exit.

#### 2.2.6 ClarificationStage
- **Goal**: Resolve ambiguities.
- **Logic**:
    1.  Invoke `ClarificationManager`.
    2.  If clarification is needed, generate a question using `ResponseGenerator`.

#### 2.2.7 ExecutionStage
- **Goal**: Plan and execute actions (The "Doing" phase).
- **Logic**:
    -   **Loop**: Run up to `MAX_ITERATIONS` (10) or timeout (60s).
    1.  **Planning**: If no plan exists, invoke `Planner`.
    2.  **Recovery**: If healing is active, create a recovery task.
    3.  **Execution**: Invoke `ActionExecutor`.
    4.  **Chaining**: If task is a compound task, loop back to handle next sub-task.

#### 2.2.8 ResponseStage
- **Goal**: Finalize communication.
- **Logic**:
    1.  If no text response exists, generate one via `ResponseGenerator`.
    2.  Log completion.
    3.  Trigger `AutonomousLearning` (Session Completed).

### 2.3 Test Cases

#### Happy Path
1.  **Standard Query**:
    -   Input: "Hello"
    -   Flow: Setup -> Language -> Intent(GREETING) -> ... -> Task(Interrupted) -> Response.
2.  **Action Request**:
    -   Input: "Create file.txt"
    -   Flow: ... -> Intent(FILE_IO) -> Execution(Plan -> Execute) -> Response.

#### Edge Cases
1.  **Input Too Long**:
    -   Input: 300KB text.
    -   Result: Error returned in SetupStage.
2.  **Confirmation Denial**:
    -   Context: Pending plan. Input: "No".
    -   Result: IntentDetectionStage clears plan and sets intent to "DISAGREE".
3.  **Execution Timeout**:
    -   Condition: Execution loop runs > 60s.
    -   Result: Loop breaks, specific timeout message returned.
