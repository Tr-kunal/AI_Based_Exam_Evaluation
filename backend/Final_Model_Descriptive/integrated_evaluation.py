"""
Integrated Automated Answer Evaluation System
==============================================

This script combines all evaluation components into a single, comprehensive solution
for automated grading of student answers against model answers.

Features:
- Semantic similarity scoring using sentence transformers
- Keyword-based matching with YAKE extraction
- MCQ detection and handling
- Flexible answer alignment
- Configurable scoring policies
- Detailed evaluation reports

Usage:
    python integrated_evaluation.py --model data/model_answers.json --student data/student_answers.json --output report.json

Author: Automated Evaluation System
Version: 1.0
"""

import json
import re
import argparse
from typing import Any, Dict
from pathlib import Path
from difflib import SequenceMatcher
import threading

# External dependencies
# External dependencies
# from sentence_transformers import SentenceTransformer, util  <-- Moved to lazy load
from unidecode import unidecode
import yake

try:
    from nltk.stem import PorterStemmer, WordNetLemmatizer
    _STEMMER = PorterStemmer()
    _LEMMATIZER = WordNetLemmatizer()
except Exception:
    _STEMMER = None
    _LEMMATIZER = None


# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG = {
    # --------- WEIGHTS (Balanced style) ----------
    "weights": {
        "semantic": 0.8,   # sentence-transformer similarity
        "keyword": 0.2     # YAKE-based keyword match
    },

    # --------- THRESHOLDS & PENALTIES ------------
    "thresholds": {
        "min_partial_score": 0.20,
        "mcq_min_correct_score": 0.60,
        "min_length_ratio": 0.15,
        "length_penalty_strength": 0.4
    },

    # --------- SEMANTIC SIMILARITY SETTINGS -------
    "semantic": {
        "model_name": "sentence-transformers/all-MiniLM-L6-v2",
        "rescale_to_unit": True
    },

    # --------- TEXT CLEANING PIPELINE -------------
    "text_cleaning": {
        "lowercase": True,
        "strip_punct": True,
        "collapse_space": True,
        "remove_stopwords": True,
        "use_synonyms": False,
        "apply_stemming": False,
        "apply_lemmatization": False,
        "normalize_numbers": False
    },

    # --------- KEYWORD EXTRACTION & MATCHING -----
    "keywords": {
        "top_k": 15,
        "minlen": 3,
        "use_fuzzy": True,
        "fuzzy_threshold": 0.88
    },

    # --------- SELECTION POLICY (choice questions) -
    "selection": {
        "default_policy": "none",
        "default_attempt_required": "all"
    }
}


# ============================================================================
# TEXT NORMALIZATION
# ============================================================================

_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "so", "to", "of", "in", "on", "at", "by", "for",
    "with", "as", "is", "are", "was", "were", "be", "been", "being", "this", "that", "these",
    "those", "it", "its", "from", "into", "about", "over", "after", "before", "not", "no",
    "do", "does", "did", "doing", "have", "has", "had", "having", "than", "then", "there",
    "here", "such", "very", "can", "could", "should", "would", "may", "might", "will", "shall"
}

_NUM_RX = re.compile(r"\d+")


def _strip_punct(text: str) -> str:
    """Replace any non-word / non-space character with a space"""
    return re.sub(r"[^\w\s]", " ", text)


def normalize_text(
    text: str,
    remove_stopwords: bool = True,
    use_synonyms: bool = False,
    apply_stemming: bool = False,
    apply_lemmatization: bool = False,
    normalize_numbers: bool = False
) -> str:
    """
    Safe string normalizer with multiple preprocessing options.
    
    Args:
        text: Input text to normalize
        remove_stopwords: Remove common stopwords
        use_synonyms: Reserved for future use
        apply_stemming: Apply Porter stemming
        apply_lemmatization: Apply WordNet lemmatization
        normalize_numbers: Replace numbers with <num> token
    
    Returns:
        Normalized text string
    """
    if not isinstance(text, str):
        return ""

    # Transliterate unicode to ASCII
    text = unidecode(text)
    text = text.lower()

    if normalize_numbers:
        text = _NUM_RX.sub(" <num> ", text)

    text = _strip_punct(text)
    text = re.sub(r"\s+", " ", text).strip()

    tokens = text.split()

    if remove_stopwords:
        tokens = [t for t in tokens if t not in _STOPWORDS]

    if apply_stemming and _STEMMER is not None:
        tokens = [_STEMMER.stem(t) for t in tokens]

    if apply_lemmatization and _LEMMATIZER is not None:
        tokens = [_LEMMATIZER.lemmatize(t) for t in tokens]

    return " ".join(tokens)


# ============================================================================
# SEMANTIC SIMILARITY
# ============================================================================

_model = None
_model_lock = threading.Lock()


