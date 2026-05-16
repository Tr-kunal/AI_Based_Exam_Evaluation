"""
Outputs:
 - debug_outputs/raw_page_<n>.png           (raw converted page)
 - debug_outputs/page_<n>_cand_<k>.png     (various preprocessing candidates)
 - debug_outputs/page_<n>_best.png         (best candidate selected)
 - debug_outputs/page_<n>_overlay.png      (overlay boxes for recognized words)
 - data/diagram_images/                     (diagram crops if found)
 - cleaned_text_debug.txt                   (recognized text + confidences)
"""

import os
from pdf2image import convert_from_path
from PIL import Image
import pytesseract
import cv2
import numpy as np

# ---------- CONFIG ----------
PDF_FILE = "data/student_handwritten.pdf"          # Change to your PDF
POPPLER_PATH = None                                # e.g., r"C:\poppler-22.04.0\bin" on Windows or None on Mac/Linux
TESSERACT_CMD = None                               # e.g., r"C:\Program Files\Tesseract-OCR\tesseract.exe"
DPI = 400                                          # try 300, 400, 600
OUTPUT_TEXT = "cleaned_text_debug.txt"
DEBUG_DIR = "debug_outputs"
DIAGRAM_DIR = "data/diagram_images"

os.makedirs(DEBUG_DIR, exist_ok=True)
os.makedirs(DIAGRAM_DIR, exist_ok=True)

if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

# ---------- helper functions ----------
def save_img(path, img):
    cv2.imwrite(path, img)

def apply_clahe(gray):
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    return clahe.apply(gray)

def deskew_image(gray):
    # Simple deskew by computing angle of the largest contours (not perfect but helps)
    coords = np.column_stack(np.where(gray < 255))
    if coords.shape[0] < 10:
        return gray
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    (h, w) = gray.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return rotated

def ocr_and_confidence(img, config):
    # returns (text_string, mean_conf, data_dict)
    data = pytesseract.image_to_data(img, config=config, output_type=pytesseract.Output.DICT)
    texts = []
    confs = []
    for t, c in zip(data.get('text', []), data.get('conf', [])):
        if t.strip() != "" and c not in ("-1", "-1\n"):
            try:
                ci = float(c)
            except:
                continue
            if ci > 0:
                texts.append(t)
                confs.append(ci)
    mean_conf = float(np.mean(confs)) if confs else -1.0
    text_out = "\n".join(data.get('text', []))
    return text_out, mean_conf, data

# ---------- Convert PDF to images ----------
print("Converting PDF to images...")
try:
    if POPPLER_PATH:
        pages = convert_from_path(PDF_FILE, dpi=DPI, poppler_path=POPPLER_PATH)
    else:
        pages = convert_from_path(PDF_FILE, dpi=DPI)
except Exception as e:
    raise SystemExit(f"Failed to convert PDF: {e}\nSet POPPLER_PATH for Windows or install poppler-utils on Linux/Mac.")

print(f"Pages converted: {len(pages)}")

all_text = []

