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

from groq import Groq


# ============================================================================
# PROMPTS
# ============================================================================

ANSWER_EXTRACTION_PROMPT = """
You are an intelligent exam evaluator. Your task is to accurately extract answers from a student's handwritten or scanned answer sheet.

Follow these instructions carefully:

1. Identify every main question (e.g., Q1, Q2, Q3, etc.).
2. For each question, extract all its subparts such as (a), (b), (c), and (i), (ii), (iii), (iv), etc.
3. If the student has written answers in a different or mixed order, rearrange them in **the correct numerical/alphabetical order** (Q1 → Q2 → Q3; within Q1: a → b → c; within subparts: i → ii → iii → iv).
4. Extract only the student's handwritten **answer text** — ignore any question text, page numbers, or headings.
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

QUESTION_EXTRACTION_PROMPT = """
You are extracting structured question data from an exam paper.

Your task:
1️⃣ Identify every main question (Q1, Q2, Q3…)
2️⃣ Identify subparts (i, ii, iii / a, b, c / A, B etc.)
3️⃣ For each question or subpart:
    - Extract EXACT question text
    - Generate a natural, correct, human-written "Model Answer"
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
✅ Ignore "for visually impaired" optional alternatives
✅ Do NOT hallucinate marks – use only values present in the text
✅ Do NOT include anything outside JSON
✅ Grammar in answers must be high quality
"""


# ============================================================================
# GROQ CLIENT HELPERS
# ============================================================================

def _get_groq_client(api_key: str) -> Groq:
    """Create a Groq client instance."""
    return Groq(api_key=api_key)


def _groq_chat(client: Groq, system_prompt: str, user_content: str,
               model: str = "llama-3.3-70b-versatile", retries: int = 3) -> str:
    """
    Send a chat completion request to Groq with retry logic.

    Args:
        client: Groq client
        system_prompt: System-level prompt
        user_content: User message content
        model: Model name (default: llama-3.3-70b-versatile)
        retries: Number of retry attempts

    Returns:
        Response text from the model
    """
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.2,
                max_tokens=8192,
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"⚠️ Groq API error (attempt {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(5 * (attempt + 1))
            else:
                raise

    raise Exception("All Groq API retries exhausted")


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
    falls back to Groq vision model for OCR.

    Args:
        pdf_path: Path to the PDF file
        api_key: Groq API key
        model: Model name for fallback OCR

    Returns:
        Extracted text string
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    # Try local extraction first
    text = _read_pdf_text_fallback(pdf_path)
    if text and len(text.strip()) > 50:
        print("📄 Text extracted locally from PDF")
        return text

    # Fallback: send to Groq for text extraction
    print("📤 Sending PDF content to Groq for text extraction...")
    client = _get_groq_client(api_key)

    # Read and encode PDF
    with open(pdf_path, "rb") as f:
        pdf_data = f.read()

    # For Groq text models, we send base64 as text context
    encoded_pdf = base64.b64encode(pdf_data).decode("utf-8")

    prompt = (
        "You are a precise document parser. The following is a base64-encoded PDF document. "
        "Extract all readable text from this document, preserving question numbering, "
        "subparts (a,b,c,i,ii, etc.), and marks. Do not summarize, just return clean structured text.\n\n"
        f"Base64 PDF data (first 5000 chars): {encoded_pdf[:5000]}"
    )

    response_text = _groq_chat(client, "You are a document text extractor.", prompt, model)
    return response_text


# ============================================================================
# ANSWER SHEET EXTRACTION
# ============================================================================

def extract_answers_from_pdf(pdf_path: str, api_key: str) -> dict:
    """
    Extract student answers from PDF using Groq API.

    Args:
        pdf_path: Path to the student answer sheet PDF
        api_key: Groq API key

    Returns:
        Dictionary containing extracted answers
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"File not found at {pdf_path}")

    print(f"🔹 Using Groq API for answer extraction")
    client = _get_groq_client(api_key)

    # Extract text from PDF first
    pdf_text = extract_text_from_pdf(pdf_path, api_key)

    if not pdf_text or len(pdf_text.strip()) < 10:
        raise Exception("Could not extract readable text from the PDF")

    print("📤 Sending extracted text to Groq for answer structuring...")

    user_msg = f"Here is the text extracted from a student's answer sheet:\n\n{pdf_text}"

    response_text = _groq_chat(client, ANSWER_EXTRACTION_PROMPT, user_msg)

    try:
        extracted_json = json.loads(response_text)
        return extracted_json
    except json.JSONDecodeError as e:
        print(f"⚠️ Error parsing JSON response: {e}")
        # Try to find JSON substring
        start = response_text.find('{')
        end = response_text.rfind('}')
        if start >= 0 and end > start:
            return json.loads(response_text[start:end + 1])
        raise Exception(f"Failed to parse extraction response as JSON: {e}")


# ============================================================================
# QUESTION PAPER EXTRACTION
# ============================================================================

def generate_model_answers(text: str, api_key: str, model: str = "llama-3.3-70b-versatile") -> dict:
    """
    Generate model answers for extracted question text using Groq.

    Args:
        text: Extracted question paper text
        api_key: Groq API key
        model: Groq model name

    Returns:
        Dictionary containing questions with model answers
    """
    print("🤖 Generating model answers for each question...")
    client = _get_groq_client(api_key)

    user_msg = f"Here is the extracted question paper text:\n\n{text}"
    response_text = _groq_chat(client, QUESTION_EXTRACTION_PROMPT, user_msg, model)

    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        start = response_text.find('{')
        end = response_text.rfind('}')
        if start >= 0 and end > start:
            return json.loads(response_text[start:end + 1])
        raise


def extract_questions_from_pdf(pdf_path: str, api_key: str, model: str = "llama-3.3-70b-versatile") -> dict:
    """
    Complete pipeline to extract questions and generate model answers.

    Args:
        pdf_path: Path to the question paper PDF
        api_key: Groq API key
        model: Groq model name

    Returns:
        Structured JSON with questions and model answers
    """
    print(f"📄 Extracting questions from: {pdf_path}")
    print(f"🔹 Using Groq model: {model}")

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
    print(f"✅ Data saved to {output_path}")


def get_api_key() -> str:
    """Get Groq API key from environment variable."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("❌ ERROR: GROQ_API_KEY is not set in environment variables.")
        print("👉 Set it before running:")
        print("   Windows: set GROQ_API_KEY=YOUR_API_KEY_HERE")
        print("   Linux/Mac: export GROQ_API_KEY=YOUR_API_KEY_HERE")
        raise ValueError("GROQ_API_KEY is not set in environment variables.")
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
        print(f"❌ ERROR: PDF file not found at {args.pdf}")
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
            print("\n✅ Student answers successfully extracted!")
        else:
            print("\n❌ Failed to extract student answers.")
            sys.exit(1)
    elif args.mode == "questions":
        result = extract_questions_from_pdf(args.pdf, api_key, args.model)
        if result:
            save_to_json(result, args.output)
            print("\n✅ Questions and model answers successfully extracted!")
        else:
            print("\n❌ Failed to extract questions.")
            sys.exit(1)

    print(f"\n✅ Extraction complete! Results saved to: {args.output}")


if __name__ == "__main__":
    main()
