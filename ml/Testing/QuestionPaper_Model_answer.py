import os
import io
import json
from pdf2image import convert_from_path
from PIL import Image
import numpy as np
import cv2
import google.generativeai as genai

# ========== CONFIGURATION ==========
# Get the API key
api_key = os.environ.get("GEMINI_API_KEY")

# If not found, let user enter manually
if not api_key:
    print("⚠️ GEMINI_API_KEY not found in environment.")
    api_key = input("Enter your Gemini API Key: ").strip()

# Now configure Gemini
genai.configure(api_key=api_key)


# ========== IMAGE PREPROCESSING ==========
def preprocess_image(img: Image.Image) -> Image.Image:
    """Enhance scanned question paper for better OCR and layout recognition."""
    gray = np.array(img.convert("L"))
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blur, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    cleaned = cv2.fastNlMeansDenoising(thresh, None, 30, 7, 21)
    return Image.fromarray(cleaned)

def pdf_to_images(pdf_path: str):
    """Convert PDF to images for multi-page documents."""
    return convert_from_path(pdf_path, dpi=300)

# ========== GEMINI STAGE 1: EXTRACT QUESTIONS ==========
def extract_questions(pdf_path: str):
    """
    Extract question numbers, text, and marks from the question paper.
    Returns a list of dicts without model answers yet.
    """
    pages = pdf_to_images(pdf_path)
    extracted_data = []

    for idx, page in enumerate(pages, start=1):
        cleaned = preprocess_image(page)

        buf = io.BytesIO()
        cleaned.save(buf, format="JPEG")
        img_bytes = buf.getvalue()

        prompt = (
            "You are an AI examiner assistant. Extract all questions from this page of a question paper. "
            "For each question, include:\n"
            "- 'question_no': the label (e.g., Q1, Q1(a), Q2(i))\n"
            "- 'question_text': the full text of the question\n"
            "- 'marks': the marks allotted (if shown, otherwise null)\n"
            "Output a JSON array only, no commentary. "
            "If questions span across pages, skip incomplete ones."
        )

        response = model.generate_content(
            {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt},
                            {"inlineData": {"mimeType": "image/jpeg", "data": img_bytes.hex()}}
                        ]
                    }
                ]
            },
            generation_config=genai.types.GenerationConfig(
                temperature=0.0,
                top_p=0.9,
                thinking_config=genai.types.ThinkingConfig(thinking_budget=1024)
            ),
        )

        try:
            page_data = json.loads(response.text)
        except json.JSONDecodeError:
            raise ValueError(f"Failed to parse JSON on page {idx}: {response.text}")

        extracted_data.extend(page_data)

    return extracted_data

# ========== GEMINI STAGE 2: GENERATE MODEL ANSWERS ==========
def generate_model_answers(question_data):
    """
    For each extracted question, ask Gemini to generate a model academic-style answer.
    Adds 'model_answer' key to each question.
    """
    final_data = []
    for q in question_data:
        question_text = q["question_text"]
        marks = q.get("marks", None)

        gen_prompt = (
            f"You are a subject matter expert and academic examiner.\n"
            f"Generate a concise, high-quality model answer for the following question.\n\n"
            f"Question: {question_text}\n"
            f"Marks allotted: {marks if marks else 'Not specified'}\n\n"
            "Guidelines:\n"
            "- Write in clear, formal, human academic tone.\n"
            "- Ensure factual correctness and relevance.\n"
            "- The answer length should be proportional to the marks.\n"
            "- Do NOT restate the question.\n"
            "- Output only the answer text, no JSON or markdown."
        )

        resp = model.generate_content(
            gen_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                top_p=0.9,
                thinking_config=genai.types.ThinkingConfig(thinking_budget=1024)
            ),
        )

        answer_text = resp.text.strip()
        q["model_answer"] = answer_text
        final_data.append(q)

    return final_data

# ========== MAIN PIPELINE ==========
if __name__ == "__main__":
    QUESTION_PDF = "sample\question_paper.pdf"
    print("📘 Extracting questions...")
    questions = extract_questions(QUESTION_PDF)
    print(f"✅ Found {len(questions)} questions")

    print("🧠 Generating model answers...")
    full_data = generate_model_answers(questions)

    OUTPUT_FILE = "question_paper_with_model_answers.json"
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(full_data, f, ensure_ascii=False, indent=2)

    print(f"✅ All done! JSON saved as {OUTPUT_FILE}")
