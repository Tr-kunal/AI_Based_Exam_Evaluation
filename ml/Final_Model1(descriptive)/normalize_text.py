import re
from unidecode import unidecode

try:
    from nltk.stem import PorterStemmer, WordNetLemmatizer
    _STEMMER = PorterStemmer()
    _LEMMATIZER = WordNetLemmatizer()
except Exception:
    # If NLTK data is not available, we just skip stemming/lemmatization
    _STEMMER = None
    _LEMMATIZER = None

_STOPWORDS = {
    "a","an","the","and","or","but","if","so","to","of","in","on","at","by","for",
    "with","as","is","are","was","were","be","been","being","this","that","these",
    "those","it","its","from","into","about","over","after","before","not","no",
    "do","does","did","doing","have","has","had","having","than","then","there",
    "here","such","very","can","could","should","would","may","might","will","shall"
}

_NUM_RX = re.compile(r"\d+")


def _strip_punct(text: str) -> str:
    # Replace any non-word / non-space character with a space
    return re.sub(r"[^\w\s]", " ", text)


def normalize_text(
    text: str,
    remove_stopwords: bool = True,
    use_synonyms: bool = False,          # currently unused, reserved for future
    apply_stemming: bool = False,
    apply_lemmatization: bool = False,
    normalize_numbers: bool = False
) -> str:
    """
    Safe string normalizer.
    Only pass STR here. Do NOT feed dict/list — caller must extract strings first.
    """
    if not isinstance(text, str):
        return ""

    # transliterate
    text = unidecode(text)

    # lowercase
    text = text.lower()

    # optionally normalize numbers
    if normalize_numbers:
        text = _NUM_RX.sub(" <num> ", text)

    # remove punctuation
    text = _strip_punct(text)

    # collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    tokens = text.split()

    if remove_stopwords:
        tokens = [t for t in tokens if t not in _STOPWORDS]

    # Apply stemming / lemmatization if enabled and tools available
    if apply_stemming and _STEMMER is not None:
        tokens = [_STEMMER.stem(t) for t in tokens]

    if apply_lemmatization and _LEMMATIZER is not None:
        # This is very basic; no POS tagging
        tokens = [_LEMMATIZER.lemmatize(t) for t in tokens]

    text = " ".join(tokens)

    # synonyms expansion intentionally disabled (no external corpora)
    return text
