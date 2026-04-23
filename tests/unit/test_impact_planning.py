# -*- coding: utf-8 -*-
import os
import sys
import json
from pathlib import Path

# Adjust path to include src
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.pipeline_core.pipeline_core import Pipeline

def test_impact_planning():
    print("=== Impact Analysis Planning Test ===")
    pipeline = Pipeline()
    
    # 1. Analyze the file to build the initial graph
    print("\n[Step 1] Analyzing project with dependencies and tests...")
    # Use .csproj instead of .cs to support MyRoslynAnalyzer's requirements
    context1 = pipeline.run("tests/fixtures/GeneralityCheck/GeneralityCheck.csproj を解析して")
    output_path = context1["analysis"]["entities"].get("output_path", {}).get("value")
    
    if not output_path:
        print("❌ Analysis failed, no output_path generated.")
        return

    # 2. Simulate APPLY_CODE_FIX for ServiceB.GetData
    print("\n[Step 2] Planning a fix for 'DependencyDemo.ServiceB.GetData'...")
    
    input_text = f"session_id:{context1['session_id']} 修正案 heal_123 を適用して"
    
    # Simulate past context with target_name and output_path in history
    past_context = {
        "session_id": context1['session_id'],
        "analysis": {
            "intent": "CS_ANALYZE",
            "entities": {
                "target_name": {"value": "DependencyDemo.ServiceB.GetData", "confidence": 1.0},
                "output_path": {"value": output_path, "confidence": 1.0}
            }
        }
    }
    pipeline.context_manager.add_context(past_context)
    
    context2 = pipeline.run(input_text)
    
    plan = context2.get("plan", {})
    print(f"Planned Action: {plan.get('action_method')}")
    
    impacted = plan.get("impacted_methods", [])
    print(f"Impacted Methods detected: {impacted}")
    
    suggested_tests = plan.get("suggested_tests", [])
    print(f"Suggested Tests detected: {[t['test_class'] for t in suggested_tests]}")
    
    # Verify impact
    expected_callers = ["DependencyDemo.ServiceA.Process", "DependencyDemo.Client.Run"]
    
    success = True
    for expected in expected_callers:
        if expected in impacted:
            print(f"✅ Found expected impact: {expected}")
        else:
            print(f"❌ Missing expected impact: {expected}")
            success = False

    # Verify suggested tests
    if any("ServiceATests" in t["test_class"] for t in suggested_tests):
        print(f"✅ Found expected test suggestion: ServiceATests")
    else:
        print(f"❌ Missing expected test suggestion: ServiceATests")
        success = False
            
    if success:
        print("\n🎉 Impact Analysis & Test Suggestion Planning Successful!")
    else:
        print("\nPartial failure in detection.")

if __name__ == "__main__":
    test_impact_planning()