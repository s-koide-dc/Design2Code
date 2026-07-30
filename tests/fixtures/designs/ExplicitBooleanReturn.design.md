# ExplicitBooleanReturn

## 1. Purpose

JSONの明示boolean return_valueをC#のboolリテラルとして返す。

## 2. Structured Specification

### Input

- **Description**: None
- **Type/Format**: void

### Output

- **Description**: status
- **Type/Format**: Task<bool>

### Core Logic

1. [ACTION|RETURN|bool|bool|NONE] [semantic_roles:{"return_value":true}] true を返す

### Test Cases

- **Scenario**: ExplicitTrue
- **Expected**: {"runtime_oracle":{"await":true,"return":true}}
