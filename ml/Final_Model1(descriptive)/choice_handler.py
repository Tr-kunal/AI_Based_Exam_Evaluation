import re

# Improved MCQ detector: matches (A), (b), (C) Answer text...
_MCQ_PREFIX = re.compile(r"^\(\s*[a-dA-D]\s*\)")

_MCQ_LETTERS = {"a","b","c","d","A","B","C","D"}

def is_mcq(model_answer_text: str) -> bool:
    """
    Detect MCQ if the model answer starts with an option (A)/(B)/(C)/(D).
    Works even if text follows.
    """
    if not isinstance(model_answer_text, str):
        return False
    return bool(_MCQ_PREFIX.match(model_answer_text.strip()))

def pick_student_choice(student_text: str) -> str | None:
    if not isinstance(student_text, str):
        return None

    paren = re.findall(r"\(([a-dA-D])\)", student_text)
    loose = re.findall(r"\b([a-dA-D])\b", student_text)

    candidates = [c.upper() for c in paren + loose if c in _MCQ_LETTERS]

    if not candidates:
        return None

    if len(set(candidates)) > 1:
        return None

    return candidates[0]
