import csv, json
from pathlib import Path
p = Path(__file__).resolve().parents[1] / "data" / "question_bank.csv"
with open(p, encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))
ids = [r["question_id"] for r in rows]
assert len(ids) == len(set(ids)), "Duplicate question_id"
general = [r for r in rows if r["question_type"] == "general"]
technical = [r for r in rows if r["question_type"] == "technical"]
assert len(general) == 2, f"Expected 2 general questions, got {len(general)}"
assert len(technical) == 45, f"Expected 45 technical questions, got {len(technical)}"
for role in ["Data Analyst","Data Scientist","Data Engineer"]:
    for level in ["Beginner","Intermediate","Advanced"]:
        subset = [r for r in technical if r["role"]==role and r["experience_level"]==level]
        assert len(subset)==5, f"{role}/{level}: expected 5, got {len(subset)}"
        for r in subset:
            assert len(json.loads(r["expected_elements"])) >= 3
print(f"OK: {len(rows)} questions (2 general + 45 technical), all combinations have 5 questions.")
