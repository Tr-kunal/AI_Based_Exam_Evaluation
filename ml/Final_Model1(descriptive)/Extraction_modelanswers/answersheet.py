import requests
import json
import base64
import os
import sys

# === CONFIGURATION ===
API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    print("❌ ERROR: GEMINI_API_KEY is not set in environment variables.")
    print("👉 Run this command before executing the script:")
    print("   set GEMINI_API_KEY=YOUR_API_KEY_HERE")
    sys.exit(1)

PDF_PATH = r"sample\student_answers.pdf"
#Gemini 2.5 Flash endpoint
GEMINI_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"


# === PROMPT FOR STRUCTURED EXTRACTION ===
prompt_text = """
You are an intelligent exam evaluator. Your task is to accurately extract answers from a student's handwritten or scanned PDF answer sheet.

Follow these instructions carefully:

1. Identify every main question (e.g., Q1, Q2, Q3, etc.).
2. For each question, extract all its subparts such as (a), (b), (c), and (i), (ii), (iii), (iv), etc.
3. If the student has written answers in a different or mixed order, rearrange them in **the correct numerical/alphabetical order** (Q1 → Q2 → Q3; within Q1: a → b → c; within subparts: i → ii → iii → iv).
4. Extract only the student’s handwritten **answer text** — ignore any question text, page numbers, or headings.
5. If a question has no subparts, record it as a single text string.
6. If a subpart exists but is blank or unreadable, mark it as `"unreadable"`.
7. Preserve nested structure (e.g., Q1(c)(i)).
8. Maintain formatting (newlines, bullets, equations) as they appear.

Return the final result **only** as a clean JSON object, with no extra text or explanations.

Important:
- Always arrange questions and subparts in correct logical order even if written out of sequence in the PDF.
- Do not paraphrase, summarize, or modify the text — extract it exactly as written.
- Output must be valid JSON only.
"""

# === FUNCTION TO CALL GEMINI API ===
def extract_answers_from_pdf(pdf_path):
    # Check if file exists
    if not os.path.exists(pdf_path):
        print(f"❌ ERROR: File not found at {pdf_path}")
        sys.exit(1)

    # Read and encode PDF file
    with open(pdf_path, "rb") as f:
        pdf_data = f.read()
    encoded_pdf = base64.b64encode(pdf_data).decode("utf-8")

    # Prepare payload
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt_text},
                    {
                        "inline_data": {
                            "mime_type": "application/pdf",
                            "data": encoded_pdf
                        }
                    }
                ]
            }
        ],
        "generationConfig": {
            "response_mime_type": "application/json"  # ensures clean JSON output
        }
    }

    headers = {"Content-Type": "application/json"}

    print("📤 Sending request to Gemini API...")
    response = requests.post(GEMINI_ENDPOINT, headers=headers, json=payload)

    # Handle HTTP errors
    if response.status_code != 200:
        print(f"❌ API request failed ({response.status_code}): {response.text}")
        sys.exit(1)

    result = response.json()

    try:
        # Safely extract text from Gemini response
        text_output = (
            result.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )

        # Convert to JSON object
        extracted_json = json.loads(text_output)
        return extracted_json

    except Exception as e:
        print("⚠️ Error parsing JSON response:", e)
        print("Raw Gemini response:\n", json.dumps(result, indent=2))
        return None


# === MAIN EXECUTION ===
if __name__ == "__main__":
    answers = extract_answers_from_pdf(PDF_PATH)
    if answers:
        with open("structured_answers.json", "w", encoding="utf-8") as f:
            json.dump(answers, f, indent=2, ensure_ascii=False)
        print("\n✅ Answers successfully extracted and saved to structured_answers.json")
    else:
        print("\n❌ Failed to extract answers.")
