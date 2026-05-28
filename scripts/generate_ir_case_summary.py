import argparse
import os
import re
import glob
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.utils.cli_output import emit_error, emit_progress

def parse_case_file(content: str) -> dict:
    data = {
        "case_id": "",
        "title": "",
        "benchmark_role": "",
        "primary": "",
        "secondary": ""
    }
    
    # Extract Case ID and Title
    title_match = re.search(r"^# Case (\d+):\s*(.+)$", content, re.MULTILINE)
    if title_match:
        data["case_id"] = title_match.group(1).strip()
        data["title"] = title_match.group(2).strip()

    # Extract Benchmark role
    role_match = re.search(r"^- Benchmark role:\s*(.+)$", content, re.MULTILINE)
    if role_match:
        data["benchmark_role"] = role_match.group(1).strip()

    # Extract Primary Failure
    primary_match = re.search(r"^- Primary:\s*(.+)$", content, re.MULTILINE)
    if primary_match:
        data["primary"] = primary_match.group(1).strip()

    # Extract Secondary Failure
    secondary_match = re.search(r"^- Secondary:\s*(.+)$", content, re.MULTILINE)
    if secondary_match:
        data["secondary"] = secondary_match.group(1).strip()

    return data

def generate_summary(cases_dir: str, output_path: str) -> int:
    case_files = glob.glob(os.path.join(cases_dir, "case_*.md"))
    if not os.path.isdir(cases_dir):
        emit_error(f"エラー: ケースディレクトリが見つかりません: {cases_dir}")
        return 1
    
    parsed_data = []
    for file_path in case_files:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            data = parse_case_file(content)
            if data["case_id"]:
                parsed_data.append(data)
                
    # Sort by case_id
    parsed_data.sort(key=lambda x: int(x["case_id"]))
    
    table_lines = [
        "# Case Summary Table",
        "",
        "| Case | Title | Benchmark Role | Primary Failure | Secondary Failure |",
        "|---|---|---|---|---|"
    ]
    
    for row in parsed_data:
        # Escape any pipes in the content to avoid breaking markdown table
        title = row["title"].replace("|", "\\|")
        role = row["benchmark_role"].replace("|", "\\|")
        primary = row["primary"].replace("|", "\\|")
        secondary = row["secondary"].replace("|", "\\|")
        
        table_lines.append(f"| {row['case_id']} | {title} | {role} | {primary} | {secondary} |")
        
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(table_lines) + "\n")
    emit_progress(f"Summary generated at: {output_path}")
    return 0


def parse_args() -> argparse.Namespace:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parser = argparse.ArgumentParser(description="Generate the IR case summary markdown table.")
    parser.add_argument(
        "--cases-dir",
        default=os.path.join(base_dir, "research", "ir_meaning_preservation", "cases"),
        help="Directory containing case_*.md files.",
    )
    parser.add_argument(
        "--output",
        default=os.path.join(base_dir, "research", "ir_meaning_preservation", "results", "case_summary_table.md"),
        help="Output markdown table path.",
    )
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    raise SystemExit(generate_summary(args.cases_dir, args.output))
