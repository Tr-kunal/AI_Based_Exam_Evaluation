import re

_MCQ_OPT = re.compile(r"\(([a-dA-D])\)")
_MCQ_LETTERS = {"a","b","c","d","A","B","C","D"}

def is_mcq(model_answer_text: str) -> bool:
    """
    Heuristic: treat as MCQ if the official model answer is a single option like '(C)' or starts with one.
    """
    if not isinstance(model_answer_text, str):
        return False
    # Starts with/equals (A)/(B) etc.
    mt = _MCQ_OPT.findall(model_answer_text)
    # If it looks like one clear option, it's MCQ
    return bool(mt) and len(model_answer_text.strip()) <= 8

def pick_student_choice(student_text: str) -> str | None:
    """
    Extract the chosen option letter from student answer text.
    If multiple different options present → return None (invalid).
    """
    if not isinstance(student_text, str):
        return None

    # collect letters in parentheses like (A) OR raw A/B/C/D tokens
    paren = re.findall(r"\(([a-dA-D])\)", student_text)
    loose = re.findall(r"\b([a-dA-D])\b", student_text)

    candidates = [c for c in paren + loose if c in _MCQ_LETTERS]
    candidates = [c.upper() for c in candidates]

    if not candidates:
        return None
    # if multiple and inconsistent → None
    if len(set(candidates)) > 1:
        return None
    return candidates[0]
