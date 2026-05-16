import os
import json
import google.generativeai as genai

# ====================== CONFIGURATION ======================

API_KEY = os.getenv("GEMINI_API_KEY") or "YOUR_FLASH_2_5_API_KEY"
PDF_PATH = "sample/question_paper.pdf"
MODEL = "gemini-2.5-flash"

# ===========================================================

if not API_KEY or API_KEY == "YOUR_FLASH_2_5_API_KEY":
    print("❌ Please set your Gemini API key in the script or environment variable.")
    exit(1)

if not os.path.exists(PDF_PATH):
    print(f"❌ PDF file not found at path: {PDF_PATH}")
    exit(1)

genai.configure(api_key=API_KEY)


def extract_text_from_pdf_with_gemini(pdf_path: str) -> str:
    print("📤 Uploading PDF to Gemini for text extraction...")
    pdf_file = genai.upload_file(pdf_path, mime_type="application/pdf")

    model = genai.GenerativeModel(MODEL)
    prompt = (
        "You are a precise document parser. Extract all readable text from this question paper. "
        "Preserve question numbering, subparts (a,b,c,i,ii, etc.), and marks. "
        "Do not summarize, just return clean structured text."
    )

    response = model.generate_content([prompt, pdf_file])
    return response.text


def generate_model_answers(text: str) -> dict:
    """
    Extracts questions with numbers, model answers, marks and attempt rules.
    """
    print("🤖 Generating model answers for each question...")

    model = genai.GenerativeModel(MODEL)

    prompt = """
You are extracting structured question data from an exam PDF.

Your task:
1️⃣ Identify every main question (Q1, Q2, Q3…)
2️⃣ Identify subparts (i, ii, iii / a, b, c / A, B etc.)
3️⃣ For each question or subpart:
    - Extract EXACT question text
    - Generate a natural, correct, human-written “Model Answer”
    - Extract the marks written for that question/subpart
4️⃣ Detect internal choice rules (like "Attempt any 1/2/4")
    - If only one must be attempted → return:
      "attempt_required": 1, "selection_policy": "first_n"
    - If all must be done → return:
      "attempt_required": "all", "selection_policy": "none"

Output MUST be a VALID JSON with this exact structure:

{
  "questions": [
    {
      "question_number": "Q#",
      "total_marks": #,
      "attempt_required": "all" or <number>,
      "selection_policy": "none" or "first_n",
      "subparts": [
        {
          "id": "<subpart>",
          "question": "<text>",
          "model_answer": "<text>",
          "marks": <number>
        }
      ]
    }
  ]
}

Rules:
✅ Remove page numbers, headers, footers
✅ Ignore Hindi or duplicate translations
✅ Ignore “for visually impaired” optional alternatives
✅ Do NOT hallucinate marks – use only values present in PDF
✅ Do NOT include anything outside JSON
✅ Grammar in answers must be high quality

Here is the extracted question paper text:
{text_input}
"""

    final_prompt = prompt.replace("{text_input}", text)

    response = model.generate_content(final_prompt)
    cleaned = response.text.strip()

    # Try to load JSON directly
    try:
        return json.loads(cleaned)
    except:
        # Try to extract JSON array substring
        start = cleaned.find('{')
        end = cleaned.rfind('}')
        return json.loads(cleaned[start:end+1])


def save_to_json(data: dict, output_path="model_answers.json"):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ Model answers saved to {output_path}")


# ====================== MAIN EXECUTION ======================

if __name__ == "__main__":
    print("📄 Extracting questions from:", PDF_PATH)
    extracted_text = extract_text_from_pdf_with_gemini(PDF_PATH)
    qna_data = generate_model_answers(extracted_text)
    save_to_json(qna_data)
