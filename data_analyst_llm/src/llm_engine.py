import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Menentukan folder utama project
ROOT = Path(__file__).resolve().parents[1]

# Membaca file .env dari folder utama
load_dotenv(ROOT / ".env")

from groq import Groq
from rag_engine import retrieve

PROMPT_DIR = ROOT / "prompts"

MODEL = os.getenv(
    "GROQ_MODEL",
    "llama-3.3-70b-versatile"
)

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError(
        "GROQ_API_KEY tidak ditemukan. Periksa file .env di folder utama."
    )

client = Groq(api_key=api_key)

def load_prompt(filename):
    return (PROMPT_DIR / filename).read_text(encoding="utf-8")

def call_json(prompt: str, temperature: float = 0.2):
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role":"system","content":"Return valid JSON only. Do not wrap it in markdown."},
                  {"role":"user","content":prompt}],
        temperature=temperature,
        response_format={"type":"json_object"}
    )
    content = response.choices[0].message.content
    return json.loads(content)

def evaluate_answer(question_row: dict, user_answer: str, rubric: dict):
    role = question_row.get("role") or "General"
    query = f"{question_row.get('topic','')} {question_row.get('question','')} {user_answer}"
    retrieved = retrieve(query, role if role != "General" else None, top_k=4)
    context = "\n\n".join(x["text"] for x in retrieved)
    qtype = question_row["question_type"]
    active_rubric = rubric["general_rubric"] if qtype == "general" else rubric["technical_rubric"]
    expected = question_row.get("expected_elements", [])
    if isinstance(expected, str):
        try: expected = json.loads(expected)
        except Exception: expected = [expected]
    template = load_prompt("02_answer_evaluation.txt")
    prompt = template.format(
        question_id=question_row["question_id"], question_type=qtype,
        role=role, experience_level=question_row.get("experience_level") or "Beginner",
        question=question_row["question"], user_answer=user_answer,
        expected_elements=json.dumps(expected, ensure_ascii=False),
        rubric=json.dumps(active_rubric, ensure_ascii=False),
        retrieved_context=context or "Tidak ada konteks referensi yang ditemukan."
    )
    result = call_json(prompt)
    result["retrieved_sources"] = list({x["source"] for x in retrieved})
    result["model"] = MODEL
    return result


def generate_question(question_row: dict):
    """Personalize one selected question while preserving its metadata and intent."""
    role = question_row.get("role") or "General"
    query = f"{question_row.get('topic','')} {question_row.get('question','')}"
    retrieved = retrieve(query, role if role != "General" else None, top_k=3)
    context = "\n\n".join(x["text"] for x in retrieved)
    expected = question_row.get("expected_elements", [])
    if isinstance(expected, str):
        try: expected = json.loads(expected)
        except Exception: expected = [expected]
    template = load_prompt("01_question_generation.txt")
    prompt = template.format(
        role=role,
        experience_level=question_row.get("experience_level") or "General",
        stage=question_row.get("stage",""),
        topic=question_row.get("topic",""),
        difficulty=question_row.get("difficulty",""),
        question_seed=question_row["question"].replace("{role}", role),
        expected_elements=json.dumps(expected, ensure_ascii=False),
        retrieved_context=context or "Tidak ada konteks referensi yang ditemukan."
    )
    result = call_json(prompt)
    result["source_question_id"] = question_row["question_id"]
    result["retrieved_sources"] = list({x["source"] for x in retrieved})
    return result
