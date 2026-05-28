# -*- coding: utf-8 -*-
import argparse
import io
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.utils.cli_output import emit_error, emit_progress

# Keep smoke profiles explicit so CI and local runs share the same small,
# reviewable target set instead of relying on broad discovery.
SMOKE_PROFILES = {
    "core": [
        "tests.unit.test_config_manager",
        "tests.unit.test_dependency_resolver",
        "tests.unit.test_method_store",
        "tests.unit.test_vector_cache_required",
    ],
    "parser": [
        "tests.unit.test_design_doc_parser",
        "tests.unit.test_json_deserialize_guard",
    ],
    "synthesis": [
        "tests.unit.test_code_synthesizer_integration",
    ],
}
DEFAULT_PROFILES = ["core", "parser", "synthesis"]


def resolve_targets(selected_profiles: list[str] | None, explicit_targets: list[str] | None) -> list[str]:
    targets = []
    seen = set()

    for profile_name in selected_profiles or DEFAULT_PROFILES:
        for target in SMOKE_PROFILES[profile_name]:
            if target in seen:
                continue
            seen.add(target)
            targets.append(target)

    for target in explicit_targets or []:
        if target in seen:
            continue
        seen.add(target)
        targets.append(target)

    return targets


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the default unit smoke suite.")
    parser.add_argument(
        "--profile",
        action="append",
        choices=sorted(SMOKE_PROFILES.keys()),
        dest="profiles",
        help="Optional built-in smoke profile to run. Repeatable. Defaults to core + parser + synthesis.",
    )
    parser.add_argument(
        "--test-target",
        action="append",
        dest="test_targets",
        help="Optional unittest target to append. Repeatable. Profiles remain active unless omitted by --profile selection.",
    )
    parser.add_argument(
        "--verbosity",
        type=int,
        default=1,
        help="unittest verbosity level (default: 1)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    targets = resolve_targets(args.profiles, args.test_targets)
    for name in targets:
        suite.addTests(loader.loadTestsFromName(name))
    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=args.verbosity)
    result = runner.run(suite)
    rendered = stream.getvalue().strip()
    if rendered:
        if result.wasSuccessful():
            for line in rendered.splitlines():
                emit_progress(line)
        else:
            for line in rendered.splitlines():
                emit_error(line)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
