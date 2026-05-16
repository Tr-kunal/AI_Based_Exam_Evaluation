from semantic_similarity import semantic_similarity
from keyword_extractor import keyword_match_score

def compute_subpart_score(model_answer, student_answer, max_marks, config, is_mcq=False):
    """
    Scoring:
    - MCQ: full marks only if semantic similarity >= threshold; else 0.
    - Subjective: weighted partial based on similarity & keyword match,
      but clamp to 0 if combined < min_partial_score.
    """
    if not student_answer or not isinstance(student_answer, str) or not student_answer.strip():
        return 0.0, 0.0, 0.0

    sem = semantic_similarity(model_answer, student_answer, config)
    kw = keyword_match_score(model_answer, student_answer, config)
    combined = config["weights"]["semantic"] * sem + config["weights"]["keyword"] * kw

    if is_mcq:
        if sem >= config["thresholds"]["mcq_min_correct_score"]:
            final_marks = float(max_marks)
        else:
            final_marks = 0.0
    else:
        if combined < config["thresholds"]["min_partial_score"]:
            final_marks = 0.0
        else:
            final_marks = round(combined * float(max_marks), 4)

    return round(final_marks, 4), round(sem, 4), round(kw, 4)
