"""
Integrated PDF Extraction System
=================================

Extracts student answers and question papers from PDFs using Groq AI API.

Features:
- Extract student answers from PDF answer sheets
- Extract questions and generate model answers from question papers
- Unified CLI interface for both operations
- Support for Groq API (Llama / Mixtral models)

Usage:
    python integrated_extraction.py --mode answers --pdf sample/student_answers.pdf --output student_answers.json
    python integrated_extraction.py --mode questions --pdf sample/question_paper.pdf --output model_answers.json

Author: Automated Extraction System
Version: 2.0 (Groq)
"""

import os
import sys
import json
import base64
import argparse
import time

from google import genai


# ============================================================================
# PROMPTS
# ============================================================================

ANSWER_EXTRACTION_PROMPT = """
You are an intelligent exam evaluator. Your task is to accurately extract answers from a student's handwritten or scanned answer sheet.

Follow these instructions carefully:

1. Identify every main question (e.g., Q1, Q2, Q3, etc.).
2. For each question, extract all its subparts such as (a), (b), (c), and (i), (ii), (iii), (iv), etc.
3. If the student has written answers in a different or mixed order, rearrange them in **the correct numerical/alphabetical order** (Q1 -> Q2 -> Q3; within Q1: a -> b -> c; within subparts: i -> ii -> iii -> iv).
4. Extract only the student's handwritten **answer text** -- ignore any question text, page numbers, or headings.
5. If a question has no subparts, record it as a single text string.
6. If a subpart exists but is blank or unreadable, mark it as `"unreadable"`.
7. Preserve nested structure (e.g., Q1(c)(i)).
8. Maintain formatting (newlines, bullets, equations) as they appear.

Return the final result **only** as a clean JSON object, with no extra text or explanations.

Important:
- Always arrange questions and subparts in correct logical order even if written out of sequence in the PDF.
- Do not paraphrase, summarize, or modify the text -- extract it exactly as written.
- Output must be valid JSON only.
"""

QUESTION_EXTRACTION_PROMPT = """
You are extracting structured question data from an exam paper.

Your task:
1 Identify every main question (Q1, Q2, Q3...)
2 Identify subparts (i, ii, iii / a, b, c / A, B etc.)
3 For each question or subpart:
    - Extract EXACT question text
    - Generate a natural, correct, human-written "Model Answer"
    - Extract the marks written for that question/subpart
4 Detect internal choice rules (like "Attempt any 1/2/4")
    - If only one must be attempted -> return:
      "attempt_required": 1, "selection_policy": "first_n"
    - If all must be done -> return:
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
[OK] Remove page numbers, headers, footers
[OK] Ignore Hindi or duplicate translations
[OK] Ignore "for visually impaired" optional alternatives
[OK] Do NOT hallucinate marks  use only values present in the text
[OK] Do NOT include anything outside JSON
[OK] Grammar in answers must be high quality
"""


# ============================================================================
# GEMINI CLIENT HELPERS
# ============================================================================

def _gemini_chat(api_key: str, system_prompt: str, user_content: str,
               model: str = "gemini-2.5-flash", retries: int = 3) -> str:
    """
    Send a chat completion request to Gemini with retry logic.
    """
    client = genai.Client(api_key=api_key)
    # Gemini uses generation_config for structured output hints.
    # However, for simple JSON extraction, we can just append to the prompt.
    prompt = f"{system_prompt}\n\nPlease output your response in JSON format.\n\nUser Input:\n{user_content}"
    
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config={"temperature": 0.2}
            )
            return response.text
        except Exception as e:
            print(f"[!] Gemini API error (attempt {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(5 * (attempt + 1))
            else:
                raise

    raise Exception("All Gemini API retries exhausted")

# ============================================================================
# PDF TEXT EXTRACTION (using Groq vision or fallback to text)
# ============================================================================

def _read_pdf_text_fallback(pdf_path: str) -> str:
    """
    Simple PDF text extraction fallback.
    Tries PyPDF2/pypdf if available, otherwise returns a message.
    """
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        text_parts = []
        for page in reader.pages:
            text_parts.append(page.extract_text() or "")
        return "\n".join(text_parts)
    except ImportError:
        pass

    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(pdf_path)
        text_parts = []
        for page in reader.pages:
            text_parts.append(page.extract_text() or "")
        return "\n".join(text_parts)
    except ImportError:
        pass

    # If no PDF library available, encode and send as base64 to vision model
    return ""


def extract_text_from_pdf(pdf_path: str, api_key: str, model: str = "llama-3.3-70b-versatile") -> str:
    """
    Extract text from a PDF file.

    Uses local PDF parsing first. If that yields no text (e.g. scanned PDF),
    falls back to Groq vision model for OCR using PyMuPDF to extract images.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    # Try local extraction first
    text = _read_pdf_text_fallback(pdf_path)
    if text and len(text.strip()) > 50:
        print("[DOC] Text extracted locally from PDF")
        return text

    # Fallback: OCR using Google Gemini (Groq Vision is decommissioned)
    print("[UP] Scanned PDF detected. Trying Gemini OCR for handwriting extraction...")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    
    if not gemini_key:
        print("[X] GEMINI_API_KEY not found. Please set it in .env for handwriting OCR.")
        return ""
        
    ocr_text = []
    try:
        from google import genai
        import fitz
        import PIL.Image
        import io
        
        client = genai.Client(api_key=gemini_key)
        
        doc = fitz.open(pdf_path)
        for page_num in range(min(len(doc), 10)):  # process up to 10 pages
            page = doc.load_page(page_num)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img_data = pix.tobytes("jpeg")
            img = PIL.Image.open(io.BytesIO(img_data))
            
            prompt = "Extract all handwriting and text from this page exactly as it appears. Preserve question numbers and line breaks."
            
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[img, prompt]
            )
            if response.text:
                ocr_text.append(response.text)
            
        doc.close()
        return "\n\n".join(ocr_text)
    except Exception as e:
        print(f"[X] Gemini Vision OCR Failed: {e}")
        raise Exception(f"Gemini OCR Failed: {e}")


# ============================================================================
# ANSWER SHEET EXTRACTION
# ============================================================================

def extract_answers_from_pdf(pdf_path: str, api_key: str) -> dict:
    """
    Extract student answers from PDF using Gemini API.

    Args:
        pdf_path: Path to the student answer sheet PDF
        api_key: Gemini API key

    Returns:
        Dictionary containing extracted answers
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"File not found at {pdf_path}")

    print(f"[*] Using Gemini API for answer extraction")

    # Extract text from PDF first
    pdf_text = extract_text_from_pdf(pdf_path, api_key)

    if not pdf_text or len(pdf_text.strip()) < 10:
        raise Exception("Could not extract readable text from the PDF")

    print("[UP] Sending extracted text to Gemini for answer structuring...")

    user_msg = f"Here is the text extracted from a student's answer sheet:\n\n{pdf_text}"

    response_text = _gemini_chat(api_key, ANSWER_EXTRACTION_PROMPT, user_msg)

    try:
        extracted_json = json.loads(response_text)
        return extracted_json
    except json.JSONDecodeError as e:
        print(f"[!] Error parsing JSON response: {e}")
        # Try to find JSON substring
        start = response_text.find('{')
        end = response_text.rfind('}')
        if start >= 0 and end > start:
            return json.loads(response_text[start:end + 1])
        raise Exception(f"Failed to parse extraction response as JSON: {e}")


