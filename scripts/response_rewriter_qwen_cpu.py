# -*- coding: utf-8 -*-
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.response_rewriter.qwen_cpu_runner import main


if __name__ == "__main__":
    main()