def _get_model(config: dict):
    """Lazy-load sentence transformer model (thread-safe singleton)"""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                sem_cfg = config.get("semantic", {})
                model_name = sem_cfg.get(
                    "model_name",
                    "sentence-transformers/all-MiniLM-L6-v2"
                )
                from sentence_transformers import SentenceTransformer
                _model = SentenceTransformer(model_name)
    return _model


def semantic_similarity(text1: str, text2: str, config: dict) -> float:
    """
    Compute semantic similarity between two texts using sentence transformers.
    
    Args:
        text1: First text (typically model answer)
        text2: Second text (typically student answer)
        config: Configuration dictionary
    
    Returns:
        Similarity score in range [0, 1]
    """
    if not text1 or not text2:
        return 0.0

    tcfg = config["text_cleaning"]

    t1 = normalize_text(
        text1,
        tcfg["remove_stopwords"],
        tcfg["use_synonyms"],
        tcfg.get("apply_stemming", False),
        tcfg.get("apply_lemmatization", False),
        tcfg.get("normalize_numbers", False)
    )
    t2 = normalize_text(
        text2,
        tcfg["remove_stopwords"],
        tcfg["use_synonyms"],
        tcfg.get("apply_stemming", False),
        tcfg.get("apply_lemmatization", False),
        tcfg.get("normalize_numbers", False)
    )

    if not t1 or not t2:
        return 0.0

    model = _get_model(config)
    emb1 = model.encode(t1, convert_to_tensor=True)
    emb2 = model.encode(t2, convert_to_tensor=True)

    from sentence_transformers import util
    sim_raw = float(util.cos_sim(emb1, emb2).item())

    sem_cfg = config.get("semantic", {})
    if sem_cfg.get("rescale_to_unit", True):
        sim = (sim_raw + 1.0) / 2.0
    else:
        sim = sim_raw

    sim = max(0.0, min(1.0, sim))
    return round(sim, 4)


# ============================================================================
# KEYWORD EXTRACTION & MATCHING
# ============================================================================

def _fuzzy_match(a: str, b: str) -> float:
    """Compute fuzzy string similarity using SequenceMatcher"""
    return SequenceMatcher(None, a, b).ratio()


def _keywords(text: str, k: int, minlen: int) -> list[str]:
    """
    Extract up to k keyword candidates from text using YAKE.
    
    Args:
        text: Input text
        k: Maximum number of keywords to extract
        minlen: Minimum keyword length
    
    Returns:
        List of extracted keywords
    """
    if not text:
        return []

    kw_extractor = yake.KeywordExtractor(top=k * 2, n=1, dedupLim=0.9)
    candidates = [w for w, _ in kw_extractor.extract_keywords(text)]

    seen = set()
    out = []
    for c in candidates:
        c = c.strip()
        if len(c) >= minlen and c not in seen:
            seen.add(c)
            out.append(c)
        if len(out) >= k:
            break

    return out


def keyword_match_score(model_answer: str, student_answer: str, config: dict) -> float:
    """
    Compute keyword overlap score based on YAKE keywords from model answer.
    
    Args:
        model_answer: Model answer text
        student_answer: Student answer text
        config: Configuration dictionary
    
    Returns:
        Keyword match score in range [0, 1]
    """
    if not model_answer or not student_answer:
        return 0.0

    kcfg = config["keywords"]
    tcfg = config["text_cleaning"]

    keys = _keywords(model_answer, kcfg["top_k"], kcfg["minlen"])

    s_norm = normalize_text(
        student_answer,
        tcfg["remove_stopwords"],
        tcfg["use_synonyms"],
        tcfg.get("apply_stemming", False),
        tcfg.get("apply_lemmatization", False),
        tcfg.get("normalize_numbers", False)
    )
    if not s_norm:
        return 0.0

    s_tokens = set(s_norm.split())
    hits = 0

    for key in keys:
        k_norm = normalize_text(
            key,
            tcfg["remove_stopwords"],
            tcfg["use_synonyms"],
            tcfg.get("apply_stemming", False),
            tcfg.get("apply_lemmatization", False),
            tcfg.get("normalize_numbers", False)
        )

        if not k_norm:
            continue

        if k_norm in s_tokens:
            hits += 1
        elif kcfg["use_fuzzy"]:
            best = max((_fuzzy_match(k_norm, t) for t in s_tokens), default=0.0)
            if best >= kcfg["fuzzy_threshold"]:
                hits += 1

    if not keys:
        return 0.0

    score = hits / len(keys)
    score = max(0.0, min(1.0, score))
    return round(score, 4)


# ============================================================================
# MCQ HANDLING
# ============================================================================

_MCQ_PREFIX = re.compile(r"^\(\s*[a-dA-D]\s*\)")
_MCQ_LETTERS = {"a", "b", "c", "d", "A", "B", "C", "D"}


