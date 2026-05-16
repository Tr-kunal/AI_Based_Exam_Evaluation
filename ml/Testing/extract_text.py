import google.generativeai as genai
import os

genai.configure(api_key=os.getenv("GEMINI_API_KEY") or "AIzaSyB-yQoydu4NEFTPXxvdOPMmpITOV9M_3s4")

def extract_text_from_pdf(pdf_path: str):
    model = genai.GenerativeModel("gemini-2.5-flash")
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    prompt = """
            You are reading a descriptive exam question paper.

            Your task is to extract *all* questions and sub-questions, including any parts marked with:
            - Roman numerals: (i), (ii), (iii), (iv) ...
            - Alphabetic labels: (a), (b), (c) ...
            - Numeric parts: 1, 2, 3 under a question
            Treat every such subpart as a **separate question** with its own marks.

            Return STRICT JSON only in this format:

            {
            "questions": [
                {
                "q_no": "Q1(a)",
                "question": "<full question text>",
                "marks": <integer>
                },
                {
                "q_no": "Q1(b)",
                "question": "<full question text>",
                "marks": <integer>
                }
            ],
            "total_marks": <sum of all marks>
            }

            Rules:
            - Each (i), (ii), (a), (b), etc. must become its own JSON entry.
            - Maintain exact numbering (e.g., Q2(i), Q3(b)).
            - If a main question has no marks but its sub-parts do, only sum sub-parts.
            - If marks are not shown, estimate proportionally based on context.
            - Never merge multiple subparts into one question.
            - Include even incomplete or continued subparts from the next page.
            - Preserve equations, tables, and symbols as text.
            - Output **valid JSON only**, no markdown or explanations.
            """

    response = model.generate_content(
        [prompt, {"mime_type": "application/pdf", "data": pdf_bytes}]
    )

    return response.text
