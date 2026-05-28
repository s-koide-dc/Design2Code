# -*- coding: utf-8 -*-
"""
CLI entrypoint for Advanced TDD support.

Usage examples:
  python scripts/validate/run_tdd.py --test-failure path/to/failure.json
  python scripts/validate/run_tdd.py --goal path/to/goal.json
"""
import argparse
import json
import os
import sys
from typing import Any, Dict

sys.path.append(os.getcwd())

from src.utils.cli_output import emit_json_stdout, emit_stderr


def load_json(path: str) -> Dict[str, Any]:
    if not path or not os.path.exists(path):
        raise FileNotFoundError(f"JSON not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    parser = argparse.ArgumentParser(description="Advanced TDD support CLI")
    parser.add_argument("--workspace", default=".", help="Workspace root (default: current dir)")
    parser.add_argument("--test-failure", help="Path to test failure JSON")
    parser.add_argument("--goal", help="Path to goal-driven TDD JSON")
    args = parser.parse_args()

    if not args.test_failure and not args.goal:
        parser.print_usage(sys.stderr)
        emit_stderr("エラー: --test-failure または --goal のどちらかを指定してください。")
        return 2

    from src.advanced_tdd.main import AdvancedTDDSupport

    tdd = AdvancedTDDSupport(args.workspace)
    try:
        if args.test_failure:
            payload = load_json(args.test_failure)
            result = tdd.analyze_and_fix_test_failure(payload)
        else:
            payload = load_json(args.goal)
            result = tdd.execute_goal_driven_tdd(payload)
    except FileNotFoundError as exc:
        emit_stderr(f"エラー: 入力JSONが見つかりません: {exc}")
        return 1
    except json.JSONDecodeError as exc:
        emit_stderr(f"エラー: 入力JSONの形式が不正です: {exc}")
        return 1
    except Exception as exc:
        emit_stderr(f"エラー: TDD CLI の実行に失敗しました: {exc}")
        return 1

    emit_json_stdout(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
