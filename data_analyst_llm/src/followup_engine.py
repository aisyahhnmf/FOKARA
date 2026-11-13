import json
from llm_engine import call_json, load_prompt

MAX_FOLLOWUPS = 2

def create_followup(main_question: str, user_answer: str, missing_elements: list,
                    previous_followups: list, role: str, experience_level: str):
    """Create one follow-up; caller must enforce MAX_FOLLOWUPS per parent question."""
    if not missing_elements or len(previous_followups) >= MAX_FOLLOWUPS:
        return {"needs_followup": False, "followup_question": None,
                "target_missing_element": None}
    prompt = load_prompt("03_followup_generation.txt").format(
        main_question=main_question,
        user_answer=user_answer,
        missing_elements=json.dumps(missing_elements, ensure_ascii=False),
        previous_followups=json.dumps(previous_followups, ensure_ascii=False),
        role=role,
        experience_level=experience_level
    )
    result = call_json(prompt)
    if len(previous_followups) >= MAX_FOLLOWUPS:
        result["needs_followup"] = False
        result["followup_question"] = None
    return result
