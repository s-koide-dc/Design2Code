# -*- coding: utf-8 -*-
import sys
import os
import json

# プロジェクトルートをパスに追加
sys.path.append(os.getcwd())

from src.autonomous_learning.autonomous_learning import AutonomousLearning

def run_bootstrap_learning():
    workspace_root = os.getcwd()
    learner = AutonomousLearning(workspace_root)
    
    print("Running learning cycle...")
    result = learner.run_learning_cycle()
    
    print("Learning Result:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    if result['status'] == 'success':
        print(f"Applied rules: {result.get('rules_applied', 0)}")
        print(f"Patterns found: {result.get('patterns_found', 0)}")
    else:
        print(f"Learning skipped or failed: {result.get('reason', 'Unknown')}")

if __name__ == "__main__":
    run_bootstrap_learning()