# ============================================================================
# QUESTION PAPER EXTRACTION
# ============================================================================

def generate_model_answers(text: str, api_key: str, model: str = "gemini-2.5-flash") -> dict:
    """
    Generate model answers for extracted question text using Gemini.

    Args:
        text: Extracted question paper text
        api_key: Gemini API key
        model: Gemini model name

    Returns:
        Dictionary containing questions with model answers
    """
    print("[AI] Generating model answers for each question...")

    user_msg = f"Here is the extracted question paper text:\n\n{text}"
    response_text = _gemini_chat(api_key, QUESTION_EXTRACTION_PROMPT, user_msg, model)

    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        start = response_text.find('{')
        end = response_text.rfind('}')
        if start >= 0 and end > start:
            return json.loads(response_text[start:end + 1])
        raise


def extract_questions_from_pdf(pdf_path: str, api_key: str, model: str = "gemini-2.5-flash") -> dict:
    """
    Complete pipeline to extract questions and generate model answers.

    Args:
        pdf_path: Path to the question paper PDF
        api_key: Gemini API key
        model: Gemini model name

    Returns:
        Structured JSON with questions and model answers
    """
    print(f"[DOC] Extracting questions from: {pdf_path}")
    print(f"[*] Using Gemini model: {model}")

    extracted_text = extract_text_from_pdf(pdf_path, api_key, model)
    qna_data = generate_model_answers(extracted_text, api_key, model)
    return qna_data


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def save_to_json(data: dict, output_path: str):
    """Save data to JSON file."""
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[OK] Data saved to {output_path}")


def get_api_key() -> str:
    """Get Gemini API key from environment variable."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[X] ERROR: GEMINI_API_KEY is not set in environment variables.")
        print("-> Set it before running:")
        print("   Windows: set GEMINI_API_KEY=YOUR_API_KEY_HERE")
        print("   Linux/Mac: export GEMINI_API_KEY=YOUR_API_KEY_HERE")
        raise ValueError("GEMINI_API_KEY is not set in environment variables.")
    return api_key


# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================

def main():
    """Main entry point for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Integrated PDF Extraction System - Extract answers and questions from PDFs using Groq AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python integrated_extraction.py --mode answers --pdf sample/student_answers.pdf --output student_answers.json
  python integrated_extraction.py --mode questions --pdf sample/question_paper.pdf --output model_answers.json
        """
    )

    parser.add_argument("-m", "--mode", required=True, choices=["answers", "questions"],
                        help="Extraction mode: 'answers' or 'questions'")
    parser.add_argument("-p", "--pdf", required=True, help="Path to the PDF file")
    parser.add_argument("-o", "--output", required=True, help="Output JSON file path")
    parser.add_argument("--model", default="llama-3.3-70b-versatile",
                        help="Groq model to use (default: llama-3.3-70b-versatile)")

    args = parser.parse_args()
    api_key = get_api_key()

    if not os.path.exists(args.pdf):
        print(f"[X] ERROR: PDF file not found at {args.pdf}")
        sys.exit(1)

    print("=" * 70)
    print("INTEGRATED PDF EXTRACTION SYSTEM (Groq AI)")
    print("=" * 70)
    print(f"Mode: {args.mode.upper()}")
    print(f"Input PDF: {args.pdf}")
    print(f"Output: {args.output}")
    print(f"Model: {args.model}")
    print("=" * 70)

    if args.mode == "answers":
        result = extract_answers_from_pdf(args.pdf, api_key)
        if result:
            save_to_json(result, args.output)
            print("\n[OK] Student answers successfully extracted!")
        else:
            print("\n[X] Failed to extract student answers.")
            sys.exit(1)
    elif args.mode == "questions":
        result = extract_questions_from_pdf(args.pdf, api_key, args.model)
        if result:
            save_to_json(result, args.output)
            print("\n[OK] Questions and model answers successfully extracted!")
        else:
            print("\n[X] Failed to extract questions.")
            sys.exit(1)

    print(f"\n[OK] Extraction complete! Results saved to: {args.output}")


if __name__ == "__main__":
    main()
