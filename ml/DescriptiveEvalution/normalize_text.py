import re
from unidecode import unidecode

_STOPWORDS = {
    "a","an","the","and","or","but","if","so","to","of","in","on","at","by","for",
    "with","as","is","are","was","were","be","been","being","this","that","these",
    "those","it","its","from","into","about","over","after","before","not","no",
    "do","does","did","doing","have","has","had","having","than","then","there",
    "here","such","very","can","could","should","would","may","might","will","shall"
}

_PUNCT_RX = re.compile(r"[^\w\s]_", re.UNICODE)

def _strip_punct(text: str) -> str:
    return re.sub(r"[^\w\s]", " ", text)

def normalize_text(
    text: str,
    remove_stopwords: bool = True,
    use_synonyms: bool = False
) -> str:
    """
    Safe string normalizer. Only pass STR here.
    (Do NOT feed dict/list — caller must extract strings first.)
    """
    if not isinstance(text, str):
        return ""

    # transliterate
    text = unidecode(text)

    # lowercase
    text = text.lower()

    # remove punctuation
    text = _strip_punct(text)

    # collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    if remove_stopwords:
        tokens = [t for t in text.split() if t not in _STOPWORDS]
        text = " ".join(tokens)

    # synonyms expansion intentionally disabled (no external corpora).
    return text
