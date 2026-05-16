# from semantic_similarity import semantic_similarity
# from keyword_extractor import keyword_match_score
# from normalize_text import normalize_text


# def _length_ratio(model_answer: str, student_answer: str, config: dict) -> float:
#     """
#     Approximate ratio of student answer length to model answer length,
#     based on normalized token counts.
#     """
#     tcfg = config["text_cleaning"]

#     m_norm = normalize_text(
#         model_answer,
#         tcfg["remove_stopwords"],
#         tcfg["use_synonyms"],
#         tcfg.get("apply_stemming", False),
#         tcfg.get("apply_lemmatization", False),
#         tcfg.get("normalize_numbers", False)
#     )
#     s_norm = normalize_text(
#         student_answer,
#         tcfg["remove_stopwords"],
#         tcfg["use_synonyms"],
#         tcfg.get("apply_stemming", False),
#         tcfg.get("apply_lemmatization", False),
#         tcfg.get("normalize_numbers", False)
#     )

#     if not m_norm or not s_norm:
#         return 0.0

#     m_len = len(m_norm.split())
#     s_len = len(s_norm.split())

#     if m_len == 0:
#         return 0.0

#     return s_len / m_len


# def compute_subpart_score(model_answer, student_answer, max_marks, config, is_mcq=False):
#     """
#     Balanced scoring:

#     - MCQ:
#         full marks if semantic similarity >= mcq_min_correct_score, else 0.

#     - Subjective:
#         1) Compute semantic + keyword weighted score in [0,1].
#         2) Apply length-based penalty if answer is too short.
#         3) If combined < min_partial_score → 0 marks.
#         4) Otherwise, marks = combined * max_marks, with a small boost
#            in the mid range to avoid being too harsh.
#     """
#     if not student_answer or not isinstance(student_answer, str) or not student_answer.strip():
#         return 0.0, 0.0, 0.0

#     max_marks = float(max_marks)

#     # Base components
#     sem = semantic_similarity(model_answer, student_answer, config)
#     kw = keyword_match_score(model_answer, student_answer, config)

#     w_sem = config["weights"]["semantic"]
#     w_kw = config["weights"]["keyword"]

#     combined = w_sem * sem + w_kw * kw

#     thresholds = config["thresholds"]
#     min_partial = thresholds["min_partial_score"]

#     if is_mcq:
#         # For MCQ we rely mostly on semantic proximity of chosen option
#         mcq_thr = thresholds["mcq_min_correct_score"]
#         if sem >= mcq_thr:
#             final_marks = max_marks
#         else:
#             final_marks = 0.0
#         return round(final_marks, 4), round(sem, 4), round(kw, 4)

#     # ----- Subjective questions: apply length penalty -----
#     length_ratio = _length_ratio(model_answer, student_answer, config)
#     min_len_ratio = thresholds.get("min_length_ratio", 0.0)
#     len_penalty_strength = thresholds.get("length_penalty_strength", 1.0)

#     if min_len_ratio > 0 and length_ratio > 0:
#         if length_ratio < min_len_ratio:
#             # Penalize if student writes much less than model
#             # Factor between ~0.3 and 1 depending on how short it is
#             factor = (length_ratio / min_len_ratio) ** len_penalty_strength
#             factor = max(0.3, min(1.0, factor))
#             combined *= factor

#     # Clamp combined to [0,1] just to be safe
#     combined = max(0.0, min(1.0, combined))

#     # Hard floor for "almost nothing"
#     if combined < min_partial:
#         final_marks = 0.0
#     else:
#         # Balanced behaviour: give a small bump in mid-range
#         # so that borderline 0.25–0.5 don't feel too punishing.
#         if combined < 0.5:
#             combined = min(0.5, combined + 0.1)
#         final_marks = combined * max_marks

#     return round(final_marks, 4), round(sem, 4), round(kw, 4)



from semantic_similarity import semantic_similarity
from keyword_extractor import keyword_match_score
from normalize_text import normalize_text


def _length_ratio(model_answer: str, student_answer: str, config: dict) -> float:
    """
    Approximate ratio of student answer length to model answer length,
    based on normalized token counts.
    """
    tcfg = config["text_cleaning"]

    m_norm = normalize_text(
        model_answer,
        tcfg["remove_stopwords"],
        tcfg["use_synonyms"],
        tcfg.get("apply_stemming", False),
        tcfg.get("apply_lemmatization", False),
        tcfg.get("normalize_numbers", False)
    )
    s_norm = normalize_text(
        student_answer,
        tcfg["remove_stopwords"],
        tcfg["use_synonyms"],
        tcfg.get("apply_stemming", False),
        tcfg.get("apply_lemmatization", False),
        tcfg.get("normalize_numbers", False)
    )

    if not m_norm or not s_norm:
        return 0.0

    m_len = len(m_norm.split())
    s_len = len(s_norm.split())

    if m_len == 0:
        return 0.0

    return s_len / m_len


def compute_subpart_score(model_answer, student_answer, max_marks, config, is_mcq=False):
    """
    Balanced scoring with teacher-style rounding:

    - MCQ:
        full marks if semantic similarity >= mcq_min_correct_score, else 0.

    - Subjective:
        1) Compute semantic + keyword weighted score in [0,1].
        2) Apply length-based penalty if answer is too short.
        3) If combined < min_partial_score → 0 marks.
        4) Otherwise, marks = combined * max_marks
        5) ROUNDED to nearest 0.25 like teachers do.
    """
    if not student_answer or not isinstance(student_answer, str) or not student_answer.strip():
        return 0.0, 0.0, 0.0

    max_marks = float(max_marks)

    # Base components
    sem = semantic_similarity(model_answer, student_answer, config)
    kw = keyword_match_score(model_answer, student_answer, config)

    w_sem = config["weights"]["semantic"]
    w_kw = config["weights"]["keyword"]

    combined = w_sem * sem + w_kw * kw

    thresholds = config["thresholds"]
    min_partial = thresholds["min_partial_score"]

    # ----- MCQ CASE -----
    if is_mcq:
        mcq_thr = thresholds["mcq_min_correct_score"]
        if sem >= mcq_thr:
            final_marks = max_marks
        else:
            final_marks = 0.0

        # Teacher rounding for MCQ too
        final_marks = round(final_marks * 4) / 4
        return final_marks, round(sem, 4), round(kw, 4)

    # ----- SUBJECTIVE CASE -----

    # 1. Length penalty (soft)
    length_ratio = _length_ratio(model_answer, student_answer, config)
    min_len_ratio = thresholds.get("min_length_ratio", 0.0)
    len_penalty_strength = thresholds.get("length_penalty_strength", 1.0)

    if min_len_ratio > 0 and length_ratio > 0:
        if length_ratio < min_len_ratio:
            factor = (length_ratio / min_len_ratio) ** len_penalty_strength
            factor = max(0.3, min(1.0, factor))
            combined *= factor

    # Ensure combined stays in range
    combined = max(0.0, min(1.0, combined))

    # 2. If too low → 0 marks
    if combined < min_partial:
        final_marks = 0.0
    else:
        # Add slight mid-range boost (balanced style)
        if combined < 0.5:
            combined = min(0.5, combined + 0.1)

        final_marks = combined * max_marks

    # ---------- Teacher rounding (0.25 increments) ----------
    final_marks = round(final_marks * 4) / 4

    return final_marks, round(sem, 4), round(kw, 4)
