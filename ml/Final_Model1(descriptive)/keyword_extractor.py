from normalize_text import normalize_text
import yake
from difflib import SequenceMatcher


def _fuzzy_match(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _keywords(text: str, k: int, minlen: int) -> list[str]:
    """
    Extract up to k keyword candidates from text using YAKE (unigrams).
    Filters:
      - length >= minlen
      - unique
    """
    if not text:
        return []

    # Slightly over-generate then filter down
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
    Simple keyword overlap score based on YAKE keywords from model_answer.
    Returns a value in [0,1].
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

        # exact token hit
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
