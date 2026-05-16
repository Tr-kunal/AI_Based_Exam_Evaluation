CONFIG = {
    # scoring weights
    "weights": {
        "semantic": 0.6,
        "keyword": 0.4
    },

    # thresholds
    "thresholds": {
        "min_partial_score": 0.25,          # below this → 0 marks for subjective
        "mcq_min_correct_score": 0.75       # semantic ≥ this → full marks for MCQ
    },

    # text cleaning pipeline
    "text_cleaning": {
        "lowercase": True,
        "strip_punct": True,
        "collapse_space": True,
        "remove_stopwords": True,
        "use_synonyms": False               # kept off (no external corpora needed)
    },

    # keyword extraction & matching
    "keywords": {
        "top_k": 15,
        "minlen": 3,
        "use_fuzzy": True,                  # allow close matches
        "fuzzy_threshold": 0.88             # 0..1; >= → counts as a hit
    },

    # selection policy defaults (used when not present in model JSON)
    "selection": {
        "default_policy": "none",           # "none" | "first_n" | "best_n"
        "default_attempt_required": "all"   # "all" | <int n>
    }
}
