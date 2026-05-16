from sentence_transformers import SentenceTransformer, util
from normalize_text import normalize_text

# Load once
_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

def semantic_similarity(text1: str, text2: str, config: dict) -> float:
    if not text1 or not text2:
        return 0.0

    t1 = normalize_text(
        text1,
        config["text_cleaning"]["remove_stopwords"],
        config["text_cleaning"]["use_synonyms"]
    )
    t2 = normalize_text(
        text2,
        config["text_cleaning"]["remove_stopwords"],
        config["text_cleaning"]["use_synonyms"]
    )

    if not t1 or not t2:
        return 0.0

    emb1 = _model.encode(t1, convert_to_tensor=True)
    emb2 = _model.encode(t2, convert_to_tensor=True)
    sim = util.pytorch_cos_sim(emb1, emb2).item()

    # bound 0..1
    sim = max(0.0, min(1.0, float(sim)))
    return round(sim, 4)