# OCR config options to try
psm_list = ["--oem 1 --psm 6", "--oem 1 --psm 3", "--oem 1 --psm 4"]
# candidate preprocessings (functions will return images)
for page_idx, page in enumerate(pages, start=1):
    raw_path = os.path.join(DEBUG_DIR, f"raw_page_{page_idx}.png")
    page.save(raw_path, "PNG")
    print(f"\n--- Page {page_idx} saved to {raw_path} ---")
    # read into OpenCV
    img_color = cv2.imread(raw_path)
    if img_color is None:
        print("ERROR: raw image could not be read. Check path:", raw_path)
        continue
    gray = cv2.cvtColor(img_color, cv2.COLOR_BGR2GRAY)

    # produce list of candidate preprocessed images
    candidates = []
    # 1) original gray
    candidates.append(("orig_gray", gray.copy()))
    # 2) CLAHE + median
    clahe_img = apply_clahe(gray)
    clahe_img = cv2.medianBlur(clahe_img, 3)
    candidates.append(("clahe_med", clahe_img))
    # 3) adaptive threshold (binary)
    adapt = cv2.adaptiveThreshold(clahe_img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                  cv2.THRESH_BINARY, 11, 2)
    candidates.append(("adaptive", adapt))
    # 4) Otsu threshold
    _, otsu = cv2.threshold(clahe_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    candidates.append(("otsu", otsu))
    # 5) inverted Otsu (text white -> black background expected by tesseract)
    candidates.append(("otsu_inv", 255 - otsu))
    # 6) deskew + adaptive
    desk = deskew_image(gray)
    desk_clahe = apply_clahe(desk)
    desk_adapt = cv2.adaptiveThreshold(desk_clahe, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY, 11, 2)
    candidates.append(("desk_adapt", desk_adapt))
    # optionally add more candidates if needed

    # save candidates
    for k, (name, img_c) in enumerate(candidates):
        save_img(os.path.join(DEBUG_DIR, f"page{page_idx}_cand_{k}_{name}.png"), img_c)

    # Try multiple configs on each candidate and pick best by mean confidence
    best = {"conf": -1.0, "text": "", "candidate_name": None, "img": None, "data": None, "config": None}
    for name, img_c in candidates:
        # Ensure image is in the PIL-friendly format for pytesseract if needed
        pil_img = Image.fromarray(img_c)
        for cfg in psm_list:
            try:
                text, mean_conf, data = ocr_and_confidence(pil_img, config=cfg)
            except Exception as e:
                print("Tesseract exception:", e)
                continue
            # save candidate result quick
            print(f"Page {page_idx} candidate '{name}' cfg '{cfg}' mean_conf={mean_conf:.2f} len_text={len(text.strip())}")
            if mean_conf > best["conf"]:
                best.update({
                    "conf": mean_conf,
                    "text": text,
                    "candidate_name": name,
                    "img": img_c,
                    "data": data,
                    "config": cfg
                })

    # Save best candidate image and overlay bounding boxes
    if best["img"] is not None:
        best_img_path = os.path.join(DEBUG_DIR, f"page_{page_idx}_best.png")
        save_img(best_img_path, best["img"])
        overlay = cv2.cvtColor(best["img"], cv2.COLOR_GRAY2BGR)
        data = best["data"]
        if data:
            n_boxes = len(data.get('text', []))
            for i in range(n_boxes):
                text_i = data['text'][i].strip()
                conf_i = float(data['conf'][i]) if data['conf'][i].strip() != "" else -1.0
                if text_i != "" and conf_i > 10:   # threshold to draw boxes
                    x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                    cv2.rectangle(overlay, (x, y), (x+w, y+h), (0,255,0), 1)
                    cv2.putText(overlay, f"{int(conf_i)}", (x, y-3), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0,0,255), 1)

        overlay_path = os.path.join(DEBUG_DIR, f"page_{page_idx}_overlay.png")
        save_img(overlay_path, overlay)

    # Save cleaned text for this page with best config
    page_header = f"=== PAGE {page_idx} | best_candidate={best['candidate_name']} config={best['config']} mean_conf={best['conf']:.2f} ===\n"
    all_text.append(page_header)
    all_text.append(best["text"] if best["text"] else "[NO TEXT FOUND]\n")
    all_text.append("\n\n")

    # ---------- (Optional) simple diagram detection (large contours) ----------
    # We re-use the adaptive threshold to find large regions that may be diagrams
    try:
        big_contours, _ = cv2.findContours(255 - candidates[2][1], cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        diag_count = 0
        for cnt in big_contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w > 60 and h > 60:
                diag_count += 1
                crop = img_color[y:y+h, x:x+w]
                diag_path = os.path.join(DIAGRAM_DIR, f"page{page_idx}_diagram{diag_count}.png")
                cv2.imwrite(diag_path, crop)
        if diag_count:
            print(f"Saved {diag_count} diagram(s) for page {page_idx} in {DIAGRAM_DIR}")
    except Exception:
        pass

# Write out final cleaned debug text
with open(OUTPUT_TEXT, "w", encoding="utf-8") as f:
    f.writelines(all_text)
