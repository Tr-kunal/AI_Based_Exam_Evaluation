import google.generativeai as genai
import os
import json

genai.configure(api_key=os.getenv("GEMINI_API_KEY") or "AIzaSyB-yQoydu4NEFTPXxvdOPMmpITOV9M_3s4")

def evaluate_answers(student_json, question_json):
    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt = f"""
    You are an examiner. Evaluate student answers compared to correct answers.
    Use question weightage from question_json.

    Return a JSON with this format:
    {{
        "Q1": {{"student_answer": "...", "teacher_answer": "...", "score": 4, "max_marks": 5, "feedback": "..."}},
        ...
        "total_score": 42,
        "max_total": 50
    }}
    """

    response = model.generate_content([
        prompt,
        f"Question Paper:\n{question_json}",
        f"Student Answers:\n{student_json}"
    ])

    return response.text
