CONFIG = {
    # --------- WEIGHTS (Balanced style) ----------
    "weights": {
        "semantic": 0.8,   # sentence-transformer similarity
        "keyword": 0.2     # YAKE-based keyword match
    },

    # --------- THRESHOLDS & PENALTIES ------------
    "thresholds": {
        # For subjective questions:
        # if combined score < this → 0 marks
        # (Balanced: a bit forgiving but still strict)
        "min_partial_score": 0.20,

        # For MCQ: semantic similarity (0..1) required to get full marks
        "mcq_min_correct_score": 0.60,

        # Length handling: how short can a student answer be
        # compared to model answer before we start penalizing?
        # e.g., 0.3 → if student answer has <30% tokens of model, downscale
        "min_length_ratio": 0.15,

        # Strength of length penalty (1.0 = linear, >1 stronger penalty)
        "length_penalty_strength": 0.4
    },

    # --------- SEMANTIC SIMILARITY SETTINGS -------
    "semantic": {
        # model used:
        # "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        "model_name": "sentence-transformers/all-MiniLM-L6-v2",

        # Rescale cosine (-1..1) → (0..1) using (x+1)/2
        "rescale_to_unit": True
    },

    # --------- TEXT CLEANING PIPELINE -------------
    "text_cleaning": {
        "lowercase": True,
        "strip_punct": True,
        "collapse_space": True,

        "remove_stopwords": True,
        "use_synonyms": False,          # kept off (no external corpora)

        # EXTRA knobs (default: off, for safety)
        "apply_stemming": False,        # NLTK PorterStemmer
        "apply_lemmatization": False,   # NLTK WordNetLemmatizer
        "normalize_numbers": False      # turn all digit sequences into a token like "<num>"
    },

    # --------- KEYWORD EXTRACTION & MATCHING -----
    "keywords": {
        "top_k": 15,            # max number of candidate keywords from model answer
        "minlen": 3,            # ignore very short tokens
        "use_fuzzy": True,      # allow close matches (SequenceMatcher)
        "fuzzy_threshold": 0.88 # 0..1; >= counts as fuzzy hit
    },

    # --------- SELECTION POLICY (choice questions) -
    "selection": {
        # "none" = score all subparts
        # "first_n" = score first N answered subparts (internal choice)
        "default_policy": "none",

        # "all" = all subparts are required
        # int N  = only N subparts are required/attempted
        "default_attempt_required": "all"
    }
}
