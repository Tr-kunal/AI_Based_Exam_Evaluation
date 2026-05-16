# Prompts are crafted to force valid JSON outputs with strict schema.

QUESTION_EXTRACT_PROMPT = """
You are an OCR + text extraction expert.
Read the provided question paper images carefully.

Return STRICT JSON in this format only:

{
  "questions": [
    {"q_no": "Q1", "question": "<text>", "marks": <int>},
    {"q_no": "Q2", "question": "<text>", "marks": <int>}
  ]
}

Rules:
- Always include all questions in order.
- Extract marks if written like "(5 marks)"; else assume 5.
- No explanations, no markdown, just raw JSON.
"""

ANSWER_EXTRACT_PROMPT = """
You are reading a student's handwritten answer sheet.
Extract the text answer for each question clearly and preserve order.

Return STRICT JSON in this format only:
{
  "answers": [
    {"q_no": "Q1", "answer": "<cleaned text>"},
    {"q_no": "Q2", "answer": "<cleaned text>"}
  ]
}

Rules:
- Each 'q_no' must match the numbering from the answer sheet.
- No markdown, no commentary, only raw JSON.
"""

MODEL_ANSWER_PROMPT = """
You are a professional subject teacher.
Generate concise, high-quality model answers for the following questions.

Return STRICT JSON list only:
[
  {"q_no": "Q1", "model_answer": "<text>"},
  {"q_no": "Q2", "model_answer": "<text>"}
]

Do not include anything else besides valid JSON.
"""

EVALUATION_PROMPT_TEMPLATE = """
You are an exam evaluator.

Compare the student's answer to the model answer for the given question.

Return STRICT JSON only with this schema:
{
  "q_no": "%s",
  "relevance": <float between 0 and 1>,
  "coverage": <float between 0 and 1>,
  "clarity": <float between 0 and 1>,
  "overall_score": <float between 0 and 1>,
  "marks_awarded": <float>,
  "feedback": "<one short sentence>"
}

Details:
Question: %s
Model Answer: %s
Student Answer: %s
Maximum Marks: %s

Compute 'marks_awarded' = overall_score × marks.
Output only valid JSON, no explanations.
"""
