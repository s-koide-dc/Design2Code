# DummyService Design Document (Class: DummyService)

## 1. Purpose
Provide a dummy service for verification.

## 2. Structured Specification
### Input
- **Description**: Target data
- **Type/Format**: string

### Core Logic
1. Call executor.execute
2. Return message

### Test Cases
- **Scenario**: Happy Path
- **Input**:
```json
{
  "init_args": {
    "name": "TestService"
  },
  "mocks": {
    "action_executor": {
      "execute.return_value": "success"
    }
  },
  "target_method": "perform_action",
  "args": {
    "target": "item1"
  }
}
```
- **Expected**: "Action performed on item1 by TestService"
