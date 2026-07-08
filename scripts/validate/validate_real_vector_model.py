# -*- coding: utf-8 -*-
"""Run real-vector integration tests in an environment that owns the model."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.config_manager import ConfigManager


TEST_MODULES = (
    "tests.integration.test_vector_engine_real_model",
    "tests.integration.test_semantic_method_search",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _model_identity(model_path: Path) -> dict:
    stat = model_path.stat()
    return {
        "name": model_path.name,
        "size_bytes": stat.st_size,
        "modified_utc": datetime.fromtimestamp(
            stat.st_mtime,
            tz=timezone.utc,
        ).isoformat(),
        "sha256": _sha256(model_path),
    }


def _run_module(module: str, timeout_seconds: int) -> dict:
    env = os.environ.copy()
    env.pop("SKIP_VECTOR_MODEL", None)
    env["SUPPRESS_VECTOR_WARNINGS"] = "1"
    started = time.monotonic()
    try:
        result = subprocess.run(
            [sys.executable, "-m", "unittest", module, "-v"],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            shell=False,
        )
        output = (result.stdout or "") + (result.stderr or "")
        return {
            "module": module,
            "status": "passed" if result.returncode == 0 else "failed",
            "return_code": result.returncode,
            "duration_seconds": round(time.monotonic() - started, 3),
            "output_tail": output[-4000:],
        }
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + (exc.stderr or "")
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        return {
            "module": module,
            "status": "timeout",
            "return_code": None,
            "duration_seconds": round(time.monotonic() - started, 3),
            "output_tail": output[-4000:],
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument(
        "--output",
        default="logs/real_vector_validation.json",
    )
    args = parser.parse_args()
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be greater than zero")

    config = ConfigManager(strict=True)
    model_path = Path(config.vector_model_path)
    required_paths = (
        model_path,
        Path(f"{model_path}.v0.vocab.npy"),
        Path(f"{model_path}.v0.matrix.npy"),
    )
    missing = [path.name for path in required_paths if not path.is_file()]
    if missing:
        print("Real vector assets are missing: " + ", ".join(missing), file=sys.stderr)
        return 2

    report = {
        "schema_version": 1,
        "executed_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version.split()[0],
        "model": _model_identity(model_path),
        "tests": [
            _run_module(module, args.timeout_seconds)
            for module in TEST_MODULES
        ],
    }
    report["status"] = (
        "passed"
        if all(test["status"] == "passed" for test in report["tests"])
        else "failed"
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temporary_path, output_path)
    print(f"Real vector validation: {report['status']} ({output_path})")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
