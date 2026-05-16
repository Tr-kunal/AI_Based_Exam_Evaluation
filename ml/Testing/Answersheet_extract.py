import os
import io
import json
from pdf2image import convert_from_path
import cv2
import numpy as np
from PIL import Image
import google.generativeai as genai
import time


# Step 0. Configure API
api_key = os.environ.get("GEMINI_API_KEY")

# Ask manually if not found
if not api_key:
    print("⚠️ GEMINI_API_KEY not found in environment.")
    api_key = input("Enter your Gemini API Key: ").strip()

# Configure Gemini
genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-2.5-pro")


def preprocess_image(img: Image.Image) -> Image.Image:
    """Enhance for OCR: grayscale, blur, Otsu, and dilate to darken faint writing."""
    arr = np.array(img.convert("L"))
    blur = cv2.GaussianBlur(arr, (5, 5), 0)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = np.ones((2, 2), np.uint8)
    # Dilation - thickening handwriting, better OCR (optional but good for faint pens)
    thresh = cv2.dilate(thresh, kernel, iterations=1)
    return Image.fromarray(thresh)


def pdf_to_images(pdf_path: str):
    """Convert PDF pages to high-resolution Pillow images."""
    return convert_from_path(pdf_path, dpi=300)


def extract_answers_from_sheet(pdf_path: str) -> dict:
    """Extract answers as question_no → answer_text from a student's handwritten answer sheet PDF."""
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    pages = pdf_to_images(pdf_path)
    if not pages:
        raise ValueError(f"No pages found in PDF: {pdf_path}")
    results = []

    prompt = """You will be provided with 3 consecutive pages from a student's handwritten answer sheet. For all pages, extract every answer and its question number (e.g., Q1, Q2(a), Q3), as they appear across the batch.\nReply ONLY with a JSON array like:\n[{\"question_no\": \"Q1\", \"answer_text\": \"Answer text...\"}, {\"question_no\": \"Q2\", \"answer_text\": \"...\"}]\nIf a question number is not visible, infer it from nearby answers. Do NOT add commentary, explanation, or markdown, just the raw JSON."""

    BATCH_SIZE = 3
    total_pages = len(pages)
    batch_num = 1
    for batch_start in range(0, total_pages, BATCH_SIZE):
        batch_pages = pages[batch_start:batch_start + BATCH_SIZE]
        cleaned_images = [preprocess_image(page) for page in batch_pages]
        batch_parts = [
            {"text": prompt}
        ]
        for cleaned in cleaned_images:
            buffer = io.BytesIO()
            cleaned.save(buffer, format="JPEG")
            image_data = buffer.getvalue()
            batch_parts.append({"inline_data": {"mime_type": "image/jpeg", "data": image_data}})

        while True:
            try:
                response = model.generate_content(
                    contents=[{
                        "role": "user",
                        "parts": batch_parts
                    }],
                    generation_config={"temperature": 0.15, "max_output_tokens": 4096}
                )
                break  # Success
            except Exception as e:
                err_str = str(e).lower()
                if "429" in err_str or "quota" in err_str or "resourceexhausted" in err_str:
                    print(f"[Batch {batch_num}] Gemini API quota exceeded. Waiting 65 seconds before retrying...")
                    time.sleep(65)
                    continue
                else:
                    raise RuntimeError(f"Gemini API error on batch {batch_num}: {e}")

        # Parse Gemini output
        try:
            raw = response.candidates[0].content.parts[0].text
        except (AttributeError, IndexError, KeyError):
            raise RuntimeError(f"Could not retrieve text output from Gemini response. Response object: {response}")
        text_output = raw.strip().strip("`")
        if text_output.lower().startswith("json"):
            text_output = text_output[4:].strip()
        if not (text_output.startswith("[") or text_output.startswith("{")):
            start = text_output.find("[")
            end = text_output.rfind("]")
            if start != -1 and end != -1:
                text_output = text_output[start:end+1]
        try:
            page_results = json.loads(text_output)
            if isinstance(page_results, dict):
                page_results = [page_results]
            results.extend(page_results)
        except json.JSONDecodeError:
            raise ValueError(f"❌ JSON parse failed for batch {batch_num}. Gemini replied:\n{raw}\nCleaned:\n{text_output}")
        print(f"Completed batch {batch_num} ({len(batch_pages)} pages).")
        batch_num += 1

    answer_map = {item["question_no"]: item["answer_text"] for item in results if "question_no" in item and "answer_text" in item}
    return answer_map


if __name__ == "__main__":
    sheet_pdf = r"sample\student_answers.pdf"
    extracted = extract_answers_from_sheet(sheet_pdf)

    # Save output
    with open("student_answers_extracted.json", "w", encoding="utf-8") as f:
        json.dump(extracted, f, ensure_ascii=False, indent=2)

    print("✅ Extraction complete.")
    print("Output saved to: student_answers_extracted.json")
