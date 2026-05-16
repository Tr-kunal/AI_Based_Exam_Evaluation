from normalize_text import normalize_text
import yake
from difflib import SequenceMatcher

def _fuzzy_match(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()

def _keywords(text: str, k: int, minlen: int) -> list[str]:
    if not text:
        return []
    kw = yake.KeywordExtractor(top=k, n=1, dedupLim=0.9)
    candidates = [w for w, _ in kw.extract_keywords(text)]
    # keep only longer tokens & unique
    seen = set()
    out = []
    for c in candidates:
        c = c.strip()
        if len(c) >= minlen and c not in seen:
            seen.add(c)
            out.append(c)
    return out

def keyword_match_score(model_answer: str, student_answer: str, config: dict) -> float:
    if not model_answer or not student_answer:
        return 0.0

    # use raw model_answer to get keywords,
    # but normalize for matching
    kcfg = config["keywords"]
    keys = _keywords(model_answer, kcfg["top_k"], kcfg["minlen"])

    s_norm = normalize_text(
        student_answer,
        config["text_cleaning"]["remove_stopwords"],
        config["text_cleaning"]["use_synonyms"]
    )
    if not s_norm:
        return 0.0

    s_tokens = set(s_norm.split())
    hits = 0

    for key in keys:
        k_norm = normalize_text(
            key,
            config["text_cleaning"]["remove_stopwords"],
            config["text_cleaning"]["use_synonyms"]
        )
        # exact token hit
        if k_norm in s_tokens:
            hits += 1
        elif kcfg["use_fuzzy"]:
            # fuzzy hit against any token
            best = max((_fuzzy_match(k_norm, t) for t in s_tokens), default=0.0)
            if best >= kcfg["fuzzy_threshold"]:
                hits += 1

    if not keys:
        return 0.0
    score = hits / len(keys)
    return round(max(0.0, min(1.0, score)), 4)
