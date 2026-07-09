# -*- coding: utf-8 -*-
import json
import sys


def main():
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        response_text = payload.get("input", {}).get("response_text", "")
        instruction = payload.get("instruction", "")
        if not response_text:
            sys.stdout.write(json.dumps({"text": ""}, ensure_ascii=False) + "\n")
            sys.stdout.flush()
            continue

        suffix = "（整形）"
        if "自然" in instruction:
            suffix = "（自然化）"
        sys.stdout.write(json.dumps({"text": f"{response_text} {suffix}。"}, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
