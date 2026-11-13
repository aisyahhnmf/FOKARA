import csv, json
from pathlib import Path
from llm_engine import evaluate_answer

ROOT = Path(__file__).resolve().parents[1]
RUBRIC = json.loads((ROOT/"data"/"rubric.json").read_text(encoding="utf-8"))

def find_question(question_id):
    with open(ROOT/"data"/"question_bank.csv", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row["question_id"] == question_id:
                row["expected_elements"] = json.loads(row["expected_elements"])
                return row
    raise KeyError(question_id)

if __name__ == "__main__":
    q = find_question("TECH-002")
    answer = input("Masukkan jawaban kandidat: ")
    print(json.dumps(evaluate_answer(q, answer, RUBRIC), ensure_ascii=False, indent=2))