def is_mcq(model_answer_text: str) -> bool:
    """
    Detect if answer is MCQ format (starts with option like (A), (B), etc.)
    
    Args:
        model_answer_text: Model answer text
    
    Returns:
        True if MCQ format detected
    """
    if not isinstance(model_answer_text, str):
        return False
    return bool(_MCQ_PREFIX.match(model_answer_text.strip()))


def pick_student_choice(student_text: str) -> str | None:
    """
    Extract student's MCQ choice from their answer.
    
    Args:
        student_text: Student answer text
    
    Returns:
        Selected choice (A/B/C/D) or None if ambiguous/missing
    """
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


# ============================================================================
# ANSWER ALIGNMENT
# ============================================================================

def _norm_id(s: str) -> str:
    """Normalize subpart ID for matching"""
    if not s:
        return ""
    s = str(s).strip()
    s = s.replace("(", "").replace(")", "").replace(".", "")
    return s.lower()


def _flatten_value(v: Any) -> str:
    """Recursively flatten nested structures to text"""
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        return " ".join(_flatten_value(x) for x in v)
    if isinstance(v, dict):
        return " ".join(_flatten_value(x) for x in v.values())
    return ""


_digit_rx = re.compile(r"\d+")


def _extract_digits(s: str) -> str:
    """Extract all digits from string"""
    m = _digit_rx.findall(s or "")
    return "".join(m) if m else ""


def _candidate_keys_for(qnum: str):
    """Generate possible key variations for question number"""
    return {
        f"q{qnum}", f"question{qnum}", f"ques{qnum}", f"{qnum}",
        f"q-{qnum}", f"question-{qnum}", f"ques-{qnum}",
        f"q {qnum}", f"question {qnum}", f"ques {qnum}"
    }


def _find_question_section(student_root: Dict[str, Any], qnum: str):
    """Find the student's answer section for a given question number"""
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
    """
    Align student answers to model answer subparts.
    
    Args:
        model_question: Model question structure
        student_root: Student answers root structure
    
    Returns:
        Dictionary mapping normalized subpart IDs to student answer text
    """
    desired_ids = [_norm_id(sp["id"]) for sp in model_question.get("subparts", [])]

    raw_q = str(model_question.get("question_number", "")).strip()
    q_digits = _extract_digits(raw_q)

    section = _find_question_section(student_root or {}, q_digits)
    if section is None:
        return {}

    extracted: Dict[str, str] = {}

    def walk(key, val):
        keyn = _norm_id(str(key)) if key is not None else ""

        if keyn and keyn in desired_ids:
            text = _flatten_value(val)
            if text.strip():
                extracted.setdefault(keyn, "")
                extracted[keyn] = (extracted[keyn] + " " + text).strip()

            if isinstance(val, dict):
                for kk, vv in val.items():
                    walk(kk, vv)
            elif isinstance(val, list):
                for item in val:
                    walk(key, item)
            return

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
        if len(desired_ids) == 1:
            extracted[desired_ids[0]] = _flatten_value(section)

    return {k: v for k, v in extracted.items() if k in desired_ids}


# ============================================================================
# SCORING UTILITIES
# ============================================================================

def _length_ratio(model_answer: str, student_answer: str, config: dict) -> float:
    """
    Compute ratio of student answer length to model answer length.
    
    Args:
        model_answer: Model answer text
        student_answer: Student answer text
        config: Configuration dictionary
    
    Returns:
        Length ratio (0.0 to infinity)
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
    Compute score for a single subpart with balanced scoring approach.
    
    Args:
        model_answer: Model answer text
        student_answer: Student answer text
        max_marks: Maximum marks for this subpart
        config: Configuration dictionary
        is_mcq: Whether this is an MCQ question
    
    Returns:
        Tuple of (final_marks, semantic_score, keyword_score)
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

    # Teacher rounding (0.25 increments)
    final_marks = round(final_marks * 4) / 4

    return final_marks, round(sem, 4), round(kw, 4)


# ============================================================================
# EVALUATION ENGINE
# ============================================================================

def _load_json(path: str):
    """Load JSON file"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_attempt_required(qobj: dict):
    """Get attempt_required setting for question"""
    ar = qobj.get("attempt_required")
    if ar is not None:
        return ar
    return CONFIG["selection"]["default_attempt_required"]


def _get_selection_policy(qobj: dict) -> str:
    """Get selection policy for question"""
    pol = qobj.get("selection_policy")
    if pol:
        return pol
    return CONFIG["selection"]["default_policy"]


