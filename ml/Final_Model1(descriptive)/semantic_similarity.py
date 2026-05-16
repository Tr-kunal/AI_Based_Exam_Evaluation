from sentence_transformers import SentenceTransformer, util
from normalize_text import normalize_text
import threading

_model = None
_model_lock = threading.Lock()


def _get_model(config: dict) -> SentenceTransformer:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                sem_cfg = config.get("semantic", {})
                model_name = sem_cfg.get(
                    "model_name",
                    "sentence-transformers/all-MiniLM-L6-v2"
                )
                _model = SentenceTransformer(model_name)
    return _model


def semantic_similarity(text1: str, text2: str, config: dict) -> float:
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

    sim_raw = float(util.cos_sim(emb1, emb2).item())

    # Optionally rescale from [-1,1] to [0,1]
    sem_cfg = config.get("semantic", {})
    if sem_cfg.get("rescale_to_unit", True):
        sim = (sim_raw + 1.0) / 2.0
    else:
        sim = sim_raw

    # bound 0..1
    sim = max(0.0, min(1.0, sim))
    return round(sim, 4)
