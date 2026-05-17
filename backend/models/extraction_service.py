"""
Extraction Service Wrapper
===========================

Clean interface to the integrated extraction model for FastAPI endpoints.
Wraps Final_Model_Descriptive/Extraction_modelanswers/integrated_extraction.py

Functions:
    - extract_student_answers(pdf_path): Extract answers from student answer sheet
    - extract_question_paper(pdf_path): Extract questions and generate model answers
"""

import os
import sys
import json
from pathlib import Path

# Add the extraction model directory to Python path
EXTRACTION_DIR = Path(__file__).parent.parent / "Final_Model_Descriptive" / "Extraction_modelanswers"
sys.path.insert(0, str(EXTRACTION_DIR))

try:
    from integrated_extraction import (
        extract_answers_from_pdf,
        extract_questions_from_pdf,
        get_api_key
    )
except ImportError as e:
    print(f"[!] Warning: Could not import extraction module: {e}")
    extract_answers_from_pdf = None
    extract_questions_from_pdf = None
    get_api_key = None


class ExtractionError(Exception):
    """Custom exception for extraction errors"""
    pass


def extract_student_answers(pdf_path: str) -> dict:
    """
    Extract student answers from a PDF answer sheet.

    Args:
        pdf_path: Absolute path to the student answer sheet PDF

    Returns:
        Dictionary containing extracted student answers

    Raises:
        ExtractionError: If extraction fails
        FileNotFoundError: If PDF file doesn't exist
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    if extract_answers_from_pdf is None:
        raise ExtractionError("Extraction module not available. Check dependencies.")

    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ExtractionError(
                "GEMINI_API_KEY not set in environment variables. "
                "Please set it before using extraction features."
            )

        result = extract_answers_from_pdf(pdf_path, api_key)

        if not result:
            raise ExtractionError("Extraction returned empty result")

        return result

    except ExtractionError:
        raise
    except Exception as e:
        raise ExtractionError(f"Failed to extract student answers: {str(e)}")


def extract_question_paper(pdf_path: str, model: str = "gemini-2.5-flash") -> dict:
    """
    Extract questions from a question paper PDF and generate model answers.

    Args:
        pdf_path: Absolute path to the question paper PDF
        model: Gemini model name to use (default: gemini-2.5-flash)

    Returns:
        Dictionary containing questions with model answers

    Raises:
        ExtractionError: If extraction fails
        FileNotFoundError: If PDF file doesn't exist
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    if extract_questions_from_pdf is None:
        raise ExtractionError("Extraction module not available. Check dependencies.")

    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ExtractionError(
                "GEMINI_API_KEY not set in environment variables. "
                "Please set it before using extraction features."
            )

        print(f"[*] Requesting extraction with model: {model}")
        result = extract_questions_from_pdf(pdf_path, api_key, model)

        if not result:
            raise ExtractionError("Extraction returned empty result")

        return result

    except ExtractionError:
        raise
    except Exception as e:
        raise ExtractionError(f"Failed to extract question paper: {str(e)}")


def save_extraction_result(data: dict, output_path: str) -> None:
    """Save extraction result to a JSON file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
