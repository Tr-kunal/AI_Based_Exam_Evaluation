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
    return {
        f"q{qnum}", f"question{qnum}", f"ques{qnum}", f"{qnum}",
        f"q-{qnum}", f"question-{qnum}", f"ques-{qnum}",
        f"q {qnum}", f"question {qnum}", f"ques {qnum}"
    }

def _find_question_section(student_root: Dict[str, Any], qnum: str):
    if not isinstance(student_root, dict):
        return None

    want = _candidate_keys_for(qnum)
    want_norm = {_norm_id(k) for k in want}
    want_digits = _extract_digits(qnum)

    # Pass 1: direct top-level matches
    for k, v in student_root.items():
        kn = _norm_id(k)
        if kn in want_norm:
            return v
        if _extract_digits(kn) == want_digits and want_digits:
            return v

    # Pass 2: look inside 1 level nested
    for _, v in student_root.items():
        if isinstance(v, dict):
            for kk, vv in v.items():
                kn = _norm_id(kk)
                if kn in want_norm or (_extract_digits(kn) == want_digits and want_digits):
                    return vv

    return None

def align_student_to_model(model_question: dict, student_root: dict) -> dict[str, str]:
    desired_ids = [_norm_id(sp["id"]) for sp in model_question.get("subparts", [])]

    raw_q = str(model_question.get("question_number", "")).strip()
    q_digits = _extract_digits(raw_q)

    section = _find_question_section(student_root or {}, q_digits)
    if section is None:
        return {}

    extracted: Dict[str, str] = {}

    def walk(key, val):
        keyn = _norm_id(str(key)) if key is not None else ""

        # ---------------------------
        # FIX: If this key is a subpart ID → flatten whole dict/list
        # ---------------------------
        if keyn and keyn in desired_ids:
            text = _flatten_value(val)
            if text.strip():
                extracted.setdefault(keyn, "")
                extracted[keyn] = (extracted[keyn] + " " + text).strip()

            # Still walk inside in case more text exists
            if isinstance(val, dict):
                for kk, vv in val.items():
                    walk(kk, vv)
            elif isinstance(val, list):
                for item in val:
                    walk(key, item)
            return

        # Normal recursive walk
        if isinstance(val, dict):
            for kk, vv in val.items():
                walk(kk, vv)
        elif isinstance(val, list):
            for item in val:
                walk(key, item)
        else:
            return

    if isinstance(section, dict):
        for k, v in section.items():
            walk(k, v)
    else:
        # 1-subpart case
        if len(desired_ids) == 1:
            extracted[desired_ids[0]] = _flatten_value(section)

    return {k: v for k, v in extracted.items() if k in desired_ids}
