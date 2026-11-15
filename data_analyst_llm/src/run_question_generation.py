import csv, json, sys
from pathlib import Path
from llm_engine import generate_question

ROOT = Path(__file__).resolve().parents[1]
def find_question(question_id):
    with open(ROOT/"data"/"question_bank.csv", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row["question_id"] == question_id:
                return row
    raise KeyError(question_id)

if __name__ == "__main__":
    question_id = sys.argv[1] if len(sys.argv) > 1 else "TECH-002"
    row = find_question(question_id)
    print(json.dumps(generate_question(row), ensure_ascii=False, indent=2))
