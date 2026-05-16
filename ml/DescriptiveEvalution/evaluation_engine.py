import json
from config import CONFIG
from align_answers import align_student_to_model
from score_utils import compute_subpart_score
from choice_handler import is_mcq, pick_student_choice

def _load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _get_attempt_required(qobj: dict):
    ar = qobj.get("attempt_required")
    if ar is not None:
        return ar
    return CONFIG["selection"]["default_attempt_required"]

def _get_selection_policy(qobj: dict) -> str:
    pol = qobj.get("selection_policy")
    if pol:
        return pol
    return CONFIG["selection"]["default_policy"]

def _norm_id(s: str) -> str:
    return s.lower().replace(".", "").replace("(", "").replace(")", "")

def _select_subparts_to_score(model_question: dict, aligned_map: dict[str, str]) -> list[str]:
    ids = [sp["id"] for sp in model_question.get("subparts", [])]
    norm_ids = [_norm_id(i) for i in ids]

    attempt_required = _get_attempt_required(model_question)
    policy = _get_selection_policy(model_question)

    if attempt_required == "all" or policy == "none":
        return norm_ids

    if isinstance(attempt_required, int) and policy == "first_n":
        present = [i for i in norm_ids if i in aligned_map and aligned_map[i].strip()]
        return present[:attempt_required]

    return norm_ids

def evaluate_student_answers(model_json_path: str, student_json_path: str, config: dict):
    model = _load_json(model_json_path)
    student = _load_json(student_json_path)

    questions = model.get("questions", model)

    report = {
        "total_awarded": 0.0,
        "total_max": 0.0,
        "percentage": 0.0,
        "by_question": {}
    }

    for mq in questions:
        qno_raw = str(mq.get("question_number", "")).strip()
        qno = qno_raw.replace("Q", "").replace("q", "").strip()
        subparts = mq.get("subparts", [])
        total_marks_q = sum(float(sp.get("marks", 0)) for sp in subparts)

        # align
        aligned = align_student_to_model(mq, student)

        # selection (choice handling)
        selected_ids = _select_subparts_to_score(mq, aligned)

        q_result = {
            "policy": {
                "missing_subpart_policy": "zero",
                "extra_attempt_policy": _get_selection_policy(mq),
                "weight_semantic": config["weights"]["semantic"],
                "weight_keyword": config["weights"]["keyword"],
                "attempt_required": _get_attempt_required(mq)
            },
            "subparts": {},
            "total_marks": total_marks_q,
            "final_score": 0.0,
            "notes": []
        }

        awarded_sum = 0.0

        # prepare maps
        sp_by_norm = {_norm_id(sp["id"]): sp for sp in subparts}

        # Always initialize every subpart with zeros in the report
        for sp in subparts:
            q_result["subparts"][sp["id"]] = {
                "semantic_score": 0.0,
                "keyword_score": 0.0,
                "score": 0.0,
                "marks": 0.0
            }

        if not selected_ids:
            if aligned:
                q_result["notes"].append("No subpart selected by policy (first_n) from answered ones.")
            else:
                q_result["notes"].append("No answers found for this question in student JSON.")

        # Score selected ones
        for sid in selected_ids:
            sp = sp_by_norm.get(sid)
            if not sp:
                continue

            model_ans = sp.get("model_answer", "")
            is_mcq_flag = is_mcq(model_ans)

            student_text = aligned.get(sid, "") or ""
            if is_mcq_flag:
                choice = pick_student_choice(student_text)
                if choice is None:
                    marks, sem, kw = 0.0, 0.0, 0.0
                else:
                    student_text = f"({choice})"
                    marks, sem, kw = compute_subpart_score(
                        model_ans, student_text, sp.get("marks", 0), config, True
                    )
            else:
                marks, sem, kw = compute_subpart_score(
                    model_ans, student_text, sp.get("marks", 0), config, False
                )

            awarded_sum += marks
            # write the actual scores into the original (human) id
            human_id = sp.get("id")
            q_result["subparts"][human_id] = {
                "semantic_score": sem,
                "keyword_score": kw,
                "score": round(config["weights"]["semantic"] * sem + config["weights"]["keyword"] * kw, 4),
                "marks": round(marks, 4)
            }

        q_result["final_score"] = round(awarded_sum, 4)
        report["by_question"][qno] = q_result
        report["total_awarded"] += awarded_sum
        report["total_max"] += total_marks_q

    report["total_awarded"] = round(report["total_awarded"], 4)
    report["total_max"] = round(report["total_max"], 1)
    report["percentage"] = round((report["total_awarded"] / report["total_max"] * 100.0), 2) if report["total_max"] else 0.0
    return report

def save_evaluation(result: dict, output_path: str = "evaluation_report.json"):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved → {output_path}")
