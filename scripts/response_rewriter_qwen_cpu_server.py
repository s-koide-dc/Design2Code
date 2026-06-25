import sys
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from src.response_rewriter.qwen_cpu_runner import serve_forever


if __name__ == "__main__":
    serve_forever()
