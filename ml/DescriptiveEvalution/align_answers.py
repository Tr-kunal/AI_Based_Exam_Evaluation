import re
from typing import Any, Dict

def _norm_id(s: str) -> str:
    if not s:
        return ""
    s = str(s).strip()
    s = s.replace("(", "").replace(")", "").replace(".", "")
    return s.lower()

def _flatten_value(v: Any) -> str:
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        return " ".join(_flatten_value(x) for x in v)
    if isinstance(v, dict):
        return " ".join(_flatten_value(x) for x in v.values())
    return ""

_digit_rx = re.compile(r"\d+")

def _extract_digits(s: str) -> str:
    m = _digit_rx.findall(s or "")
    return "".join(m) if m else ""

def _candidate_keys_for(qnum: str):
    # Accept many common patterns for "Question X"
    return {
        f"q{qnum}", f"question{qnum}", f"ques{qnum}", f"{qnum}",
        f"q-{qnum}", f"question-{qnum}", f"ques-{qnum}",
        f"q {qnum}", f"question {qnum}", f"ques {qnum}"
    }

def _find_question_section(student_root: Dict[str, Any], qnum: str):
    """
    Try multiple strategies to find the student section for question `qnum`.
    1) Exact/fuzzy key match on the top-level.
    2) Digit-based match (extract only digits and compare).
    3) One-level nested search if top-level fails.
    """
    if not isinstance(student_root, dict):
        return None

    want = _candidate_keys_for(qnum)
    want_norm = {_norm_id(k) for k in want}
    want_digits = _extract_digits(qnum)

    # Pass 1: direct/fuzzy on top-level keys
    for k, v in student_root.items():
        kn = _norm_id(k)
        if kn in want_norm:
            return v
        if _extract_digits(kn) == want_digits and want_digits:
            return v

    # Pass 2: look one level deeper (e.g., {"Section A": {"Q3": ...}})
    for _, v in student_root.items():
        if isinstance(v, dict):
            for kk, vv in v.items():
                kn = _norm_id(kk)
                if kn in want_norm or (_extract_digits(kn) == want_digits and want_digits):
                    return vv

    return None

def align_student_to_model(model_question: dict, student_root: dict) -> dict[str, str]:
    """
    Returns: subpart_id_norm -> student_text
    Works for nested shapes and many question-key spellings.
    """
    desired_ids = [_norm_id(sp["id"]) for sp in model_question.get("subparts", [])]

    # question number (keep only digits for resilient matching)
    raw_q = str(model_question.get("question_number", "")).strip()
    q_digits = _extract_digits(raw_q)

    section = _find_question_section(student_root or {}, q_digits)
    if section is None:
        return {}

    extracted: Dict[str, str] = {}

    def walk(key, val):
        keyn = _norm_id(str(key)) if key is not None else ""
        if isinstance(val, dict):
            for kk, vv in val.items():
                walk(kk, vv)
        elif isinstance(val, list):
            for item in val:
                walk(key, item)
        else:
            text = _flatten_value(val)
            if keyn and keyn in desired_ids:
                extracted.setdefault(keyn, "")
                extracted[keyn] = (extracted[keyn] + " " + text).strip()

    if isinstance(section, dict):
        for k, v in section.items():
            walk(k, v)
    else:
        # If the question has exactly 1 subpart in model but student wrote a single blob
        if len(desired_ids) == 1:
            extracted[desired_ids[0]] = _flatten_value(section)

    # keep only requested ids
    return {k: v for k, v in extracted.items() if k in desired_ids}