def _select_subparts_to_score(model_question: dict, aligned_map: dict[str, str]) -> list[str]:
    """
    Determine which subparts to score based on policy.
    
    Args:
        model_question: Model question structure
        aligned_map: Aligned student answers
    
    Returns:
        List of normalized subpart IDs to score
    """
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
    """
    Main evaluation function.
    
    Args:
        model_json_path: Path to model answers JSON
        student_json_path: Path to student answers JSON
        config: Configuration dictionary
    
    Returns:
        Evaluation report dictionary
    """
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

        if "total_marks" in mq:
            total_marks_q = float(mq["total_marks"])
        else:
            total_marks_q = sum(float(sp.get("marks", 0)) for sp in subparts)

        aligned = align_student_to_model(mq, student)
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
        sp_by_norm = {_norm_id(sp["id"]): sp for sp in subparts}

        for sp in subparts:
            q_result["subparts"][sp["id"]] = {
                "semantic_score": 0.0,
                "keyword_score": 0.0,
                "score": 0.0,
                "marks": 0.0
            }

        if not selected_ids:
            if aligned:
                q_result["notes"].append("No subpart selected by policy (first_n).")
            else:
                q_result["notes"].append("No answers found for this question.")
        
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
            human_id = sp.get("id")

            q_result["subparts"][human_id] = {
                "semantic_score": sem,
                "keyword_score": kw,
                "score": round(config["weights"]["semantic"] * sem +
                               config["weights"]["keyword"] * kw, 4),
                "marks": round(marks, 4)
            }

        q_result["final_score"] = round(awarded_sum, 4)
        report["by_question"][qno] = q_result
        report["total_awarded"] += awarded_sum
        report["total_max"] += total_marks_q

    report["total_awarded"] = round(report["total_awarded"], 4)
    report["total_max"] = round(report["total_max"], 1)
    report["percentage"] = round(
        (report["total_awarded"] / report["total_max"] * 100.0),
        2
    ) if report["total_max"] else 0.0

    return report


def save_evaluation(result: dict, output_path: str = "evaluation_report.json"):
    """
    Save evaluation report to JSON file.
    
    Args:
        result: Evaluation report dictionary
        output_path: Output file path
    """
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved evaluation report → {output_path}")


# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================

def print_summary(report: dict):
    """Print a summary of the evaluation results"""
    print("\n" + "="*70)
    print("EVALUATION SUMMARY")
    print("="*70)
    print(f"Total Awarded: {report['total_awarded']:.2f} / {report['total_max']:.1f}")
    print(f"Percentage: {report['percentage']:.2f}%")
    print("\nQuestion-wise Breakdown:")
    print("-"*70)
    
    for qno, qdata in report["by_question"].items():
        print(f"\nQuestion {qno}:")
        print(f"  Score: {qdata['final_score']:.2f} / {qdata['total_marks']:.1f}")
        print(f"  Subparts:")
        for sp_id, sp_data in qdata["subparts"].items():
            if sp_data["marks"] > 0:
                print(f"    {sp_id}: {sp_data['marks']:.2f} marks "
                      f"(sem: {sp_data['semantic_score']:.2f}, kw: {sp_data['keyword_score']:.2f})")
    
    print("\n" + "="*70)


def main():
    """Main entry point for command-line usage"""
    parser = argparse.ArgumentParser(
        description="Integrated Automated Answer Evaluation System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python integrated_evaluation.py --model data/model_answers.json --student data/student_answers.json
  python integrated_evaluation.py -m model.json -s student.json -o results.json
  python integrated_evaluation.py -m model.json -s student.json --no-summary
        """
    )
    
    parser.add_argument(
        "-m", "--model",
        required=True,
        help="Path to model answers JSON file"
    )
    
    parser.add_argument(
        "-s", "--student",
        required=True,
        help="Path to student answers JSON file"
    )
    
    parser.add_argument(
        "-o", "--output",
        default="evaluation_report.json",
        help="Output path for evaluation report (default: evaluation_report.json)"
    )
    
    parser.add_argument(
        "--no-summary",
        action="store_true",
        help="Don't print summary to console"
    )
    
    parser.add_argument(
        "--config",
        help="Path to custom config JSON file (optional)"
    )
    
    args = parser.parse_args()
    
    # Load custom config if provided
    config = CONFIG
    if args.config:
        with open(args.config, 'r') as f:
            custom_config = json.load(f)
            config.update(custom_config)
    
    print("🚀 Running Integrated Automated Evaluation Engine...")
    print(f"📖 Model answers: {args.model}")
    print(f"📝 Student answers: {args.student}")
    
    # Run evaluation
    result = evaluate_student_answers(
        model_json_path=args.model,
        student_json_path=args.student,
        config=config
    )
    
    # Save results
    save_evaluation(result, args.output)
    
    # Print summary unless disabled
    if not args.no_summary:
        print_summary(result)
    
    print(f"\n✅ Evaluation complete! Results saved to: {args.output}")


if __name__ == "__main__":
    main()
