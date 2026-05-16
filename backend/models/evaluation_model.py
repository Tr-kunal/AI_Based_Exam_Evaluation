# A simple, replaceable evaluation stub.
# Currently it computes similarity between student answer text and answer-key text
# using difflib.SequenceMatcher and returns score, matched_ratio and short feedback.


from difflib import SequenceMatcher


def evaluate_answer_text(student_text: str, answer_key_text: str) -> dict:
    #  """Return a dict with score (0-100), ratio and feedback."""
    if not student_text:
        return {'score': 0, 'ratio': 0.0, 'feedback': 'No answer provided.'}


    a = student_text.lower().strip()
    b = answer_key_text.lower().strip()


    # naive similarity
    ratio = SequenceMatcher(None, a, b).ratio()
    score = int(round(ratio * 100))


    # simple feedback rules
    if ratio > 0.85:
        feedback = 'Excellent match to the answer key.'
    elif ratio > 0.6:
        feedback = 'Good — several key points present.'
    elif ratio > 0.35:
        feedback = 'Partial answer — some key points missing.'
    else:
        feedback = 'Answer does not match key. Provide more details.'


    return {'score': score, 'ratio': ratio, 'feedback': feedback}


    # You can replace evaluate_answer_text with a pipeline that calls OCR -> NLP model -> rubric.